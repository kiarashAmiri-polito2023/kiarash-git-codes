import os
import sys
import json
import argparse
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig, get_cosine_schedule_with_warmup
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROJECT_ROOT = Path.cwd()
TRAIN_FILE = PROJECT_ROOT / "dataset" / "train.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora"

class VLADataset(Dataset):
    def __init__(self, jsonl_path, processor, max_samples=None):
        self.processor = processor
        self.records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.records.append(json.loads(line.strip()))
                    if max_samples and len(self.records) >= max_samples:
                        break

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        item = self.records[idx]
        img_path = PROJECT_ROOT / item["image"]
        image = Image.open(img_path).convert("RGB")
        
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

def train(args):
    print("=" * 75)
    print(f"🚀 TRAINING QWEN3-VL (Mode: {'DRY RUN' if args.dry_run else 'FULL'})")
    print("=" * 75)
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, quantization_config=bnb_config, device_map="auto", trust_remote_code=True)
    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16, lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)

    max_s = 10 if args.dry_run else None
    dataset = VLADataset(TRAIN_FILE, processor, max_samples=max_s)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    epochs = 1 if args.dry_run else args.epochs
    total_steps = (len(loader) // args.grad_accum) * epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=max(1, int(total_steps*0.05)), num_training_steps=max(1, total_steps))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.train()
    
    global_step = 0
    for epoch in range(epochs):
        epoch_loss = 0.0
        optimizer.zero_grad()
        for step, batch in enumerate(loader):
            batch = {k: v.to("cuda") for k, v in batch.items()}
            out = model(**batch)
            loss = out.loss / args.grad_accum
            loss.backward()
            epoch_loss += loss.item() * args.grad_accum

            if (step + 1) % args.grad_accum == 0 or (step + 1) == len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1
                if global_step % 5 == 0 or args.dry_run:
                    print(f"Epoch [{epoch+1}/{epochs}] Step [{step+1}/{len(loader)}] | Loss: {loss.item()*args.grad_accum:.4f}")

        print(f"✅ Epoch {epoch+1} Complete | Average Loss: {epoch_loss/len(loader):.4f}")

    if not args.dry_run:
        print(f"💾 Saving LoRA Weights to {OUTPUT_DIR}...")
        model.save_pretrained(OUTPUT_DIR)
        processor.save_pretrained(OUTPUT_DIR)
        print("🎉 WEIGHTS SAVED SUCCESSFULLY!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--dry-run", action="store_true")
    train(parser.parse_args())
