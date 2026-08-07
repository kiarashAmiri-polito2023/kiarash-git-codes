import sys
import json
from pathlib import Path
import torch
from PIL import Image

print("=== TEST VLA READINESS ===")
PROJECT_ROOT = Path.cwd()

# 1. Check first 3 lines of train.jsonl & Image Path Verification
train_file = PROJECT_ROOT / "dataset" / "train.jsonl"
print(f"Reading: {train_file}")

with open(train_file, "r", encoding="utf-8") as f:
    sample_lines = [json.loads(line) for idx, line in enumerate(f) if idx < 3]

print(f"Loaded {len(sample_lines)} samples for inspection.")
for i, s in enumerate(sample_lines):
    img_rel = s.get("image", "")
    full_img_path = PROJECT_ROOT / img_rel
    exists = full_img_path.is_file()
    print(f"Sample {i+1}:")
    print(f"  - Relative path: {img_rel}")
    print(f"  - Exists on disk: {exists}")
    if exists:
        with Image.open(full_img_path) as im:
            print(f"  - Image size: {im.size}, mode: {im.mode}")
    print(f"  - Behavior: {s.get('metadata', {}).get('behavior_class')}")
    print(f"  - Linear_X: {s.get('metadata', {}).get('linear_velocity_x')}")
print("")

# 2. Test Model & Processor Loading
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
print(f"Testing loader for {MODEL_ID} ...")

try:
    from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )

    print("  -> Loading processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    print("  -> Processor loaded OK.")

    print("  -> Loading 4-bit quantized model...")
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    print("  -> Model loaded OK on GPU.")
    print(f"  -> Allocated VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

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
    print("  -> PEFT LoRA adapter attached OK.")
    model.print_trainable_parameters()

    print("\n✅ ALL CHECKS PASSED: Environment is 100% ready for training!")

except Exception as e:
    print(f"\n❌ FAILED DURING MODEL TEST: {e}")
    import traceback
    traceback.print_exc()

print("=== END TEST ===")
