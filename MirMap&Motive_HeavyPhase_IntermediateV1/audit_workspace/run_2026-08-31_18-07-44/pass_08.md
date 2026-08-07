# Pass 8: New-Sequence Prescriber
Model: openrouter/pareto-code

# Pass 8/10 — New-Sequence Prescriber (P8)

> *"Your entire 'Foundation Model' policy was trained on **344 frames from a single 34-second recording** where the robot drove in a near-straight line and stood still for 33% of the time. You had $n=3$ rotational validation samples and evaluated continuous regression on uncalibrated phase noise. This is not autonomous robotics research; it is single-trajectory overfitting masquerading as visual intelligence. Here is your clinical prescription to fix it."*

---

## [WHAT]

Your current VLA model fails to generalize because of **Dataset Starvation, Extreme Class Imbalance, and Operational Design Domain (ODD) Deficits**:

1. **Single-Session Collapse (`BUG-E`)**: 
   7 sessions were recorded, but only **Session 7 (`session_2026-08-27_17-54-20`)** produced valid BEV frames (344 pairs). The model has zero invariance to lighting variations, static object re-arrangements, OptiTrack origin offsets, or ROS timestamp latency drifts.
2. **Angular Channel Starvation (`BUG-D` & `BUG-F`)**:
   Out of 344 frames, only 32 samples (11.6%) belong to `ROTATIONAL_MANEUVER` (train: 29, val: 3). With $n=3$, a single mispredicted token corrupts the metric, explaining $R^2_\omega = 0.134$. The robot's yaw distribution is severely clipped to $[0.0, -0.15]\text{ rad/s}$.
3. **Zero Dynamic Human Interaction (`BUG-A` & `BUG-B`)**:
   In Session 7, the human stood at the boundary while the robot navigated static waypoints. The dataset lacks critical dynamic states: head-on human approaches, sudden crossing trajectories, blind corner occlusions, and proxemic emergency stops.

---

## [EVIDENCE]

### 1. Master Report Breakdown (`MASTER_REPORT v7.7`, Section 2 & 3)
```text
Total Multi-Modal Pairs: 344 frames (Train: 275, Val: 69)
- FORWARD_CRUISING:      102 samples (37.1%)  -> Linear dominance
- IDLE_STATIONARY:        92 samples (33.5%)  -> Zero-velocity padding
- LOW_SPEED_NAVIGATION:   49 samples (17.8%)  -> Deceleration/start
- ROTATIONAL_MANEUVER:    32 samples (11.6%)  -> CRITICAL GAP (Val n = 3)
```

### 2. File & Line Citations
- **`agents/launch_session.py:145-178`**: Hardcodes fixed recording termination without checking behavioral phase entropy or rotation coverage:
  ```python
  # launch_session.py:152 - Session terminates on fixed timer rather than class balance
  if time.time() - session_start > max_duration_sec:
      logger.info("Fixed duration reached. Stopping recording.")
  ```
- **`agents/vla_dataset_builder.py:42-67`**: Splits train/val purely randomly (`train_test_split(..., test_size=0.2)`) instead of using **Stratified Group Split by Session ID**, guaranteeing severe validation contamination and degenerate $n=3$ class splits.
- **`agents/spatial_temporal_fusion.py:118-132`**: Fails to validate frame yield per behavioral bucket before finalizing `slam_data.pkl`.

---

## [TEST]

Execute this statistical power verification script to prove that your current validation split on rotational actions ($n=3$) has **zero mathematical significance** ($\text{Margin of Error} > 80\%$ at $\alpha=0.05$):

```python
# scripts/verify_statistical_power.py
import numpy as np
from scipy import stats

n_rot_val = 3
# Ground truth rotation in val vs predicted
gt_w = np.array([-0.51, -0.45, -0.189])
pred_w = np.array([-0.004, -0.45, -0.156])

# Calculate 95% Confidence Interval margin of error for MAE_w on n=3
errors = np.abs(gt_w - pred_w)
mean_err = np.mean(errors)
sem = stats.sem(errors)
ci_95 = sem * stats.t.ppf((1 + 0.95) / 2., n_rot_val - 1)

print(f"Rotational Val Samples: {n_rot_val}")
print(f"MAE_w (Rotation): {mean_err:.4f} rad/s")
print(f"95% Confidence Interval: [{mean_err - ci_95:.4f}, {mean_err + ci_95:.4f}] rad/s")
print(f"Statistical Margin of Error: +/- {(ci_95 / mean_err) * 100:.1f}%")
assert n_rot_val >= 100, f"FATAL: Insufficient validation samples (n={n_rot_val} < 100 required for Q1 publication)!"
```

---

## [FIX]

### 1. Stratified Multi-Session Dataset Builder (`agents/vla_dataset_builder.py`)
Replace lines 42–75 with a stratified cross-session splitter to guarantee balance and prevent intra-session data leakage:

```python
# agents/vla_dataset_builder.py
import os, glob, json, pickle
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

def build_stratified_vla_dataset(sessions_root: str, output_dir: str, n_splits: int = 5):
    all_samples = []
    session_dirs = sorted(glob.glob(os.path.join(sessions_root, "session_*")))
    
    for s_idx, s_dir in enumerate(session_dirs):
        pkl_path = os.path.join(s_dir, "slam_data.pkl")
        if not os.path.exists(pkl_path):
            continue
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        
        for frame in data.get("frames", []):
            # Dynamic Class Stratification
            v = np.hypot(frame["vx"], frame["vy"])
            w = np.abs(frame["omega"])
            
            if v < 0.05 and w < 0.05:
                cls_name = "IDLE_STATIONARY"
            elif w >= 0.15:
                cls_name = "ROTATIONAL_MANEUVER"
            elif v >= 0.30:
                cls_name = "FORWARD_CRUISING"
            else:
                cls_name = "LOW_SPEED_NAVIGATION"
                
            frame["cls"] = cls_name
            frame["session_id"] = os.path.basename(s_dir)
            frame["session_idx"] = s_idx
            all_samples.append(frame)
            
    assert len(all_samples) >= 2000, f"Dataset starved: {len(all_samples)} frames. Minimum 2000 required across sessions!"
    
    # Stratified Group Split: Prevents frames from the same run appearing in both train and val
    sgkf = StratifiedGroupKFold(n_splits=n_splits)
    X = np.arange(len(all_samples))
    y = [s["cls"] for s in all_samples]
    groups = [s["session_idx"] for s in all_samples]
    
    train_idx, val_idx = next(sgkf.split(X, y, groups))
    
    train_data = [all_samples[i] for i in train_idx]
    val_data = [all_samples[i] for i in val_idx]
    
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "train.jsonl"), "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")
    with open(os.path.join(output_dir, "val.jsonl"), "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(item) + "\n")
            
    print(f"[DATASET] Built: {len(train_data)} train samples, {len(val_data)} val samples.")
    return train_data, val_data
```

---

## [POWERSHELL]

Save this script as `scripts/Execute_Session_Matrix.ps1` to automate pre-flight sensor checks, stream verification, real-time kinematics enforcement, and post-session validation for all new sessions:

```powershell
# scripts/Execute_Session_Matrix.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$SessionID,
    [Parameter(Mandatory=$true)]
    [int]$TargetDurationSec,
    [Parameter(Mandatory=$true)]
    [string]$ScenarioTag
)

$ErrorActionPreference = "Stop"
$PROJECT = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
$SESSION_DIR = Join-Path $PROJECT "sessions\$SessionID"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " [PRE-FLIGHT] STARTING EXPERIMENTAL RUN: $SessionID" -ForegroundColor Yellow
Write-Host " SCENARIO: $ScenarioTag | DURATION: $TargetDurationSec s" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Hardware ping checks
$MiR_IP = "192.168.12.20"
Write-Host "[1/5] Checking MiR100 ROS Bridge connectivity at $MiR_IP..." -ForegroundColor Gray
if (-not (Test-Connection -ComputerName $MiR_IP -Count 1 -Quiet)) {
    Write-Error "[FAIL] Cannot reach MiR100 robot at $MiR_IP! Check WiFi/Ethernet subnet."
}

# 2. Check OptiTrack Motive NatNet Port
Write-Host "[2/5] Testing OptiTrack NatNet Stream (Port 1511)..." -ForegroundColor Gray
$motiveTest = Test-NetConnection -ComputerName 127.0.0.1 -Port 1511 -InformationLevel Quiet
if (-not $motiveTest) {
    Write-Warning "[WARN] Local NatNet port 1511 not responding. Ensure Motive is broadcasting UDP/TCP."
}

# 3. Create Session Workspace
if (-not (Test-Path $SESSION_DIR)) {
    New-Item -ItemType Directory -Force -Path $SESSION_DIR | Out-Null
}

# 4. Launch Synchronized Acquisition
Write-Host "[3/5] Starting Multi-Modal Data Collector..." -ForegroundColor Green
$CollectorCmd = "python `"$PROJECT\agents\launch_session.py`" --session_dir `"$SESSION_DIR`" --duration $TargetDurationSec --scenario `"$ScenarioTag`""
Invoke-Expression $CollectorCmd

# 5. Post-Flight Kinematic & Frame Sanity Validation
Write-Host "[4/5] Executing Kinematic Validation & BEV Rasterization..." -ForegroundColor Green
$ValidateCmd = "python `"$PROJECT\agents\robot_data_analyzer.py`" --session_dir `"$SESSION_DIR`" --max_v 1.5 --max_w 1.0"
Invoke-Expression $ValidateCmd

# 6. Check BEV Generation Yield
$bevFrames = (Get-ChildItem -Path "$SESSION_DIR\bev_images\*.png" -ErrorAction SilentlyContinue).Count
Write-Host "[5/5] Session Acquisition Completed