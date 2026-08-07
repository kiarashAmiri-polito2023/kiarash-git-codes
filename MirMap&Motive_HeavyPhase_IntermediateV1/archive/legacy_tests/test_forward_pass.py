import sys
import os
import json
from pathlib import Path

# Fix Windows cp1252 console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

print("=== INSPECTING RECORD FORMAT & FORWARD-BACKWARD PASS ===")
PROJECT_ROOT = Path.cwd()
train_file = PROJECT_ROOT / "dataset" / "train.jsonl"

with open(train_file, "r", encoding="utf-8") as f:
    first_record = json.loads(f.readline())

print("\n--- SAMPLE RECORD KEYS ---")
print("Top-level keys:", list(first_record.keys()))
print("\n--- FULL CONVERSATIONS FIELD ---")
print(json.dumps(first_record.get("conversations", []), indent=2, ensure_ascii=False))

if "metadata" in first_record:
    print("\n--- METADATA FIELD ---")
    print(json.dumps(first_record["metadata"], indent=2))

print("\n--- TESTING 1 FORWARD + BACKWARD PASS ON GPU ---")
try:
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from PIL import Image

    MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )
    
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)
    peft_config = LoraConfig(
        r=16, lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)
    model.train()

    # Load 1 sample image & conversation
    img_path = PROJECT_ROOT / first_record["image"]
    image = Image.open(img_path).convert("RGB")
    
    user_txt, asst_txt = "", ""
    for msg in first_record.get("conversations", []):
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

    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    inputs = processor(text=[prompt], images=[image], padding=True, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    inputs["labels"] = inputs["input_ids"].clone()

    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4)
    optimizer.zero_grad()
    
    outputs = model(**inputs)
    loss = outputs.loss
    loss.backward()
    optimizer.step()

    print(f"\nSUCCESS: Single batch step executed flawlessly!")
    print(f"Computed Loss Value: {loss.item():.4f}")
    print(f"Peak VRAM used: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

except Exception as e:
    print(f"\nERROR in forward pass: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETED ===")
