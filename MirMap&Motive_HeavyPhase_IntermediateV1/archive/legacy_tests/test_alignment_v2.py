import sys, json
from pathlib import Path
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image
from transformers import AutoProcessor

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROJECT_ROOT = Path.cwd()

processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
tok = processor.tokenizer

records = []
with open(PROJECT_ROOT / "dataset" / "train.jsonl", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        records.append(json.loads(line))

print("=" * 70)
for i, rec in enumerate(records):
    image = Image.open(PROJECT_ROOT / rec["image"]).convert("RGB")
    user_txt, asst_txt = "", ""
    for msg in rec["conversations"]:
        if msg.get("from") in ("user", "human"):
            user_txt = msg["value"].replace("<image>\n", "").replace("<image>", "")
        elif msg.get("from") in ("assistant", "gpt"):
            asst_txt = msg["value"]

    user_msgs = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": user_txt}]}]
    full_msgs = user_msgs + [{"role": "assistant", "content": [{"type": "text", "text": asst_txt}]}]

    prefix_text = processor.apply_chat_template(user_msgs, tokenize=False, add_generation_prompt=True)
    full_text = processor.apply_chat_template(full_msgs, tokenize=False, add_generation_prompt=False)

    pref = processor(text=[prefix_text], images=[image], return_tensors="pt")
    full = processor(text=[full_text], images=[image], return_tensors="pt")

    print(f"Sample {i+1}:")
    print("  processor keys:", sorted(full.keys()))
    prefix_ids = pref["input_ids"][0].tolist()
    full_ids = full["input_ids"][0].tolist()
    plen = len(prefix_ids)
    aligned = full_ids[:plen] == prefix_ids
    print(f"  prefix_len={plen} full_len={len(full_ids)} alignment={'OK' if aligned else 'FAIL'}")
    if aligned:
        sup = tok.decode(full_ids[plen:], skip_special_tokens=True)
        print(f"  supervised={len(full_ids)-plen} tokens ({100*(len(full_ids)-plen)/len(full_ids):.1f}%)")
        print(f"  supervised text: {sup[:110]!r}")
    else:
        for j in range(min(plen, len(full_ids))):
            if full_ids[j] != prefix_ids[j]:
                print(f"  DIVERGE at {j}: full={tok.decode(full_ids[j:j+5])!r} vs prefix={tok.decode(prefix_ids[j:j+5])!r}")
                break
    print("-" * 70)
print("[DONE]")
