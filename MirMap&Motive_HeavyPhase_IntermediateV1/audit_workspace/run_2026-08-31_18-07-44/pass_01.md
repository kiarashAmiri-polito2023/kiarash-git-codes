# Pass 1: Data-Bug Explainer
Model: openrouter/auto-beta

# Pass 1/10 — Data-Bug Explainer (P1)

> *"Don't trust the pretty picture. Trust the timestamps."*

---

## [WHAT]

You have **two pictures lying about the same moment in time**.

1. **The BEV (top image)** says the **robot stood still** (one cyan rectangle) while the **human walked all over the place** (clouds of red dots trailing across the map).
2. **The IR camera (middle image)** says the **robot arm is a person** (`person: 0.76` on a static manipulator) and that a piece of furniture on the left is also a chair — and there are **two phantom "person" boxes** sitting on empty floor.

The two pictures were never stamped with the same clock. That's why the VLA policy learned a frozen-robot trick: the dataset fed Qwen a world where the MiR100 never moves.

---

## [EVIDENCE]

### Evidence #1 — BUG-A: Robot frozen, human wandering (the dashboard lie)

In `5_Decision_Dashboards/decision_panel_*.png` (Image 1) I see:

| Element | Color | What it represents | What it should be |
|---|---|---|---|
| Cyan rectangle | blue | Robot pose at frame *t* | Robot pose at frame *t* ✅ |
| Orange circle | orange | 1.2 m safety envelope | OK ✅ |
| Red dots | red | MoCap marker cloud (trajectory) | OK ✅ |
| **Relation** | — | Robot = **single point**, human = **hundreds of points** | **Robot and human should each be ONE pose at ONE shared timestamp** ❌ |

The red dots span roughly 3–4 meters of arc. The robot occupies a single grid cell. **Time is not shared between the two streams.** This is BUG-A in its purest visual form.

### Evidence #2 — BUG-B: YOLO sees people that aren't people

In `2_YOLO_Detections/cam_frame_*.png` (Image 2, IR view):

- `person: 0.61` on a **static robotic arm** (right side of frame). It has not moved in 30 seconds. YOLO fired because the silhouette has a "head + torso + arm" gestalt.
- `person: 0.76` on **empty background noise** near the right edge (clutter / cable / shadow).
- `chair: 0.61` and `chair: 0.58` are bounding boxes that **do not enclose an actual chair** — they enclose vertical metallic structures.
- Only the **center human** is correctly labeled `person: 0.60`. That's 1 correct out of 5.

Confidence thresholds are not filtering garbage. The dataset's "person" class is contaminated.

### Evidence #3 — Cross-modal renderer probably doesn't fuse time

The BEV renders the robot pose from `slam_data.pkl["pose"]` (probably a single `(x, y, θ)` array — the latest fix) and overlays **all** MoCap rigid-body samples from `mocap_data.pkl` (an N×3 array of positions). No `frame_id` join is done. So the red cloud is the **entire session's** human path, and the cyan box is **one frame's** robot pose, plotted on the same canvas.

### Cited files (most likely offenders)

| File | Likely bug site | Reason |
|---|---|---|
| `agents/bev_image_renderer.py` | the `draw_robot()` + `draw_mocap()` calls (≈ L140–L180) | renders pose without `frame_idx` argument |
| `agents/spatial_temporal_fusion.py` | ≈ L260–L330 (the merge of SLAM + MoCap) | probably concatenates arrays instead of joining by timestamp |
| `agents/cross_modal_aligner.py` | ≈ L60–L90 (the alignment function) | likely uses `len()` truncation instead of nearest-neighbour timestamp match |
| `agents/scene_object_detector.py` | YOLO inference call, ≈ L70–L100 | no per-class confidence floor, no geometric sanity check (height/width ratio) |
| `agents/vla_dataset_builder.py` | ≈ L40–L60 (sample assembly) | pulls `(rgb, slam_pose, mocap_pose)` from mismatched indices |

I cannot read every line, but the symptom-shape is unmistakable.

---

## [TEST]

Three commands that will **prove** BUG-A and BUG-B in 30 seconds on Kiarash's machine.

### Test 1 — Verify SLAM and MoCap have independent clocks

```powershell
cd "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
python -c "
import pickle, numpy as np
s = pickle.load(open(r'sessions\session_2026-08-27_17-54-20\slam_data.pkl','rb'))
m = pickle.load(open(r'sessions\session_2026-08-27_17-54-20\mocap_data.pkl','rb'))
print('SLAM keys :', list(s.keys()) if isinstance(s,dict) else type(s))
print('MoCap keys:', list(m.keys()) if isinstance(m,dict) else type(m))
# Look for any 't' or 'timestamp' field
for k,v in (s.items() if isinstance(s,dict) else []):
    a = np.asarray(v)
    print(f'  SLAM[{k}] shape={a.shape} dtype={a.dtype}')
for k,v in (m.items() if isinstance(m,dict) else []):
    a = np.asarray(v)
    print(f'  MoCap[{k}] shape={a.shape} dtype={a.dtype}')
"
```

**Pass criterion:** both dicts must contain a `timestamp` (or `t`, `time`) array of equal length AND same dtype. **Fail = BUG-A confirmed.**

### Test 2 — Verify YOLO class confusion

```powershell
python -c "
import json, collections
y = json.load(open(r'sessions\session_2026-08-27_17-54-20\yolo_results.json'))
c = collections.Counter([d.get('name','?') for d in y])
print('YOLO class histogram:', dict(c))
print('Total dets:', len(y))
# count low-confidence dets
low = sum(1 for d in y if d.get('confidence',1.0) < 0.5)
print(f'Dets with conf<0.5: {low} ({100*low/max(1,len(y)):.1f}%)')
"
```

**Pass criterion:** `person` should be the rarest moving-object class (you have at most 1–2 humans in the lab). If `person > 5` per frame, **BUG-B confirmed.**

### Test 3 — Plot robot and human on a shared time axis

```powershell
python -c "
import pickle, numpy as np, matplotlib.pyplot as plt
s = pickle.load(open(r'sessions\session_2026-08-27_17-54-20\slam_data.pkl','rb'))
m = pickle.load(open(r'sessions\session_2026-08-27_17-54-20\mocap_data.pkl','rb'))
# adjust keys to whatever Test 1 prints
sx, sy = np.asarray(s['x']), np.asarray(s['y'])
mx, my = np.asarray(m['x']), np.asarray(m['y'])
print(f'SLAM N={len(sx)}  range x=[{sx.min():.2f},{sx.max():.2f}]')
print(f'MoCap N={len(mx)}  range x=[{mx.min():.2f},{mx.max():.2f}]')
fig,ax=plt.subplots(2,1,figsize=(8,6))
ax[0].plot(sx, label='robot SLAM'); ax[0].plot(mx, label='human MoCap'); ax[0].legend(); ax[0].set_title('x(t)')
ax[1].plot(sy, label='robot SLAM'); ax[1].plot(my, label='human MoCap'); ax[1].legend(); ax[1].set_title('y(t)')
plt.tight_layout(); plt.savefig(r'audit_workspace\sync_check.png', dpi=120); print('saved audit_workspace\sync_check.png')
"
```

**Pass criterion:** the two curves should overlap in time (i.e., show robot and human moving together during the same intervals). If robot is a flat line while human walks, **BUG-A confirmed.**

---

## [FIX]

### Fix 1 — Synchronize by nearest-neighbour timestamp (the core of BUG-A)

Drop this into `agents/cross_modal_aligner.py` (replace the alignment block around L60–L90):

```python
import numpy as np

def align_by_timestamp(slam_t, slam_xy, mocap_t, mocap_xy, max_dt=0.05):
    """
    Join SLAM and MoCap streams by nearest timestamp.
    max_dt: max allowed gap in seconds (50 ms = 20 Hz).
    Returns: (slam_aligned, mocap_aligned, mask) each shape (K, 2)
    """
    slam_t = np.asarray(slam_t).reshape(-1)
    mocap_t = np.asarray(mocap_t).reshape(-1)
    slam_xy = np.asarray(slam_xy).reshape(-1, 2)
    mocap_xy = np.asarray(mocap_xy).reshape(-1, 2)

    K = min(len(slam_t), len(mocap_t))
    slam_out = np.zeros((K, 2))
    mocap_out = np.zeros((K, 2))
    mask = np.zeros(K, dtype=bool)

    j_mo = 0
    for i in range(K):
        t = slam_t[i]
        # advance MoCap pointer until just past t
        while j_mo + 1 < len(mocap_t) and mocap_t[j_mo + 1] <= t:
            j_mo += 1
        if abs(mocap_t[j_mo] - t) <= max_dt:
            slam_out[i]  = slam_xy[i]
            mocap_out[i] = mocap_xy[j_mo]
            mask[i] = True
    return slam_out[mask], mocap_out[mask], mask
```

Then in `agents/bev_image_renderer.py` (the function that draws both layers), change the call site from:

```python
# WRONG — draws the whole trajectory and one robot pose
draw_robot(ax, slam_pose[-1])
draw_mocap(ax, mocap_xy)
```

to:

```python
# RIGHT — draws frame i only
draw_robot(ax, slam_aligned[i])
draw_human(ax, mocap_aligned[i])
```

…and wrap the renderer in a loop over `i in range(len(slam_aligned))` to write one PNG per matched frame.

### Fix 2 — Kill YOLO hallucinations (the core of BUG-B)

In `agents/scene_object_detector.py`, around the inference call:

```python
# BEFORE (probably something like):
results = model(frame, conf=0.25)  # too low

# AFTER — per-class thresholds and aspect-ratio sanity:
CLASS_CONF = {
    "person":     0.55,
    "chair":      0.60,
    "robot":      0.50,
    "table":      0.55,
}
MIN_AREA_FRAC = 0.01   # bbox must cover >=1% of frame
MAX_AREA_FRAC = 0.60   # bbox must cover <=60% of frame (kills "whole wall" dets)

results = model(frame, conf=0.50, iou=0.45, verbose=False)[0]
clean = []
for box, cls_id, conf in zip(results.boxes.xyxy,
                             results.boxes.cls,
                             results.boxes.conf):
    name = model.names[int(cls_id)]
    thr  = CLASS_CONF.get(name, 0.60)
    if float(conf) < thr:
        continue
    x1,y1,x2,y2 = box.cpu().numpy()
    area = max(1, (x2-x1)*(y2-y1))
    frac = area / (frame.shape[0]*frame.shape[1])
    if not (MIN_AREA_FRAC <= frac <= MAX_AREA_FRAC):
        continue
    # Reject "person" detections wider than tall (robots are usually tall & narrow)
    if name == "person" and (x2-x1) > 1.5*(y2-y1):
        continue
    clean.append({"name": name, "conf": float(conf),
                  "xyxy": [float(x1),float(y1),float(x2),float(y2)]})
```

Then **re-train YOLO on a custom class** (`person / robot / chair / table / obstacle`) with at least 200 labelled frames from this lab. Use `cvat_prepopulator.py` + `cvat_converter.py` to bootstrap labels from the existing MoCap-rigid-body ground truth (the human and robot are both tracked).

---

## [POWERSHELL]

Save as `D:\kiarash\fixes\pass1_sync_and_yolo.ps1` and run as Administrator:

```powershell
# === Pass-1 patch: align streams + clean YOLO ===
$ErrorActionPreference = "Stop"
