import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"

print("="*70)
print("PROBE: eval_results_v3.json FULL SCHEMA")
print("="*70)
with open(os.path.join(BASE, "eval_results_v3.json"), "r", encoding="utf-8") as f:
    ev = json.load(f)

print("Top-level keys:", list(ev.keys()))
print("\nz_bl (zero baseline):", ev.get("z_bl"))
print("m_bl (mean baseline):", ev.get("m_bl"))
print("mae_v:", ev.get("mae_v"))
print("mae_w:", ev.get("mae_w"))

p = ev.get("p", [])
print(f"\n'p' array length: {len(p)}")
print("First 3 entries of 'p' (FULL structure):")
for i, item in enumerate(p[:3]):
    print(f"  [{i}] type={type(item).__name__} -> {item}")

if len(p) > 0 and isinstance(p[0], dict):
    print("\nAll keys found across all 69 entries of 'p':")
    all_keys = set()
    for item in p:
        all_keys.update(item.keys())
    print(" ", sorted(all_keys))
elif len(p) > 0 and isinstance(p[0], list):
    print(f"\nEach entry of 'p' is a list of length {len(p[0])}")

print("\n" + "="*70)
print("PROBE: training_history.json FULL SCHEMA")
print("="*70)
hp = os.path.join(BASE, "models", "qwen3_vla_mir100_lora_v2", "training_history.json")
with open(hp, "r", encoding="utf-8") as f:
    hist = json.load(f)

def describe(node, prefix="", depth=0):
    if depth > 3: return
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                print(f"{prefix}{k}: {type(v).__name__}(len={len(v)})")
                describe(v, prefix + "  ", depth+1)
            else:
                print(f"{prefix}{k}: {v}")
    elif isinstance(node, list) and node:
        print(f"{prefix}[0] sample: {node[0]}")

describe(hist)

print("\n" + "="*70)
print("SEARCH: any per-epoch CANARY / hard-sample prediction logs anywhere?")
print("="*70)
import glob
candidates = glob.glob(os.path.join(BASE, "**", "*canary*"), recursive=True) + \
             glob.glob(os.path.join(BASE, "**", "*.json"), recursive=True)
canary_hits = [c for c in set(candidates) if "canary" in c.lower()]
print("Files with 'canary' in name:", canary_hits if canary_hits else "NONE FOUND")

# Check if training_history.json itself contains anything sample-level
def search_for_canary_keys(node, path=""):
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            if "canary" in k.lower() or "sample" in k.lower() or "hard" in k.lower():
                hits.append(f"{path}.{k}")
            hits += search_for_canary_keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, item in enumerate(node[:2]):
            hits += search_for_canary_keys(item, f"{path}[{i}]")
    return hits

hits = search_for_canary_keys(hist)
print("Keys resembling canary/sample-level logs inside training_history.json:", hits if hits else "NONE FOUND")
