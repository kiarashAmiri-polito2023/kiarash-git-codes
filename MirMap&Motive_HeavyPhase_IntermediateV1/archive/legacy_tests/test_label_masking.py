import sys, json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image
from transformers import AutoProcessor

PROJECT_ROOT = Path.cwd()
TRAIN_FILE = PROJECT_ROOT / "dataset" / "train.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen3_vla_mir100_lora"

processor = AutoProcessor.from_pretrained(OUTPUT_DIR, trust_remote_code=True)
tokenizer = processor.tokenizer
im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
print("im_end token id:", im_end_id)
print("=" * 70)

# --- Part A: Verify masking alignment on 3 samples ---
records = []
with open(TRAIN_FILE, encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        records.append(json.loads(line))

for i, rec in enumerate(records):
    image = Image.open(PROJECT_ROOT / rec["image"]).convert("RGB")
    user_txt, asst_txt = "", ""
    for msg in rec["conversations"]:
        if msg.get("from") in ["user", "human"]:
            user_txt = msg["value"].replace("<image>\n", "").replace("<image>", "")
        elif msg.get("from") in ["assistant", "gpt"]:
            asst_txt = msg["value"]

    # Prefix = user turn + assistant generation start (WITH image)
    msgs_user = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
    prefix_text = processor.apply_chat_template(msgs_user, tokenize=False, add_generation_prompt=True)
    prefix_inputs = processor(text=[prefix_text], images=[image], return_tensors="pt")
    prefix_len = prefix_inputs["input_ids"].shape[1]

    # Suffix = assistant answer + im_end (text only)
    suffix_ids = tokenizer(asst_txt + "<|im_end|>", add_special_tokens=False, return_tensors="pt")["input_ids"]
    suffix_len = suffix_ids.shape[1]

    sup_decoded = tokenizer.decode(suffix_ids[0], skip_special_tokens=False)
    tail = tokenizer.decode(prefix_inputs["input_ids"][0][-10:], skip_special_tokens=False)

    print(f"Sample {i+1}:")
    print(f"  prefix tokens (will be MASKED, -100): {prefix_len}")
    print(f"  supervised tokens (real learning):     {suffix_len}")
    print(f"  supervision ratio: {suffix_len/(prefix_len+suffix_len)*100:.1f}%")
    print(f"  prefix tail: ...{tail!r}")
    print(f"  supervised text: {sup_decoded[:150]!r}")
    print(f"  GT action: {rec.get('ground_truth_action')} | class: {rec.get('behavior_class')}")
    print("-" * 70)

# --- Part B: Verify action diversity across ALL train records ---
all_recs = []
with open(TRAIN_FILE, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            all_recs.append(json.loads(line))

moving = sum(1 for r in all_recs if abs(float(r.get("ground_truth_action", [0,0])[0])) > 0.01)
rotating = sum(1 for r in all_recs if abs(float(r.get("ground_truth_action", [0,0])[1])) > 0.02)
vs = [float(r["ground_truth_action"][0]) for r in all_recs if "ground_truth_action" in r]
ws = [float(r["ground_truth_action"][1]) for r in all_recs if "ground_truth_action" in r]
print("ACTION DIVERSITY ACROSS", len(all_recs), "TRAIN SAMPLES:")
print(f"  moving (|v|>0.01): {moving} ({moving/len(all_recs)*100:.1f}%)")
print(f"  rotating (|w|>0.02): {rotating} ({rotating/len(all_recs)*100:.1f}%)")
print(f"  v range: [{min(vs):+.3f}, {max(vs):+.3f}] | w range: [{min(ws):+.3f}, {max(ws):+.3f}]")
print("=" * 70)
print("[DONE] Send this output back for the final masked-training script.")
