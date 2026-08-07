"""
Multi-Session VLA Dataset Builder (Bug-fixed v2.0)
Author: Kiarash Amiri (PoliTo / DIGEP)
Aggregates formatted multimodal Qwen-VL datasets across sessions,
preserves behavior class labels, and generates deterministic 80/20 train/val splits.
"""

import os
import sys
import json
import random
from pathlib import Path
from collections import Counter

ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
SESSIONS_DIR = ROOT / "sessions"
OUTPUT_DIR = ROOT / "dataset"

def build_dataset(split_ratio=0.8, seed=42):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_samples = []
    session_counts = {}

    for s_dir in sorted(SESSIONS_DIR.glob("session_*")):
        qwen_file = s_dir / "qwen_vla_dataset.jsonl"
        if qwen_file.exists():
            count = 0
            with open(qwen_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        all_samples.append(record)
                        count += 1
            if count > 0:
                session_counts[s_dir.name] = count

    if not all_samples:
        print("[FAIL] No Qwen VLA dataset records found across sessions.")
        return False

    print(f"[INFO] Total multimodal samples loaded: {len(all_samples)}")

    random.seed(seed)
    shuffled = list(all_samples)
    random.shuffle(shuffled)

    split_idx = int(len(shuffled) * split_ratio)
    train_samples = shuffled[:split_idx]
    val_samples = shuffled[split_idx:]

    train_path = OUTPUT_DIR / "train.jsonl"
    val_path = OUTPUT_DIR / "val.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for s in train_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for s in val_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    total_dist = Counter(s.get("behavior_class", "UNKNOWN") for s in all_samples)
    train_dist = Counter(s.get("behavior_class", "UNKNOWN") for s in train_samples)
    val_dist = Counter(s.get("behavior_class", "UNKNOWN") for s in val_samples)

    stats = {
        "dataset_name": "MiR100_VLA_MultiModal_PoliTo",
        "generated_by": "vla_dataset_builder.py v2.0",
        "operator": "Kiarash Amiri",
        "supervisor": "Prof. Dario Antonelli",
        "total_samples": len(all_samples),
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "split_ratio": split_ratio,
        "seed": seed,
        "sessions_included": list(session_counts.keys()),
        "samples_per_session": session_counts,
        "behavior_distribution_total": dict(total_dist),
        "behavior_distribution_train": dict(train_dist),
        "behavior_distribution_val": dict(val_dist),
        "files": {
            "train": "train.jsonl",
            "val": "val.jsonl"
        }
    }

    stats_path = OUTPUT_DIR / "dataset_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"[OK] Train split: {len(train_samples)} samples -> {train_path}")
    print(f"[OK] Val split: {len(val_samples)} samples -> {val_path}")
    print(f"[OK] Behavior Dist: {dict(total_dist)}")
    return True

if __name__ == "__main__":
    build_dataset()
