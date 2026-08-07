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

# ==============================================================================
# DATASET WITH LABEL MASKING (supervision ONLY on assistant response tokens)
# ==============================================================================
class MaskedVLADataset(Dataset):
    def __init__(self, jsonl_path: Path, processor):
        self.processor = processor
        self.tok = processor.tokenizer
        self.records = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.records.append(json.loads(line))
        self.suffix_ids = []
        for rec in self.records:
            asst = ""
            for msg in rec.get("conversations", []):
                if msg.get("from") in ("assistant", "gpt"):
                    asst = msg.get("value", "")
            self.suffix_ids.append(
                self.tok(asst + "<|im_end|>", add_special_tokens=False)["input_ids"]
            )

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        image = Image.open(PROJECT_ROOT / rec["image"]).convert("RGB")
        user_txt = ""
        for msg in rec.get("conversations", []):
            if msg.get("from") in ("user", "human"):
                user_txt = msg["value"].replace("<image>\n", "").replace("<image>", "")

        msgs = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": user_txt}]}]
        prefix_text = self.processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        pref = self.processor(text=[prefix_text], images=[image], return_tensors="pt")

        suffix = torch.tensor([self.suffix_ids[idx]], dtype=torch.long)
        input_ids = torch.cat([pref["input_ids"], suffix], dim=1)
        labels = torch.cat([torch.full_like(pref["input_ids"], -100), suffix], dim=1)

        out = {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids), "labels": labels}
        for k, v in pref.items():
            if k not in ("input_ids", "attention_mask"):
                out[k] = v
        return out

def collate_single(batch):
    return batch[0]

# ==============================================================================
# TRAINING
# ==============================================================================
def train():
    log("=" * 78)
    log("[TRAIN v2] LABEL-MASKED QLoRA | epochs={} | {}".format(EPOCHS, torch.cuda.get_device_name(0)))
    log("=" * 78)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, quantization_config=bnb,
                                                        device_map="auto", trust_remote_code=True)
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={"use_reentrant": False})
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = MaskedVLADataset(TRAIN_FILE, processor)
    loader = DataLoader(ds, batch_size=1, shuffle=True, collate_fn=collate_single)

    # --- mask sanity check ---
    ex = ds[0]
    sup_ids = ex["labels"][ex["labels"] != -100]
    log("[mask check] total={} | supervised={} | ratio={:.1f}%".format(
        ex["input_ids"].shape[1], sup_ids.shape[0],
        100.0 * sup_ids.shape[0] / ex["input_ids"].shape[1]))
    log("[mask check] supervised text: {!r}".format(
        processor.tokenizer.decode(sup_ids, skip_special_tokens=True)[:120]))

    # --- canary indices: one fast-moving, one rotating sample ---
    canary_idx = []
    for i, rec in enumerate(ds.records):
        a = rec.get("ground_truth_action", [0, 0])
        if len(canary_idx) == 0 and abs(float(a[0])) > 0.5:
            canary_idx.append(i)
        elif len(canary_idx) == 1 and abs(float(a[1])) > 0.3:
            canary_idx.append(i)
        if len(canary_idx) == 2:
            break
    log("[canary] fixed samples idx={} GT={}".format(
        canary_idx, [ds.records[i].get("ground_truth_action") for i in canary_idx]))

    def run_canary():
        try:
            model.eval()
            res = []
            for ci in canary_idx:
                rec = ds.records[ci]
                image = Image.open(PROJECT_ROOT / rec["image"]).convert("RGB")
                user_txt = ""
                for msg in rec.get("conversations", []):
                    if msg.get("from") in ("user", "human"):
                        user_txt = msg["value"].replace("<image>\n", "").replace("<image>", "")
                msgs = [{"role": "user", "content": [
                    {"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
                txt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                inputs = processor(text=[txt], images=[image], return_tensors="pt").to("cuda")
                with torch.no_grad():
                    out = model.generate(**inputs, max_new_tokens=64, do_sample=False, use_cache=True)
                otxt = processor.tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
                pv, pw = parse_action(otxt)
                gt = rec.get("ground_truth_action", [0, 0])
                res.append({"gt": [float(gt[0]), float(gt[1])], "pred": [pv, pw]})
                log("  [canary] GT [{:+.3f},{:+.3f}] -> PRED [{:+.3f},{:+.3f}]".format(
                    float(gt[0]), float(gt[1]), pv, pw))
            return res
        except Exception as e:
            log("  [canary] skipped: {}".format(e))
            return None
        finally:
            model.train()
            model.config.use_cache = False

    steps = (len(loader) // GRAD_ACCUM) * EPOCHS
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.01)
    sched = get_cosine_schedule_with_warmup(opt, max(1, int(steps * 0.05)), max(1, steps))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    history = {"epochs": [], "canary": []}

    log("\n[*] {} samples | {} optimizer steps | starting...\n".format(len(ds), steps))
    gstep = 0
    t_start = time.time()
    for ep in range(EPOCHS):
        model.train()
        model.config.use_cache = False
        ep_loss, n = 0.0, 0
        opt.zero_grad()
        for step, batch in enumerate(loader):
            batch = {k: v.to("cuda") for k, v in batch.items()}
            out = model(**batch)
            loss = out.loss / GRAD_ACCUM
            loss.backward()
            ep_loss += out.loss.item()
            n += 1
            if (step + 1) % GRAD_ACCUM == 0 or (step + 1) == len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                gstep += 1
                if gstep % 15 == 0:
                    log("  ep{} [{:03d}/{}] loss(sup)={:.4f} lr={:.2e} elapsed={:.0f}s".format(
                        ep + 1, step + 1, len(loader), out.loss.item(),
                        sched.get_last_lr()[0], time.time() - t_start))

        avg = ep_loss / max(1, n)
        log("[OK] Epoch {} done | avg SUPERVISED loss: {:.4f}".format(ep + 1, avg))
        history["epochs"].append({"epoch": ep + 1, "avg_supervised_loss": avg})

        ckpt = OUTPUT_DIR / ("epoch_{}".format(ep + 1))
        model.save_pretrained(ckpt)
        log("  checkpoint saved -> {}".format(ckpt.name))

        log("  [canary] epoch {}:".format(ep + 1))
        history["canary"].append({"epoch": ep + 1, "results": run_canary()})

    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    with open(OUTPUT_DIR / "training_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    del model, opt, sched
    torch.cuda.empty_cache()
    log("\n[OK] Training complete. Adapters in {}".format(OUTPUT_DIR))

# ==============================================================================
# EVALUATION with scientific baselines
# ==============================================================================
def evaluate():
    log("=" * 78)
    log("[EVAL v2] Full benchmark on validation set")
    log("=" * 78)

    processor = AutoProcessor.from_pretrained(OUTPUT_DIR, trust_remote_code=True)
    base = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=torch.float16,
                                                       device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(base, OUTPUT_DIR)
    try:
        model.gradient_checkpointing_disable()
    except Exception:
        pass
    base.config.use_cache = True
    model.eval()

    with open(VAL_FILE, encoding="utf-8") as f:
        samples = [json.loads(l) for l in f if l.strip()]
    with open(TRAIN_FILE, encoding="utf-8") as f:
        tr = [json.loads(l) for l in f if l.strip()]

    mv = sum(float(r["ground_truth_action"][0]) for r in tr) / len(tr)
    mw = sum(float(r["ground_truth_action"][1]) for r in tr) / len(tr)

    log("[*] Benchmarking {} frames...".format(len(samples)))
    preds = []
    t0 = time.time()
    for idx, s in enumerate(samples):
        image = Image.open(PROJECT_ROOT / s["image"]).convert("RGB")
        gt = s.get("ground_truth_action", [0.0, 0.0])
        user_txt = ""
        for msg in s.get("conversations", []):
            if msg.get("from") in ("user", "human"):
                user_txt = msg["value"].replace("<image>\n", "").replace("<image>", "")
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
        txt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[txt], images=[image], return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=96, do_sample=False, use_cache=True)
        otxt = processor.tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        pv, pw = parse_action(otxt)
        preds.append({"idx": idx, "gt": [float(gt[0]), float(gt[1])], "pred": [pv, pw],
                      "class": s.get("behavior_class", "UNKNOWN"), "raw": otxt[:200]})
        if (idx + 1) % 10 == 0 or idx == len(samples) - 1:
            log("  [{:02d}/{}] GT [{:+.2f},{:+.2f}] PRED [{:+.2f},{:+.2f}] ({:.0f}s elapsed)".format(
                idx + 1, len(samples), float(gt[0]), float(gt[1]), pv, pw, time.time() - t0))

    mae_v = sum(abs(p["pred"][0] - p["gt"][0]) for p in preds) / len(preds)
    mae_w = sum(abs(p["pred"][1] - p["gt"][1]) for p in preds) / len(preds)
    zero_v = sum(abs(p["gt"][0]) for p in preds) / len(preds)
    zero_w = sum(abs(p["gt"][1]) for p in preds) / len(preds)
    mean_v = sum(abs(p["gt"][0] - mv) for p in preds) / len(preds)
    mean_w = sum(abs(p["gt"][1] - mw) for p in preds) / len(preds)

    log("")
    log("=" * 78)
    log("FINAL SCIENTIFIC RESULTS:")
    log("  MODEL    MAE_v={:.4f} m/s | MAE_w={:.4f} rad/s".format(mae_v, mae_w))
    log("  ZERO-BL  MAE_v={:.4f} m/s | MAE_w={:.4f} rad/s   (always [0,0])".format(zero_v, zero_w))
    log("  MEAN-BL  MAE_v={:.4f} m/s | MAE_w={:.4f} rad/s   (always train-mean)".format(mean_v, mean_w))
    verdict_v = "MODEL BEATS BASELINES" if mae_v < min(zero_v, mean_v) else "MODEL FAILS vs baseline"
    log("  VERDICT (v): {}".format(verdict_v))
    classes = {}
    for p in preds:
        classes.setdefault(p["class"], []).append(p)
    for c, ps in sorted(classes.items()):
        cv = sum(abs(p["pred"][0] - p["gt"][0]) for p in ps) / len(ps)
        cw = sum(abs(p["pred"][1] - p["gt"][1]) for p in ps) / len(ps)
        log("  [{}] n={:02d} | MAE_v={:.4f} | MAE_w={:.4f}".format(c, len(ps), cv, cw))
    log("=" * 78)

    with open(PROJECT_ROOT / "eval_results_v2.json", "w", encoding="utf-8") as f:
        json.dump({"mae_v": mae_v, "mae_w": mae_w,
                   "zero_baseline": [zero_v, zero_w], "mean_baseline": [mean_v, mean_w],
                   "predictions": preds}, f, indent=2)
    log("Saved: eval_results_v2.json")

if __name__ == "__main__":
    try:
        train()
        evaluate()
        log("\n[DONE] v2 masked-training + evaluation pipeline finished.")
    except Exception:
        err = traceback.format_exc()
        log("[FATAL]\n" + err)
        with open("train_v2_error.log", "w", encoding="utf-8") as f:
            f.write(err)
        sys.exit(1)
