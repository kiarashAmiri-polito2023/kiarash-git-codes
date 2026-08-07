import os
import re
import json
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

PROJECT_ROOT = Path.cwd()
VAL_FILE = PROJECT_ROOT / "dataset" / "val.jsonl"
ADAPTER_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora"
BASE_MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"

def parse_action(text):
    try:
        m = re.search(r"\{.*?\}", text, re.DOTALL)
        if m:
            d = json.loads(m.group(0))
            return d.get("behavior_class", "UNKNOWN"), float(d.get("linear_velocity_x", 0.0)), float(d.get("angular_velocity_z", 0.0))
    except Exception:
        pass
    return "UNKNOWN", 0.0, 0.0

def evaluate():
    print("=" * 75)
    print("📊 EVALUATING FINE-TUNED VLA MODEL ON VALIDATION DATASET")
    print("=" * 75)
    
    processor = AutoProcessor.from_pretrained(ADAPTER_DIR, trust_remote_code=True)
    base_model = AutoModelForImageTextToText.from_pretrained(BASE_MODEL_ID, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.eval()

    with open(VAL_FILE, "r", encoding="utf-8") as f:
        samples = [json.loads(line.strip()) for line in f if line.strip()]

    lin_errs, ang_errs, correct = [], [], 0

    for idx, s in enumerate(samples):
        img = Image.open(PROJECT_ROOT / s["image"]).convert("RGB")
        meta = s["metadata"]
        gt_b, gt_v, gt_w = meta.get("behavior_class", ""), float(meta.get("linear_velocity_x", 0.0)), float(meta.get("angular_velocity_z", 0.0))
        
        user_txt = ""
        for msg in s.get("conversations", []):
            if (msg.get("from") or msg.get("role")) in ["user", "human"]:
                user_txt = (msg.get("value") or msg.get("content")).replace("<image>\n", "").replace("<image>", "")

        msgs = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": user_txt}]}]
        txt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[txt], images=[img], return_tensors="pt").to("cuda")

        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=128, do_sample=False)
            out_txt = processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        pred_b, pred_v, pred_w = parse_action(out_txt)
        lin_errs.append(abs(pred_v - gt_v))
        ang_errs.append(abs(pred_w - gt_w))
        if pred_b.strip().upper() == gt_b.strip().upper():
            correct += 1

        if (idx + 1) % 15 == 0 or idx == len(samples) - 1:
            print(f"  [{idx+1:02d}/{len(samples):02d}] GT: {gt_b:20s} | PRED: {pred_b:20s} | Err_v: {abs(pred_v - gt_v):.3f} m/s")

    print("\n" + "=" * 75)
    print(f"🎯 ACCURACY: {correct/len(samples)*100:.2f}% ({correct}/{len(samples)})")
    print(f"🎯 MAE Linear Velocity:  {sum(lin_errs)/len(lin_errs):.4f} m/s")
    print(f"🎯 MAE Angular Velocity: {sum(ang_errs)/len(ang_errs):.4f} rad/s")
    print("=" * 75)

if __name__ == "__main__":
    evaluate()
