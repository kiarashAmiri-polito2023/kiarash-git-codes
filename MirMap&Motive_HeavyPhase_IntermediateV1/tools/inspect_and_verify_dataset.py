import os
import sys
import json
import shutil
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path.cwd()
DATASET_DIR = PROJECT_ROOT / "dataset"
TRAIN_JSONL = DATASET_DIR / "train.jsonl"
VAL_JSONL = DATASET_DIR / "val.jsonl"

def get_desktop_dir():
    home = Path.home()
    desktop = home / "Desktop"
    return desktop if desktop.exists() else PROJECT_ROOT / "visual_inspections"

def inspect_jsonl(file_path, output_dir, max_samples=3):
    if not file_path.exists():
        raise FileNotFoundError(f"Missing dataset file: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    classes = {}
    valid_imgs = 0
    step = max(1, len(lines) // max_samples)
    
    for idx, line in enumerate(lines):
        rec = json.loads(line)
        img_path = PROJECT_ROOT / rec.get("image", "")
        if img_path.exists():
            valid_imgs += 1
            if idx % step == 0 and len(classes.get("exported", [])) < max_samples:
                classes.setdefault("exported", []).append(True)
                dest = output_dir / f"{file_path.stem}_sample_{idx:03d}.png"
                shutil.copy(img_path, dest)
        meta = rec.get("metadata", {})
        cls_name = meta.get("behavior_class", "UNKNOWN")
        classes[cls_name] = classes.get(cls_name, 0) + 1
        
    return len(lines), valid_imgs, classes

desktop_path = get_desktop_dir() / "vla_bev_visual_check"
desktop_path.mkdir(parents=True, exist_ok=True)
print(f"📁 Exporting visual confirmation samples to: {desktop_path}")

for p in [TRAIN_JSONL, VAL_JSONL]:
    if p.exists():
        tot, valids, cls_dict = inspect_jsonl(p, desktop_path)
        print(f"✅ {p.name}: {valids}/{tot} images intact. Class distribution: {cls_dict}")
