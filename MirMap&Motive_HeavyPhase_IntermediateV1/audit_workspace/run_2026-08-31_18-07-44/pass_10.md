# Pass 10: Consensus Judge
Model: openrouter/auto

[WHAT]

**Verdict: this is not yet a defensible “safe semantic VLA” result.** It is currently a single-session behavioral-regression demonstration with unresolved sensor synchronization, unvalidated perception, weak angular data, and potentially invalid evaluation.

The most urgent issue is **BUG-A: prove time synchronization and coordinate registration before collecting or training on another frame**. If the robot is frozen while the human moves, the model is learning a false world model. Additional data collected through the same broken alignment will make the thesis worse, not better.

I cannot honestly provide exact line numbers for most agent defects: the prompt supplies file names and file lengths, but not their source contents. Any reviewer claiming `MoCapData.py:417` or `spatial_temporal_fusion.py:203` from this evidence would be inventing citations. The exact citations currently supported are:

- `generate_publication_report_v5.py:10–18` — hard-coded machine-specific paths and run creation.
- `generate_publication_report_v5.py:48–57` — selects the newest session containing only `slam_data.pkl`.
- `generate_publication_report_v5.py:60–64` — discovers BEV frames only from the selected session.
- `generate_publication_report_v5.py:68–81` — loads evaluation and training history from fixed paths without dataset/model provenance validation.
- `generate_publication_report_v5.py:86–108` — computes and publishes performance numbers from `eval_results_v3.json`.
- `A15_referee_ai_loop.py:approximately 1–20` — external LLM referee infrastructure, not an experimental validation mechanism.
- `MASTER_REPORT v7.7`, §2–§3 — reports 344 samples from one valid BEV session and only three rotational validation examples.
- `eval_results_v3.json`, top level and `p[]` — reports aggregate metrics but does not establish session-disjoint, subject-disjoint, or leakage-free evaluation.
- `training_history.json`, `canary[]` — two canary samples are repeatedly evaluated during training; they are not a held-out test set.

[ EVIDENCE ]

### 1. Dataset leakage and false independence

`MASTER_REPORT v7.7`, §2–§3 states:

```text
344 total pairs
275 train
69 validation
only session_2026-08-27_17-54-20 has 344 BEV frames
```

Thus the nominal 80/20 split is almost certainly a **random frame split within one trajectory**. Adjacent frames are highly correlated. A model can memorize scene layout, camera appearance, and trajectory phase while appearing accurate.

This is not evidence of generalization to a new session, person, lighting condition, obstacle arrangement, or motion pattern.

### 2. The report generator silently selects stale or incomplete data

`generate_publication_report_v5.py:48–57`:

```python
for cand in reversed(sessions):
    if os.path.exists(os.path.join(cand, "slam_data.pkl")):
        S = cand
        break
```

This accepts a session merely because `slam_data.pkl` exists. It does not require:

- `mocap_data.pkl`
- YOLO output
- synchronized timestamps
- matching frame counts
- valid BEV images
- calibration metadata
- quality-gate approval

The report can therefore describe one session while its evaluation belongs to another. That is a provenance failure.

### 3. Hard-coded paths make reproduction and review unsafe

`generate_publication_report_v5.py:10–18` hard-codes:

```python
BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
```

and loads fixed artifacts:

```python
eval_results_v3.json
models\qwen3_vla_mir100_lora_v2\training_history.json
```

There is no recorded:

- Git commit
- model checkpoint hash
- dataset manifest hash
- calibration version
- preprocessing version
- split manifest
- random seed
- software environment

The claim in the report that “all numbers [are] traceable” is therefore unsupported.

### 4. The published metrics do not establish safe navigation

`eval_results_v3.json` reports:

```text
MAE_v = 0.0600 m/s
MAE_w = 0.0799 rad/s
```

These are regression errors, not safety metrics. They say nothing about:

- collision rate
- minimum human distance
- emergency-stop latency
- missed-person rate
- false obstacle rate
- command saturation
- recovery after tracking loss
- performance under synchronization failure
- closed-loop stability

A model can obtain low MAE by predicting conservative or frequent stationary commands. This is especially plausible with 92 idle samples and the canary predictions clustering around a few values.

### 5. Angular performance is underpowered

`MASTER_REPORT v7.7`, §2:

```text
ROTATIONAL_MANEUVER: 32 total
validation: n = 3
```

A rotational validation result with `n=3` is descriptive only. The reported `R²_w = 0.134` is consistent with an unusable angular policy, not with a successful navigation controller.

The angular command must be evaluated separately by:

- signed left/right turns
- low/high angular speed
- simultaneous `v` and `w`
- stop-to-turn and turn-to-stop transitions
- unseen trajectories

### 6. The canary set is not validation

`training_history.json`, `canary[]` contains two examples evaluated at every epoch. Repeatedly inspecting or selecting a checkpoint based on those examples makes them development data. They cannot support a publication claim of held-out performance.

For example, the second canary evolves from:

```text
epoch 1: [0.25, 0.00]
epoch 6: [0.002, -0.45]
```

That demonstrates optimization on two examples, not generalization.

### 7. Perception is not validated by screenshots

The provided YOLO image shows person and chair detections, but a visualization is not an accuracy evaluation. There is no confusion matrix, precision, recall, mAP, calibration curve, or manually verified test set.

The reported human/chair and robot/person confusion must be treated as a failed perception component until quantified. A robot detector trained on generic YOLO classes is especially vulnerable to confusing the MiR chassis with a person or other industrial object.

### 8. MiR100 physical limits are a hard safety invariant

The stated BUG-C (`9.13 m/s`) is a deployment-blocking defect. The model or command adapter must enforce:

```text
0 <= v <= 1.5 m/s
|w| <= 1.0 rad/s
```

The limit must be enforced at the final command boundary, not merely in training labels. Training-time clipping alone is insufficient.

### 9. External LLM referee code is circular evidence

`A15_referee_ai_loop.py:approximately 1–20` and its `PROJECT_CONTEXT` encode the known bugs and request “referee” judgments. That system can summarize evidence, but its output is not an independent scientific evaluation. The self-score of 88.5/100 and report readiness grade must be removed from the evidence section or explicitly labeled as non-scientific internal commentary.

[ TEST ]

Run these tests before retraining.

### Test 1: session integrity and provenance

```python
# agents/audit_dataset.py
from pathlib import Path
import json, hashlib, pickle, sys

BASE = Path(sys.argv[1])
required = ["slam_data.pkl", "mocap_data.pkl", "yolo_results.json"]

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

rows = []
for s in sorted((BASE / "sessions").glob("session_*")):
    present = {x: (s / x).exists() for x in required}
    pngs = list((s / "bev_images").glob("*.png")) if (s / "bev_images").exists() else []
    row = {
        "session": s.name,
        "required": present,
        "bev_count": len(pngs),
        "files": {x: sha256(s / x) for x in required if (s / x).exists()}
    }
    print(json.dumps(row))
    if not all(present.values()) or not pngs:
        print(f"FAIL incomplete session: {s.name}", file=sys.stderr)
        raise SystemExit(2)
    rows.append(row)

if len(rows) < 3:
    raise SystemExit("FAIL: fewer than three complete sessions")
(BASE / "dataset_manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(f"PASS: {len(rows)} complete sessions")
```

### Test 2: synchronized timestamps

The fusion output must contain timestamps from every sensor. Reject a sample if the nearest timestamp error exceeds the declared tolerance.

```python
import numpy as np

def align_nearest(reference_t, source_t, max_gap=0.050):
    reference_t = np.asarray(reference_t, dtype=float)
    source_t = np.asarray(source_t, dtype=float)
    idx = np.searchsorted(source_t, reference_t)
    idx = np.clip(idx, 1, len(source_t) - 1)
    left = idx - 1
    use_left = abs(source_t[left] - reference_t) <= abs(source_t[idx] - reference_t)
    chosen = np.where(use_left, left, idx)
    error = np.abs(source_t[chosen] - reference_t)
    valid = error <= max_gap
    return chosen, error, valid
```

Required audit output:

```text
frame_id, slam_timestamp, mocap_timestamp, camera_timestamp,
dt_slam_mocap, dt_slam_camera, valid
```

Do not interpolate across missing data without recording the gap.

### Test 3: velocity sanity

```python
import numpy as np

def finite_difference_speed(xy, t):
    xy = np.asarray(xy, dtype=float)
    t = np.asarray(t, dtype=float)
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("timestamps are not strictly increasing")
    speed = np.linalg.norm(np.diff(xy, axis=0), axis=1) / dt
    return np.r_[speed[0], speed]

def validate_mir_commands(v, w):
    v, w = np.asarray(v), np.asarray(w)
    if np.any(~np.isfinite(v)) or np.any(~np.isfinite(w)):
        raise ValueError("non-finite command")
    if np.max(v) > 1.5 + 1e-6:
        raise ValueError(f"linear speed exceeds MiR100 limit: {np.max(v)}")
    if np.max(np.abs(w)) > 1.0 + 1e-6:
        raise ValueError(f"angular speed exceeds MiR100 limit: {np.max(np.abs(w))}")
```

Investigate 9.13 m/s rather than silently clipping it. The likely causes are milliseconds treated as seconds, pixels treated as metres, or a frame index used as time.

### Test 4: split leakage

The split must be generated by session, not frame:

```python
from sklearn.model_selection import GroupShuffleSplit

groups = [x["session_id"] for x in samples]
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_i, val_i = next(gss.split(samples, groups=groups))
assert set(groups[i] for i in train_i).isdisjoint(set(groups[i] for i in val_i))
```

Keep one completely untouched test set. Do not use it for checkpoint selection.

### Test 5: perception confusion matrix

Manually annotate at least 500 frames, with explicit classes:

```text
human, MiR100, chair, table, unknown
```

Report per-class precision, recall, F1, and confidence calibration. Generic YOLO labels are not sufficient for a robot-specific safety claim.

[ FIX ]

### Fix 1: one authoritative fusion contract

Create a single output schema. Every row must include:

```python
{
    "frame_id": int,
    "t_camera": float,
    "t_slam": float,
    "t_mocap": float,
    "dt_slam_mocap": float,
    "dt_slam_camera": float,
    "robot_pose_slam": [x, y, yaw],
    "human_pose_world": [x, y],
    "human_pose_robot": [x, y],
    "yolo": [...],
    "v_gt": float,
    "w_gt": float,
    "quality": "PASS"
}
```

Only one module should perform timestamp alignment. Retire or convert to library functions the overlapping implementations in:

- `cross_modal_aligner.py`
- `semantic_slam_fusion.py`
- `spatial_temporal_fusion.py`

Do not allow each script to write a replacement `.pkl` with a different coordinate convention.

### Fix 2: explicit coordinate transform

```python
import numpy as np

def world_to_robot(point_xy, robot_xy, robot_yaw):
    p = np.asarray(point_xy, dtype=float) - np.asarray(robot_xy, dtype=float)
    c, s = np.cos(robot_yaw), np.sin(robot_yaw)
    return np.array([c*p[0] + s*p[1], -s*p[0] + c*p[1]])
```

Document axis direction, units, origin, yaw convention, and calibration ID in the dataset metadata. A static robot pose with a moving human must fail the quality gate unless independently explained.

### Fix 3: command-boundary safety wrapper

```python
def safe_mir_command(v, w, human_distance=None, tracking_ok=True):
    if not tracking_ok:
        return 0.0, 0.0

    v = float(np.clip(v, 0.0, 1.5))
    w = float(np.clip(w, -1.0, 1.0))

    if human_distance is not None:
        if human_distance < 0.60:
            return 0.0, 0.0
        if human_distance < 1.20:
            v = min(v, 0.15)

    return v, w
```

This is a last-resort guard, not a substitute for a certified MiR safety system. The learned policy must never bypass the robot’s native safety mechanisms.

### Fix 4: honest evaluation

Report:

- session-disjoint test MAE
- class-balanced MAE
- `v` and `w` MAE separately
- RMSE and confidence intervals
- signed-turn accuracy
- stop-event recall
- maximum command
- human minimum-distance violations
- emergency-stop latency
- collision/near-collision count
- tracking-loss behavior

Remove “Paper Readiness Score,” “Grade A-,” “OPERATIONAL,” and “Ready for supervisor review” from scientific results unless independently defined and validated.

[ POWERSHELL ]

These commands create a safe audit and prevent accidental deployment. Replace `$Project` if required.

```powershell
$Project = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
Set-Location $Project

# Archive current claims before modification
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force "audit_archive\$stamp" | Out-Null
Copy-Item "eval_results_v3.json","MASTER_REPORT v7.7*" -Destination "audit_archive\$stamp" -ErrorAction SilentlyContinue

# Run integrity audit
python agents\audit_dataset.py $Project
if ($LASTEXITCODE -ne 0) {
    throw "Dataset integrity failed. Do not train or drive the robot."
}

# Find suspicious velocity literals and unsafe command paths
Select-String -Path agents\*.py -Pattern "9\.13|speed|max_velocity|velocity|angular|cmd_vel|set_velocity|robot.*move" |
    Format-Table Path,LineNumber,Line -AutoSize

# Find all frame-level random splitting
Select-String -Path agents\*.py -Pattern "train_test_split|random_split|shuffle|80.?20|0\.8|275|69" |
    Format-Table Path,LineNumber,Line -AutoSize

# Find timestamp and coordinate handling
Select-String -Path agents\*.py -Pattern "timestamp|time_ns|time_ms|interpol|searchsorted|nearest|scale|origin|yaw|heading" |
    Format-Table Path,LineNumber,Line -AutoSize

# Refuse execution if known unsafe value remains in source
$bad = Select-String -Path agents\*.py -Pattern "9\.13"
if ($bad) { throw "Unsafe 9.13 m/s literal remains in agents." }

# Produce a reproducibility manifest
@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    git_commit = (git rev-parse HEAD 2>$null)
    python = (python --version 2>&1).ToString()
    project = $Project
} | ConvertTo-Json | Set-Content "audit_workspace\run_manifest.json" -Encoding UTF8
```

Create the audit file with:

```powershell
@'
# Save the Python code from [TEST] section here:
'@ | Set-Content agents\audit_dataset.py -Encoding UTF8
```

Do **not** patch command execution by blindly replacing every velocity expression. First identify the final MiR API call, then put `safe_mir_command()` immediately before that call and add a unit test.

[ SEQUENCES ]

Do not record “Session 