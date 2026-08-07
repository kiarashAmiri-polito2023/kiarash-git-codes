import sys, json, re, time, traceback
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROJECT_ROOT = Path.cwd()
VAL_FILE = PROJECT_ROOT / "dataset" / "val.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora"

def log(msg):
    print(msg, flush=True)

def parse_action(text):
    m = re.search(r"<action>\s*\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m2 = re.search(r"\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", text)
    if m2:
        return float(m2.group(1)), float(m2.group(2))
    return 0.0, 0.0

def main():
    log("=" * 70)
    log("[TEST] EVALUATION SMOKE TEST ON 3 SAMPLES")
    log("=" * 70)

    log("[1/5] Loading processor from adapter dir...")
    processor = AutoProcessor.from_pretrained(OUTPUT_DIR, trust_remote_code=True)

    log("[2/5] Loading base model (fp16)...")
    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

    log("[3/5] Attaching LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)

    # CRITICAL FIX 1: disable gradient checkpointing inherited from training
    try:
        model.gradient_checkpointing_disable()
    except Exception as e:
        log(f"    (checkpoint disable note: {e})")

    # CRITICAL FIX 2: force KV cache ON for fast generation
    base_model.config.use_cache = True
    model.eval()
    log("[4/5] Checkpointing OFF | KV-Cache ON | VRAM: {:.2f} GB".format(torch.cuda.memory_allocated()/1e9))

    with open(VAL_FILE, "r", encoding="utf-8") as f:
        samples = [json.loads(l) for l in f if l.strip()]

    test_samples = samples[:3]
    log(f"[5/5] Generating predictions for {len(test_samples)} samples...\n")

    for idx, s in enumerate(test_samples):
        img_path = PROJECT_ROOT / s["image"]
        image = Image.open(img_path).convert("RGB")
        gt = s.get("ground_truth_action", [0.0, 0.0])
        user_txt = ""
        for msg in s.get("conversations", []):
            if (msg.get("from") or msg.get("role")) in ["user", "human"]:
                user_txt = (msg.get("value") or msg.get("content")).replace("<image>\n", "").replace("<image>", "")

        msgs = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
        txt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[txt], images=[image], return_tensors="pt").to("cuda")

        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=96, do_sample=False, use_cache=True)
        dt = time.time() - t0

        try:
            out_txt = processor.tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        except Exception:
            out_txt = processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        pv, pw = parse_action(out_txt)
        log("  Sample {}: {:.1f}s | GT: [{:+.3f}, {:+.3f}] | PRED: [{:+.3f}, {:+.3f}]".format(idx+1, dt, float(gt[0]), float(gt[1]), pv, pw))
        log("    RAW: " + out_txt[:180].replace("\n", " "))
        log("")

    log("[SUCCESS] Smoke test passed! Generation pipeline is healthy.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        log("[FATAL ERROR]\n" + err)
        with open("eval_error.log", "w", encoding="utf-8") as f:
            f.write(err)
        sys.exit(1)
