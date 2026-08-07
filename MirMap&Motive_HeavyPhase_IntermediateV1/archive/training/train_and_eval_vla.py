import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Reconfigure console for clean Windows UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from transformers import (
    AutoProcessor,
    AutoModelForImageTextToText,
    BitsAndBytesConfig,
    get_cosine_schedule_with_warmup
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROJECT_ROOT = Path.cwd()
DATASET_DIR = PROJECT_ROOT / "dataset"
TRAIN_FILE = DATASET_DIR / "train.jsonl"
VAL_FILE = DATASET_DIR / "val.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora"

# ==============================================================================
# 1. MULTI-MODAL DATASET
# ==============================================================================
class MirVLADataset(Dataset):
    def __init__(self, jsonl_path: Path, processor: Any):
        self.processor = processor
        self.records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.records.append(json.loads(line.strip()))

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.records[idx]
        image_path = PROJECT_ROOT / item["image"]
        image = Image.open(image_path).convert("RGB")

        user_txt, asst_txt = "", ""
        for msg in item.get("conversations", []):
            role = msg.get("from") or msg.get("role")
            val = msg.get("value") or msg.get("content")
            if role in ["user", "human"]:
                user_txt = val.replace("<image>\n", "").replace("<image>", "")
            elif role in ["assistant", "gpt"]:
                asst_txt = val

        messages = [
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": user_txt}]},
            {"role": "assistant", "content": [{"type": "text", "text": asst_txt}]}
        ]

        prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        inputs = self.processor(text=[prompt], images=[image], padding=True, return_tensors="pt")
        inputs = {k: v.squeeze(0) for k, v in inputs.items()}
        inputs["labels"] = inputs["input_ids"].clone()
        return inputs

# ==============================================================================
# 2. TRAINING FUNCTION
# ==============================================================================
def train_vla(epochs: int = 3, batch_size: int = 1, grad_accum: int = 4, lr: float = 2e-4):
    print("=" * 80)
    print(f"[*] TRAINING QWEN3-VL VLA POLICY (Epochs: {epochs} | Accelerator: {torch.cuda.get_device_name(0)})")
    print("=" * 80)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )

    print("[*] Initializing Base Model & Processor in 4-bit...")
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    train_dataset = MirVLADataset(TRAIN_FILE, processor)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    total_steps = (len(train_loader) // grad_accum) * epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, int(total_steps * 0.05)),
        num_training_steps=max(1, total_steps)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.train()
    global_step = 0

    print(f"\n[*] Starting optimization across {len(train_dataset)} training samples (Total optimizer steps: {total_steps})...\n")

    for epoch in range(epochs):
        epoch_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            batch = {k: v.to("cuda") for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss / grad_accum
            loss.backward()
            epoch_loss += loss.item() * grad_accum

            if (step + 1) % grad_accum == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                if global_step % 10 == 0:
                    curr_lr = scheduler.get_last_lr()[0]
                    print(f"  Epoch [{epoch+1}/{epochs}] Step [{step+1:03d}/{len(train_loader):03d}] | Loss: {loss.item()*grad_accum:.4f} | LR: {curr_lr:.2e}")

        avg_loss = epoch_loss / len(train_loader)
        print(f"[OK] Epoch {epoch+1} Complete | Average Loss: {avg_loss:.4f}\n")

    print(f"[*] Saving Fine-Tuned LoRA Adapter Weights to: {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print("[OK] LoRA Adapter saved successfully!\n")

    del model, processor, optimizer, scheduler
    torch.cuda.empty_cache()

# ==============================================================================
# 3. BENCHMARK & EVALUATION FUNCTION
# ==============================================================================
def parse_predicted_action(text: str) -> Tuple[float, float]:
    """Extract [linear_x, angular_z] from model output <action>[v, w]</action>"""
    try:
        match = re.search(r"<action>\s*\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]\s*</action>", text, re.IGNORECASE)
        if match:
            return float(match.group(1)), float(match.group(2))
        
        # Fallback: general bracket matching
        match_alt = re.search(r"\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]", text)
        if match_alt:
            return float(match_alt.group(1)), float(match_alt.group(2))
    except Exception:
        pass
    return 0.0, 0.0

def evaluate_vla():
    print("=" * 80)
    print("[*] QUANTITATIVE BENCHMARK EVALUATION ON VALIDATION SET")
    print("=" * 80)

    processor = AutoProcessor.from_pretrained(OUTPUT_DIR, trust_remote_code=True)
    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)
    model.eval()

    with open(VAL_FILE, "r", encoding="utf-8") as f:
        val_samples = [json.loads(line.strip()) for line in f if line.strip()]

    print(f"[*] Benchmarking {len(val_samples)} Validation Frames on GPU...\n")
    linear_errs, angular_errs = [], []

    for idx, s in enumerate(val_samples):
        img_path = PROJECT_ROOT / s["image"]
        image = Image.open(img_path).convert("RGB")
        
        gt_action = s.get("ground_truth_action", [0.0, 0.0])
        gt_vx, gt_wz = float(gt_action[0]), float(gt_action[1])
        b_class = s.get("behavior_class", "UNKNOWN")

        user_txt = ""
        for msg in s.get("conversations", []):
            role = msg.get("from") or msg.get("role")
            if role in ["user", "human"]:
                user_txt = (msg.get("value") or msg.get("content")).replace("<image>\n", "").replace("<image>", "")

        msgs = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
        txt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[txt], images=[image], return_tensors="pt").to("cuda")

        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=96, do_sample=False)
            out_txt = processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        pred_vx, pred_wz = parse_predicted_action(out_txt)
        err_v = abs(pred_vx - gt_vx)
        err_w = abs(pred_wz - gt_wz)
        linear_errs.append(err_v)
        angular_errs.append(err_w)

        if (idx + 1) % 15 == 0 or idx == len(val_samples) - 1:
            print(f"  [{idx+1:02d}/{len(val_samples):02d}] Class: {b_class:20s} | GT: [{gt_vx:+.2f}, {gt_wz:+.2f}] | PRED: [{pred_vx:+.2f}, {pred_wz:+.2f}] | Err_v: {err_v:.3f} m/s")

    mae_v = sum(linear_errs) / len(linear_errs)
    mae_w = sum(angular_errs) / len(angular_errs)

    print("\n" + "=" * 80)
    print("🏆 FINAL SCIENTIFIC VALIDATION BENCHMARK RESULTS:")
    print(f"  • Total Validation Samples:          {len(val_samples)} frames")
    print(f"  • Linear Velocity MAE  (MAE_v):       {mae_v:.4f} m/s")
    print(f"  • Angular Velocity MAE (MAE_w):       {mae_w:.4f} rad/s")
    print("=" * 80)

if __name__ == "__main__":
    train_vla(epochs=3, batch_size=1, grad_accum=4, lr=2e-4)
    evaluate_vla()
    print("\n[SUCCESS] Entire VLA Fine-Tuning & Evaluation Pipeline Finished Successfully!")
