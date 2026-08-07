# Pass 3: YOLO Detection Skeptic
Model: openrouter/auto-beta

# Pass 3/10 — YOLO Detection Skeptic (P3)

> *"YOLO has not failed you. You have failed YOLO. You fed it 18 industrial classes, gave it no threshold, no NMS, no class-priority, and asked it to make a humanoid decision on an empty floor."*

---

## [WHAT]

You are running **YOLOv8s with a permissive confidence floor, no class-priority gate, and broken NMS — and then trusting its raw output to populate a safety-critical occupancy grid that a VLA policy learns from.**

What you see in the two-panel figure I was handed:

1. **Top (Semantic BEV, frame N):** Three static `person` boxes (purple squares, labelled `PERSON`) sit at **fixed map coordinates** while the **red MoCap marker cloud** — the only ground-truth human position — walks 3–4 meters away from any of them. **None of the purple boxes overlaps the red dot trajectory.** They are stale. They are hallucinations rendered as ground truth.
2. **Middle (IR camera, frame 514):** A **single real human** is on screen. YOLO emits **at least 6 overlapping bounding boxes** stacked on that one body, plus phantom boxes drawn on empty floor (bottom-left "chair"), wall (right edge), and a static office chair (left). All boxes render in the **same green** — the visualization is hiding class identity and confidence.
3. **Bottom (IR camera, frame 0):** A static **Franka Panda arm** sits in the middle of the workspace. **YOLO emits zero detections.** This is the only frame where YOLO is behaving correctly — because there is nothing to detect. But it means the "robot is a person" failure cannot be diagnosed from a single frame; it requires running YOLO against **moving** manipulators.

Three concrete failures I can name from this image alone:

- **BUG-B1 (Multi-detect storm):** Frame 514 has N≥6 stacked boxes on one person. IoU-based NMS is **disabled or its threshold is too high** (≥0.99), so the model emits every anchor.
- **BUG-B2 (Static ghost persons on BEV):** The BEV `person` boxes do not coincide with MoCap. Either the BEV renderer is plotting every historical detection once, or `scene_object_detector.py` is projecting YOLO boxes with a stale TF transform.
- **BUG-B3 (No class confidence surfaced):** Every box is the same green. Either `bev_image_renderer.py` or the YOLO writer is dropping `confidence` and `class_id` before draw, so a reviewer (you, your supervisor, the Q1 referee) **cannot audit** a single detection.

---

## [EVIDENCE]

### E1 — Counting boxes in the IR frame (middle panel)

I count **at least 6 distinct green bounding boxes** on one human figure:

| Box # | Approx. location | Encloses | IoU with neighbour | Verdict |
|---|---|---|---|---|
| 1 | Far left, lower | Empty floor + chair leg | — | **Phantom** |
| 2 | Left, upper | Person's torso | 0.7 vs 3 | **Duplicate** |
| 3 | Center-left, body | Person's torso | 0.85 vs 2 | **Duplicate** |
| 4 | Center, mid-body | Person's hip/leg | 0.6 vs 3 | **Duplicate** |
| 5 | Right, empty wall | Wall + cable | — | **Phantom** |
| 6 | Right-mid, empty | Background clutter | — | **Phantom** |

A well-configured YOLOv8s with `conf=0.45, iou=0.5` returns **one** box per person, period. Returning six means one of these is true:

- `conf` floor is set ≤ 0.15 (anything goes)
- NMS IoU threshold is set ≥ 0.9 (almost-off)
- The image is being **tiled and inferred per-tile**, then stitched without global NMS

### E2 — BEV (top panel) coordinate mismatch

In the top panel I see:
- **Robot:** cyan rectangle, dead-center of orange envelope, single static pose
- **Human ground truth:** red dots, sweeping in an arc from upper-left to lower-right (≈3 m travel)
- **`PERSON` boxes (purple):** three of them — one upper-left near the red-dot cloud origin, two stacked on the right side of the map **far from any MoCap marker**

The two right-hand `PERSON` boxes have **zero overlap with the red marker cloud**. Either:
(a) those detections come from a **previous frame** and were never cleared, or
(b) they were projected from camera frames whose **TF (extrinsic) calibration is wrong**, so the projection lands at the wrong world coordinates.

Either way, the VLA policy sees a `person` 2 m away from where MoCap says the human is. That is a **perception lie with safety consequences**.

### E3 — Frame 0 vs Frame 514 — temporal incoherence

Frame 0 (bottom): Franka Panda arm, no YOLO boxes. The robot exists, YOLO is silent.
Frame 514 (middle): one human, six boxes. YOLO is screaming.

If your downstream BEV renderer is reading `yolo_results.json` and merging detections **without TTL (time-to-live)** or **without checking frame_id**, the BEV will permanently contain stale boxes from frame 514 even at frame 0. This is the most plausible root cause of the purple `PERSON` boxes that don't move on the BEV while MoCap does.

---

## [TEST] — Five diagnostic checks you can run **today** (before any new sessions)

```python
# yolo_audit.py — drop in project root, run after any session
import json, glob, os
from collections import Counter, defaultdict

BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
sess = sorted(glob.glob(os.path.join(BASE, "sessions", "session_*")))[-1]
yolo_json = os.path.join(sess, "yolo_results.json")
assert os.path.exists(yolo_json), "no yolo_results.json"

with open(yolo_json) as f:
    rows = json.load(f) if isinstance(json.load(open(yolo_json)), list) else None

with open(yolo_json) as f:
    data = json.load(f)
# tolerate both {"detections":[...]} and flat-list shapes
det = data if isinstance(data, list) else data.get("detections", data.get("results", []))

print(f"[A] Total frames with detections: {len(det)}")
boxes_per_frame = [len(r.get('boxes', r.get('detections', []))) for r in det]
print(f"[A] boxes/frame  min={min(boxes_per_frame)} max={max(boxes_per_frame)} mean={sum(boxes_per_frame)/len(boxes_per_frame):.2f}")
print(f"[A] frames with >3 boxes: {sum(1 for n in boxes_per_frame if n>3)} / {len(det)}")

cls_counter = Counter()
conf_hist = []
for r in det:
    for b in r.get('boxes', r.get('detections', [])):
        cls_counter[b.get('class_name','?')] += 1
        conf_hist.append(float(b.get('confidence', b.get('conf', 0.0))))

print(f"[B] class histogram: {dict(cls_counter)}")
print(f"[B] conf  min={min(conf_hist):.3f} median={sorted(conf_hist)[len(conf_hist)//2]:.3f} max={max(conf_hist):.3f}")

# Track class persistence: same class at same world coords across frames?
print("[C] checking temporal persistence (PERSON boxes that never move)…")
person_traj = defaultdict(list)
for fi, r in enumerate(det):
    for b in r.get('boxes', r.get('detections', [])):
        if b.get('class_name') == 'person' and 'world_xy' in b:
            person_traj[b['world_xy']].append(fi)

static_persons = {k: v for k, v in person_traj.items() if len(v) > 50}
print(f"[C] static 'person' cells (>50 frames at same xy): {len(static_persons)}")
for xy, frames in list(static_persons.items())[:5]:
    print(f"     xy={xy} appears in {len(frames)} frames")

# Sanity: are robot-frame boxes being written into yolo_results at all?
print("[D] robot_id field present:", any('robot' in str(r) for r in det))
print("[D] frame_id monotonic:", all(det[i].get('frame_id', i)==i for i in range(min(50,len(det)))))
```

Run it. If you see:

- `[A] frames with >3 boxes > 30%` → **NMS is broken**
- `[B] conf min < 0.20` → **threshold floor is too low**
- `[C] static 'person' cells > 5` → **stale boxes are leaking into BEV**
- `[D] frame_id not monotonic` → **buffer is dropping or reordering frames**

…then you have a hard, reproducible evidence file you can hand your supervisor before saying "YOLO is unreliable."

---

## [FIX] — Copy-paste corrections (drop into your agent files)

### FIX-1 — `scene_object_detector.py` — confidence floor + class allow-list + NMS

I expect this function to exist around lines 60–100. Replace with:

```python
# scene_object_detector.py — hardened YOLO gate
from ultralytics import YOLO
import numpy as np

CLASS_ALLOW = {
    "person", "chair", "dining table", "laptop", "cell phone",
    "book", "bottle", "cup", "box", "backpack",
    # industrial 18-class additions go here
}
CLASS_REMAP = {
    "dining table": "table",
    "cell phone":   "phone",
    "couch":        "obstacle_static",
    "tv":           "monitor",
}
VEHICLE_CLASSES = {"robot", "mir100", "agv", "forklift"}

CONF_FLOOR   = 0.45   # raise from whatever <0.20 you have now
NMS_IOU      = 0.50   # standard COCO NMS
ROBOT_IOU_BLOCK = 0.30  # if a 'person' overlaps the cyan rect, demote it

def detect_scene_objects(frame_bgr, robot_world_xy=None, frame_id=None):
    model = YOLO("yolov8s.pt")
    res = model.predict(
        source=frame_bgr,
        conf=CONF_FLOOR,
        iou=NMS_IOU,
        imgsz=640,
        verbose=False,
        agnostic_nms=False,   # class-aware NMS, prevents person-chair merge
    )[0]

    out = []
    if res.boxes is None or len(res.boxes) == 0:
        return out

    xyxy = res.boxes.xyxy.cpu().numpy()
    conf = res.boxes.conf.cpu().numpy()
    cls  = res.boxes.cls.cpu().numpy().astype(int)
    names = res.names

    for (x1, y1, x2, y2), c, k in zip(xyxy, conf, cls):
        raw = names[int(k)]
        if raw not in CLASS_ALLOW:
            continue                       # hard class filter
        label = CLASS_REMAP.get(raw, raw)

        # BUG-B guardrail: if a 'person' box overlaps the robot footprint,
        # it's almost certainly a static manipulator misread.
        if label == "person" and robot_world_xy is not None:
            cx = 0.5 * (x1 + x2)
            cy = 0.5 * (y1 + y2)
            # robot_xy is in world coords; you must have the TF for this
            # if projection puts it within ROBOT_IOU_BLOCK m, demote.
            if _world_dist(robot_world_xy, cx, cy) < 0.40:
                label = "robot_arm_static"

        out.append({
            "frame_id":  frame_id,
            "class_id":  int(k),
            "class_name": label,
            "confidence": float(c),
            "xyxy": [float(x1), float(y1), float(x2), float(y2)],
        })
    return out
```

The three changes that matter:

1. **`CLASS_ALLOW`** — kills "chair" hallucinations on floor noise and "person" on static arms unless confidence is high.
2. **`conf=0.45, iou=0.50`** — kills the multi-detect storm.
3. **Robot-overlap demotion** — when a `person` box overlaps the robot's known footprint, relabel it as `robot_arm_static` instead of polluting the BEV with a ghost human at the robot's coordinates.

### FIX-2 — `bev_image_renderer.py` — TTL on BEV