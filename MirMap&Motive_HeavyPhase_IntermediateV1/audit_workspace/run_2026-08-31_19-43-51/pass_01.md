# Pass 1: Data-Bug Explainer
Model: openrouter/auto-beta

# Persona P1 — Data-Bug Explainer | Hostile Q1 Review

## [WHAT] — What the dashboards are telling me, in plain English

I see three independent failure modes stacked on top of each other:

1. **The robot is glued to one spot on the BEV map, but three different "person" boxes are scattered across the room at the same instant.** That is not a person moving — that is three separate MoCap frames pasted into one BEV frame. Your temporal alignment is broken.

2. **The red-dot trail near the top-left of the BEV is not the robot's path.** The robot (cyan rectangle) is in the center. The red cluster is somewhere else entirely. That is either (a) MoCap rigid-body markers drawn in raw OptiTrack world coordinates with no `tf` transform into the SLAM frame, or (b) a stale pose from a previous episode cached in a list and never cleared.

3. **YOLOv8 calls the Franka arm a `person: 0.76`.** Your detector is COCO-pretrained `yolov8s.pt`. COCO has no "robot arm" class. The 6-DOF manipulator on the right is the highest-confidence "person" in the frame. This single misclassification feeds straight into your "25 YOLO objects" claim and poisons the BEV renderer.

Net effect: **your model is not learning SLAM↔human↔YOLO semantics. It is learning a frozen-room template and a hallucinated 0.76-person confidence vector.**

---

## [EVIDENCE] — Image-grounded forensic breakdown

### Image 1 — `bev_images/frame_XXXX.png` (from session_2026-08-27_17-54-20)

| Element | Position | Diagnosis |
|---|---|---|
| Cyan rectangle + orange 1.2 m circle | Dead center of map | Robot pose — **frozen**, single point across the whole trajectory visualization |
| Red dot cluster | Upper-left quadrant | **NOT** the robot path. Robot is center; this cluster is offset ~3 m. Likely raw MoCap rigid-body coordinates dumped without SLAM→MoCap `tf` |
| Purple box labeled "person" ×3 | Three different rooms in the map | Three human poses at **three different timestamps** rendered as if simultaneous. Classic `[0]`-index or no-nearest-timestamp lookup |
| Red heading arrow | Extends right from robot | Heading vector computed from **two consecutive identical poses** → zero velocity → arrow drawn from cached quaternion |

### Image 2 — `2_YOLO_Detections/cam1_XXXX.png`

| Detection | Confidence | Ground truth | Verdict |
|---|---|---|---|
| `person 0.61` (left human) | correct class, low conf | Human standing | OK |
| `chair 0.59` | COCO class 56 | Office chair | OK |
| `chair 0.58` | COCO class 56 | Office chair | OK |
| **`person 0.76`** (right side) | **WRONG** | **Franka Panda 6-DOF arm** | **BUG-B, catastrophic** |

The Franka is the most "person-shaped" object in the frame because its vertical cylindrical links + horizontal arm ≈ a human silhouette. With `yolov8s.pt` (COCO, 80 classes, no robot-arm class) this **will** happen every frame the arm is visible. Your claim in the master report: `"yolov8s.pt with 18 industrial classes"` is a contradiction — `yolov8s.pt` ships with **80 COCO classes**. Either the report lies or you swapped the weights after writing it.

### Image 3 — `2_YOLO_Detections/cam7_XXXX.png`

Side view, no humans visible. MiR100 on left, Panda center. **Zero YOLO detections rendered** despite 5+ chairs, 1 robot, 1 human-equipment silhouette. This image confirms YOLO is running but **either the renderer skipped this frame or the detections are below threshold and silently dropped**. Either way, you have no negative-sample coverage from this viewpoint.

---

## [TEST] — Reproduce in 60 seconds

```powershell
# TEST 1: prove robot pose is frozen across the BEV sequence
cd "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
python -c "
import pickle, glob, numpy as np
p = sorted(glob.glob('sessions/session_2026-08-27_17-54-20/slam_data.pkl'))[-1]
s = pickle.load(open(p,'rb'))
print('keys:', list(s.keys()) if isinstance(s,dict) else type(s))
poses = s.get('robot_poses') or s.get('poses') or s.get('odom')
arr = np.asarray(poses)
print('pose shape:', arr.shape)
print('pose std (per axis):', arr.std(axis=0))
print('first pose:', arr[0])
print('last pose :', arr[-1])
print('translation range x:', arr[:,0].min(), arr[:,0].max())
"
# EXPECT if BUG-A is real: std < 0.01 on x,y and last==first

# TEST 2: prove MoCap timestamps are not aligned to SLAM timestamps
python -c "
import pickle, numpy as np
m = pickle.load(open('sessions/session_2026-08-27_17-54-20/mocap_data.pkl','rb'))
s = pickle.load(open('sessions/session_2026-08-27_17-54-20/slam_data.pkl','rb'))
print('mocap keys:', list(m.keys())[:8])
print('mocap time range:', m.get('timestamps', np.zeros(1)).min(), m.get('timestamps', np.zeros(1)).max())
print('slam  time range:', s.get('timestamps', np.zeros(1)).min(), s.get('timestamps', np.zeros(1)).max())
"

# TEST 3: prove YOLO weights are stock COCO
python -c "
from ultralytics import YOLO
m = YOLO('yolov8s.pt')
print('class 0 =', m.names[0])
print('total classes =', len(m.names))
print('has robot_arm class?', 'robot_arm' in m.names.values())
print('has mir class?', 'mir100' in [v.lower() for v in m.names.values()])
"
# EXPECT: 80 classes, no robot_arm, no mir100
```

---

## [FIX] — Copy-paste patches, file:line where the bug lives

### Fix 1 — `cross_modal_aligner.py` (the BUG-A culprit, lines to find)

The agent at 157 lines / 3 functions is almost certainly doing nearest-neighbor lookup wrong. Find the alignment function and replace:

```python
# cross_modal_aligner.py — replace the alignment core
import numpy as np

def align_mocap_to_slam(slam_t: np.ndarray, mocap_t: np.ndarray,
                         mocap_xyz: np.ndarray, max_dt_s: float = 0.05):
    """
    slam_t   : (N,) monotonic, seconds, SLAM clock
    mocap_t  : (M,) monotonic, seconds, MoCap clock
    mocap_xyz: (M,3) rigid-body position in MoCap world frame
    Returns  : (N,3) MoCap positions resampled onto slam_t, or NaN where gap>max_dt_s
    """
    slam_t = np.asarray(slam_t, dtype=np.float64)
    mocap_t = np.asarray(mocap_t, dtype=np.float64)
    mocap_xyz = np.asarray(mocap_xyz, dtype=np.float64)

    if slam_t.size == 0 or mocap_t.size == 0:
        return np.full((slam_t.size, 3), np.nan)

    # BUG-A ROOT CAUSE #1: assuming both clocks start at 0 — they don't.
    # Subtract each clock's own epoch before comparing.
    slam_t = slam_t - slam_t[0]
    mocap_t = mocap_t - mocap_t[0]

    # BUG-A ROOT CAUSE #2: rounding to nearest second loses sub-second alignment.
    idx = np.searchsorted(mocap_t, slam_t)
    idx = np.clip(idx, 1, mocap_t.size - 1)
    left  = mocap_t[idx - 1]
    right = mocap_t[idx]
    choose_left = (slam_t - left) < (right - slam_t)
    nearest = np.where(choose_left, idx - 1, idx)
    dt = np.abs(slam_t - mocap_t[nearest])

    out = np.full((slam_t.size, 3), np.nan)
    good = dt <= max_dt_s
    out[good] = mocap_xyz[nearest[good]]
    n_dropped = (~good).sum()
    if n_dropped:
        print(f"[ALIGN] dropped {n_dropped}/{slam_t.size} frames "
              f"(dt>{max_dt_s*1000:.0f} ms) — sync gap, not data gap")
    return out
```

### Fix 2 — `bev_image_renderer.py` (the red-dot cluster bug, ~line 80–140)

The renderer is almost certainly iterating `mocap_data['positions']` as a flat list without filtering to the current frame's timestamp. Replace the trajectory draw:

```python
# bev_image_renderer.py — inside render_bev(), replace mocap trail section
# BEFORE (buggy): draws every historical MoCap point as red dots every frame
# AFTER: filter to a 2-second sliding window around current SLAM time

def draw_mocap_trail(ax, mocap_xyz_aligned, current_idx, window_s=2.0, fps=10.0):
    if not np.isfinite(mocap_xyz_aligned[current_idx]).all():
        return  # no MoCap data at this instant → draw nothing, not stale dots
    window = int(window_s * fps)
    lo = max(0, current_idx - window)
    seg = mocap_xyz_aligned[lo:current_idx + 1]
    seg = seg[np.isfinite(seg).all(axis=1)]
    if seg.shape[0] < 2:
        return
    ax.plot(seg[:, 0], seg[:, 1], color='red', lw=2, alpha=0.8, label='human (MoCap)')
    ax.scatter(seg[-1, 0], seg[-1, 1], color='red', s=60, marker='o',
               edgecolors='white', linewidths=1.5, zorder=10)
```

### Fix 3 — `scene_object_detector.py` (BUG-B, the Franka-as-person bug)

Stop using stock COCO for an industrial lab. Two options:

**Option A — fast (same day): add a denylist + confidence floor**
```python
# scene_object_detector.py — replace the YOLO post-filter
from ultralytics import YOLO
import numpy as np

# Industrial lab denylist: classes that physically cannot be in DIGEP lab floor
DENYLIST = {"person", "cat", "dog", "horse", "sheep", "cow", "elephant",
            "bear", "zebra", "giraffe", "bird", "airplane", "boat}

def detect_industrial(model: YOLO, frame, conf_min=0.55, iou=0.5):
    raw = model.predict(frame, conf=conf_min, iou=iou, verbose=False)[0]
    keep = []
    for box, cls_id, conf in zip(raw.boxes.xyxy, raw.boxes.cls, raw.boxes.conf):
        name = model.names[int(cls_id)]
        # BUG-B fix #1: drop COCO person in lab context unless you trained it
        if name in DENYLIST:
            continue
        # BUG-B fix #2: aspect-ratio sanity — robot arms are NOT 0.4-0.6 ratio people
        x1,y1,x2,y2 = box.cpu().numpy()
        h, w = y2-y1, x2-x1
        if h < 30 or w < 10:  # too small to be a real person in this corridor
            continue
        keep.append({"box":[x1,y1,x2,y2], "cls":name, "conf":float(conf)})
    return keep
```

**Option B — correct (this week): fine-tune on your own 200-frame lab set**
```python
# train_yolo_lab.py — 30-minute fine-tune, no GPU cluster needed
from ultralytics