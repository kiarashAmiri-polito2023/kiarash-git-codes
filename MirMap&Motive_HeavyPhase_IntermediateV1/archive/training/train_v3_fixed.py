import sys, os, json, re, time, traceback
from pathlib import Path
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from transformers import (
    AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig,
    get_cosine_schedule_with_warmup
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROJECT_ROOT = Path.cwd()
TRAIN_FILE = PROJECT_ROOT / "dataset" / "train.jsonl"
VAL_FILE = PROJECT_ROOT / "dataset" / "val.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora_v2"
EPOCHS = 6
GRAD_ACCUM = 4
def log(msg):
    print(msg, flush=True)
def parse_action(text):
    m = re.search(r"<action>\s*\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", text)
    if not m:
        m = re.search(r"\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 0.0, 0.0
class RobustVLADataset(Dataset):
    def __init__(self, jsonl_path, processor):
        self.proc = processor
        self.tok = processor.tokenizer
        self.records = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.records.append(json.loads(line))
        self.suffix_ids = []
        for rec in self.records:
            asst_val = ""
            for msg in rec.get("conversations", []):
                if msg.get("from") in ("assistant", "gpt"):
                    asst_val = msg.get("value", "")
            self.suffix_ids.append(
                self.tok(asst_val + "<|im_end|>", add_special_tokens=False)["input_ids"]
            )
        self._plen_cache = {}
    def __len__(self):
        return len(self.records)
    def __getitem__(self, idx):
        rec = self.records[idx]
        image = Image.open(PROJECT_ROOT / rec["image"]).convert("RGB")
        u_txt, a_txt = "", ""
        for msg in rec.get("conversations", []):
            role = msg.get("from") or msg.get("role")
            val = msg.get("value") or msg.get("content")
            if role in ["user", "human"]:
                u_txt = val.replace("<image>\n", "").replace("<image>", "")
            elif role in ["assistant", "gpt"]:
                a_txt = val
        user_msgs = [{"role": "user", "content": [
            {"type": "image", "image": image}, {"type": "text", "text": u_txt}]}]
        full_msgs = user_msgs + [{"role": "assistant", "content": [{"type": "text", "text": a_txt}]}]
        full_text = self.proc.apply_chat_template(full_msgs, tokenize=False, add_generation_prompt=False)
        raw = self.proc(text=[full_text], images=[image], return_tensors="pt")
        input_ids = raw["input_ids"]
        plen = self._plen_cache.get(idx)
        if plen is None:
            p_text = self.proc.apply_chat_template(user_msgs, tokenize=False, add_generation_prompt=True)
            p_raw = self.proc(text=[p_text], images=[image], return_tensors="pt")
            p_ids = p_raw["input_ids"][0].tolist()
            f_ids = input_ids[0].tolist()
            s_ids = self.suffix_ids[idx]
            if len(s_ids) > 0 and f_ids[-len(s_ids):] == list(s_ids):
                plen = len(f_ids) - len(s_ids)
            elif f_ids[:len(p_ids)] == p_ids:
                plen = len(p_ids)
            else:
                raise RuntimeError("Alignment error at index " + str(idx))
            self._plen_cache[idx] = plen
        labels = torch.full_like(input_ids, -100)
        labels[0, plen:] = input_ids[0, plen:]
        raw["labels"] = labels
        return raw
def collate(batch):
    return batch[0]
def train():
    log("="*78)
    log("[TRAIN v3.2] MASKED QLoRA | epochs=" + str(EPOCHS) + " | " + str(torch.cuda.get_device_name(0)))
    log("="*78)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    proc = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    base_m = AutoModelForImageTextToText.from_pretrained(MODEL_ID, quantization_config=bnb,
                                                         device_map="auto", trust_remote_code=True)
    base_m.config.use_cache = False
    base_m = prepare_model_for_kbit_training(base_m, gradient_checkpointing_kwargs={"use_reentrant": False})
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
    model = get_peft_model(base_m, lora)
    model.print_trainable_parameters()
    ds = RobustVLADataset(TRAIN_FILE, proc)
    loader = DataLoader(ds, batch_size=1, shuffle=True, collate_fn=collate)
    e0 = ds[0]
    sup = e0["labels"][e0["labels"] != -100]
    log("[mask] total=" + str(e0["input_ids"].shape[1]) + " | supervised=" + str(sup.shape[0]) + " (" + str(round(100*sup.shape[0]/e0["input_ids"].shape[1], 1)) + "%)")
    log("[sup] " + proc.tokenizer.decode(sup, skip_special_tokens=True)[:100])
    c_ids = []
    for i, r in enumerate(ds.records):
        a = r.get("ground_truth_action", [0,0])
        if len(c_ids)==0 and abs(float(a[0]))>0.5: c_ids.append(i)
        elif len(c_ids)==1 and abs(float(a[1]))>0.3: c_ids.append(i)
        if len(c_ids)==2: break
    log("[canary] idx=" + str(c_ids) + " GT=" + str([ds.records[i].get("ground_truth_action") for i in c_ids]))
    def canary():
        try:
            model.eval()
            try: model.gradient_checkpointing_disable()
            except: pass
            base_m.config.use_cache = True
            res = []
            for ci in c_ids:
                r = ds.records[ci]
                img = Image.open(PROJECT_ROOT / r["image"]).convert("RGB")
                u = ""
                for m in r.get("conversations",[]):
                    if m.get("from") in ("user","human"): u=m["value"].replace("<image>\n","").replace("<image>","")
                ms = [{"role":"user","content":[{"type":"image","image":img},{"type":"text","text":u}]}]
                tx = proc.apply_chat_template(ms, tokenize=False, add_generation_prompt=True)
                inp = proc(text=[tx], images=[img], return_tensors="pt").to("cuda")
                with torch.no_grad():
                    ot = model.generate(**inp, max_new_tokens=96, do_sample=False, use_cache=True)
                otx = proc.tokenizer.decode(ot[0][inp["input_ids"].shape[1]:], skip_special_tokens=True)
                pv, pw = parse_action(otx)
                gt = r.get("ground_truth_action",[0,0])
                res.append({"gt":[float(gt[0]),float(gt[1])],"pred":[pv,pw]})
                log("  CANARY GT[" + str(float(gt[0])) + "," + str(float(gt[1])) + "] -> PRED[" + str(pv) + "," + str(pw) + "]")
            return res
        except Exception as ex:
            log("  (canary err: " + str(ex) + ")"); return None
        finally:
            model.train(); base_m.config.use_cache = False
    steps = (len(loader)//GRAD_ACCUM)*EPOCHS
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.01)
    sched = get_cosine_schedule_with_warmup(opt, max(1,int(steps*0.05)), max(1,steps))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    hist={"epochs":[],"canary":[]}
    log("\n[*] " + str(len(ds)) + " samples | " + str(steps) + " steps | Start...\n")
    gstep=0; t0=time.time()
    for ep in range(EPOCHS):
        model.train(); base_m.config.use_cache = False
        e_loss,n=0.0,0; opt.zero_grad()
        for step,batch in enumerate(loader):
            batch={k:v.to("cuda") for k,v in batch.items()}
            out=model(**batch); loss=out.loss/GRAD_ACCUM
            loss.backward(); e_loss+=out.loss.item(); n+=1
            if (step+1)%GRAD_ACCUM==0 or (step+1)==len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
                opt.step(); sched.step(); opt.zero_grad(); gstep+=1
                if gstep%15==0:
                    log("  E" + str(ep+1) + " S[" + str(step+1) + "/" + str(len(loader)) + "] loss=" + str(round(out.loss.item(),4)) + " lr=" + str(sched.get_last_lr()[0]) + " T=" + str(round(time.time()-t0)) + "s")
        avg=e_loss/max(1,n)
        log("\n[DONE] Epoch " + str(ep+1) + " | Avg Loss: " + str(round(avg,4)))
        hist["epochs"].append({"epoch":ep+1,"loss":avg})
        ckpt=OUTPUT_DIR/("epoch_" + str(ep+1))
        model.save_pretrained(ckpt)
        log("  Saved " + ckpt.name + ". Canary check...")
        hist["canary"].append({"epoch":ep+1,"res":canary()})
    model.save_pretrained(OUTPUT_DIR)
    proc.save_pretrained(OUTPUT_DIR)
    with open(OUTPUT_DIR/"training_history.json","w",encoding="utf-8") as f:
        json.dump(hist,f,indent=2)
    del model,opt,sched; torch.cuda.empty_cache()
    log("\n[OK] Training complete.")
def evaluate():
    log("="*78)
    log("[EVAL v3] VALIDATION WITH BASELINES")
    log("="*78)
    proc = AutoProcessor.from_pretrained(OUTPUT_DIR, trust_remote_code=True)
    bm = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=torch.float16, device_map="auto", trust_remote_code=True)
    m = PeftModel.from_pretrained(bm, OUTPUT_DIR)
    try: m.gradient_checkpointing_disable()
    except: pass
    bm.config.use_cache=True; m.eval()
    with open(VAL_FILE,"r",encoding="utf-8") as f: vals=[json.loads(l) for l in f if l.strip()]
    with open(TRAIN_FILE,"r",encoding="utf-8") as f: tr=[json.loads(l) for l in f if l.strip()]
    mv=sum(float(x["ground_truth_action"][0]) for x in tr)/len(tr)
    mw=sum(float(x["ground_truth_action"][1]) for x in tr)/len(tr)
    preds=[]; t0=time.time()
    log("[*] Evaluating " + str(len(vals)) + " frames...")
    for i,s in enumerate(vals):
        img=Image.open(PROJECT_ROOT/s["image"]).convert("RGB")
        gt=s.get("ground_truth_action",[0.,0.])
        u=""
        for mx in s.get("conversations",[]):
            if mx.get("from") in ("user","human"):
                u=(mx.get("value") or mx.get("content")).replace("<image>\n","").replace("<image>","")
        ms=[{"role":"user","content":[{"type":"image","image":img},{"type":"text","text":u}]}]
        tx=proc.apply_chat_template(ms,tokenize=False,add_generation_prompt=True)
        inp=proc(text=[tx],images=[img],return_tensors="pt").to("cuda")
        with torch.no_grad():
            o=m.generate(**inp,max_new_tokens=96,do_sample=False,use_cache=True)
        otx=proc.tokenizer.decode(o[0][inp["input_ids"].shape[1]:],skip_special_tokens=True)
        pv,pw=parse_action(otx)
        preds.append({"gt":[float(gt[0]),float(gt[1])],"pred":[pv,pw],"cls":s.get("behavior_class","UNKNOWN"),"raw":otx[:200]})
        if(i+1)%10==0 or i==len(vals)-1:
            log("  [" + str(i+1) + "/" + str(len(vals)) + "] GT[" + str(float(gt[0])) + "," + str(float(gt[1])) + "] PRED[" + str(pv) + "," + str(pw) + "] " + str(round(time.time()-t0)) + "s")
    mae_v=sum(abs(p["pred"][0]-p["gt"][0]) for p in preds)/len(preds)
    mae_w=sum(abs(p["pred"][1]-p["gt"][1]) for p in preds)/len(preds)
    zv=sum(abs(p["gt"][0]) for p in preds)/len(preds)
    zw=sum(abs(p["gt"][1]) for p in preds)/len(preds)
    mv_e=sum(abs(p["gt"][0]-mv) for p in preds)/len(preds)
    mw_e=sum(abs(p["gt"][1]-mw) for p in preds)/len(preds)
    log("\n"+"="*78)
    log("FINAL RESULTS:")
    log("  MODEL   MAE_v=" + str(round(mae_v, 4)) + " | MAE_w=" + str(round(mae_w, 4)))
    log("  ZERO_BL MAE_v=" + str(round(zv, 4)) + " | MAE_w=" + str(round(zw, 4)))
    log("  MEAN_BL MAE_v=" + str(round(mv_e, 4)) + " | MAE_w=" + str(round(mw_e, 4)))
    log("  VERDICT: " + ("BEATS BASELINES" if mae_v<min(zv,mv_e) else "FAILS"))
    cls={}
    for p in preds: cls.setdefault(p["cls"],[]).append(p)
    for c,ps in sorted(cls.items()):
        cv=sum(abs(x["pred"][0]-x["gt"][0]) for x in ps)/len(ps)
        cw=sum(abs(x["pred"][1]-x["gt"][1]) for x in ps)/len(ps)
        log("  " + str(c) + " n=" + str(len(ps)) + " | MAE_v=" + str(round(cv, 4)) + " | MAE_w=" + str(round(cw, 4)))
    with open(PROJECT_ROOT/"eval_results_v3.json","w",encoding="utf-8") as f:
        json.dump({"mae_v":mae_v,"mae_w":mae_w,"z_bl":[zv,zw],"m_bl":[mv_e,mw_e],"p":preds},f,indent=2)
    log("Saved: eval_results_v3.json")
if __name__=="__main__":
    try:
        train(); evaluate()
        log("\n[DONE]")
    except Exception:
        traceback.print_exc()
        with open("v3_error.log","w",encoding="utf-8") as f: f.write(traceback.format_exc())
