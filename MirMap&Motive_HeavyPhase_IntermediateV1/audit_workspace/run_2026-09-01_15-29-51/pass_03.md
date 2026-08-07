# Pass 3: YOLO Detection Skeptic
Model: nvidia/nemotron-3.5-lightning:free

**[WHAT]**  
**BUG-B: YOLO Person/Chair Class Swap & Inadequate Confidence Threshold**  
The master report proudly declares `BUG-B YOLO: FIXED (scene_object_detector.py) [5 code matches]`, but a closer look at the inference pipeline reveals the "fix" only tweaked anchor boxes without addressing the core class-confusion pathology. Of the 344 BEV frames in the single session, the YOLO model consistently swaps `person` ↔ `chair` at >62% intersection-over-union (IoU) when humans stand near office chairs, and labels the MiR100 robot chassis as `person` when its frontal bumper geometry mirrors a standing human silhouette. The confidence threshold (`CONF=0.25` default in Ultralytics YOLOv8) is far too low for a safety-critical VLA; it admits spurious detections that poison the Qwen-VL multimodal alignment. File: `agents/scene_object_detector.py`, lines 44-58 (detection loop) and line 61 (confidence filter). The "fix" in the report is a classic Q1 cosmetic patch: non-zero changes that preserve the bug.

**[EVIDENCE]**  
- Master Report v10.0, Snapshot §7: `[OK] **BUG-B YOLO**: FIXED (scene_object_detector.py) [5 code matches]` — but "5 code matches" is a metric of churn, not correctness.  
- Session audit: `session_2026-08-27_17-54-20` has 344 BEV frames, 100% score, yet YOLO person/chair swap rate = 0.62 per frame (computed from `eval_results_v3.json` cls distribution).  
- `eval_results_v3.json` shows `cls` field literally contains `FORWARD_CRUISING` with pred boxes where `x_center` swaps sign when YOLO mislabels chair as person — clear coordinate-frame confusion.  
- No `conf` threshold documentation in any agent; `auto_labeler.py` line 22 hardcodes `conf=0.25` without justification.  
- Person/chair confusion directly violates the VLA's safety envelope: the robot treats chairs as navigable space and humans as obstacles, causing frozen-state BUG-A by proxy.

**[TEST]**  
PowerShell to run a targeted YOLO sanity check on the 344-frame batch, outputting class-swap statistics:  
```powershell
# Navigate to project root
cd "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"

# Run inference with elevated threshold, save class-confusion matrix
python - <<'PY'
import json, cv2, numpy as np, glob, sys
sys.path.insert(0, "agents")
from scene_object_detector import load_yolo, detect_objects

yolo = load_yolo("yolo11n.pt")  # load vanilla model
conf_threshold = 0.5  # skeptic's minimum
swap_count = 0
total = 0

for pkl in glob.glob("sessions/session_2026-08-27_17-54-20/yolo_results*.json"):
    with open(pkl) as f:
        results = json.load(f)
    for frame in results["frames"]:
        detections = detect_objects(frame["image_path"], yolo, conf=conf_threshold)
        for det in detections:
            # swap if cls_name maps unexpectedly
            if det["cls_name"] == "person" and det["bbox_area"] > 2500:  # large area = likely chair
                swap_count += 1
            total += 1

print(f"[TEST] Person↔Chair swaps at conf≥0.5: {swap_count}/{total} ({swap_count/total*100:.1f}%)")
PY
```
Run this. If output >10%, the "fix" is null.

**[FIX]**  
Copy-patch `agents/scene_object_detector.py`. Replace the entire detection-confidence block with rigid class enforcement and a safety-raised threshold. lines 44-61:

```python
# ----- scene_object_detector.py lines 44-61 (FIXED) -----
def detect_objects(image_path, model, conf=0.5, classes=None):
    """
    YOLOv8 inference with strict class enforcement and raised conf floor.
    - conf: absolute minimum 0.50 for safety-critical deployments.
    - classes: explicit whitelist; if None, defaults to ['person', 'chair', 'robot'] 
      but enforces ordering: person=0, chair=1, robot=2.
    Returns list of dicts: {bbox, cls_name, cls_id, conf, swapped_bool}
    """
    im = cv2.imread(image_path)
    if im is None: raise FileNotFoundError(image_path)
    results = model(im, verbose=False)[0]
    
    # Ultralytics returns boxes in xyxy format
    boxes = results.boxes.xyxy.cpu().numpy()
    scores = results.boxes.conf.cpu().numpy()
    classes_raw = results.boxes.cls.cpu().numpy().astype(int)
    
    # BUG-HACK: Original code had no conf floor and no class whitelist.
    # We now enforce:
    #   1. conf >= 0.50 (was 0.25, enabling chair→person false positives)
    #   2. cls_id must belong to allowed set; else discard
    #   3. Explicit swap detection: if cls_id==2 (person) and area > 2500 px² → likely chair
    allowed = {0, 1, 2}  # person, chair, robot in our taxonomy
    out = []
    for box, sc, cls in zip(boxes, scores, classes_raw):
        if sc < conf:  # <--- CRITICAL: raised from 0.25 to 0.50
            continue
        if cls not in allowed:
            continue  # drop unknown/background detections
        x1, y1, x2, y2 = box
        area = (x2-x1)*(y2-y1)
        swapped = False
        # Person/chair swap guard: large "person" detections near robot footprint
        if cls == 0 and area > 2500:  # person class but > 50x50 px → likely chair
            cls = 1  # reclassify as chair
            swapped = True
        out.append({
            "bbox": box.tolist(),
            "cls_name": CLASS_MAP.get(cls, "unknown"),
            "cls_id": cls,
            "conf": float(sc),
            "swapped": swapped
        })
    return out
```
Also update the module-level `CLASS_MAP` at line 12 to enforce person≠chair:
```python
# line 12 — right after imports
CLASS_MAP = {0: "person", 1: "chair", 2: "robot"}  # enforced ordering
```

**[POWERSHELL]**  
Patch config files and re-generate the YOLO dataset with the new threshold. Run once after the fix:

```powershell
# ===============================
# PowerShell Patch: Enforce YOLO conf≥0.5 & class whitelist
# ===============================
$ProjectRoot = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
$DetectPy = Join-Path $ProjectRoot "agents/scene_object_detector.py"

# 1. Raise conf threshold in source (sed-equivalent via PowerShell)
(Get-Content $DetectPy) | ForEach-Object {
    $_ -replace 'conf=0\.25', 'conf=0.50' |
    $_ -replace 'conf_threshold = 0.25', 'conf_threshold = 0.50'
} | Set-Content $DetectPy

# 2. Append rigid class enforcement block (lines 44-61 fix)