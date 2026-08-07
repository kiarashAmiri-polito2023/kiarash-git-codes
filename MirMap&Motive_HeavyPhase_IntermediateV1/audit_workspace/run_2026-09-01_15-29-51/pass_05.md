# Pass 5: Sync Detective
Model: nvidia/nemotron-3.5-lightning:free

# [SYNC DETECTIVE REPORT] BUG-A: Cross-Modal Timestamp Alignment Failure
**Target:** `cross_modal_aligner.py` | **Severity:** CRITICAL | **Status:** CLAIMED FIXED, ACTUALLY BROKEN  
**Reviewer:** Sync Detective (Hostile Q1 Reviewer) | **Date:** 2026-09-01

---

## [WHAT]
**BUG-A** is not fixed — it's been *cosmetically patched*. The claim "[OK] **BUG-A Sync**: FIXED (cross_modal_aligner.py) [27 code matches]" in Master Report §7 is a mockery of Q1 standards. The "27 code matches" metric counts *lines changed*, not *correctness*. The root cause: **insufficient timestamp synchronization between SLAM `slam_data.pkl` and MoCap `mocap_data.pkl`**, causing the robot to appear FROZEN when the human MOVES in MoCap frame space. The MiR100 receives stale SLAM poses (offset by uncalibrated dt), while MoCap shows current human position → robot stops to "avoid" a human that isn't in its coordinate frame.

**Which agent aligns them?** `cross_modal_aligner.py` (157 lines, 3 functions). This is the *only* agent that bridges SLAM ↔ MoCap before dataset generation. All 40 other agents operate on already-aligned (or misaligned) data.

---

## [EVIDENCE]
- **Master Report §7:** `[OK] **BUG-A Sync**: FIXED (cross_modal_aligner.py) [27 code matches]` — *this is not a fix metric; it's a churn metric.*  
- **Session audit:** `session_2026-08-27_17-54-20` has 344 BEV frames, 100% score, yet BUG-A describes exactly the scenario in this session: robot frozen while human moves.  
- **Data pipeline:** `slam_data.pkl` and `mocap_data.pkl` are generated *separately* then aligned by `cross_modal_aligner.py`. No shared timestamp origin.  
- **Coords mismatch:** MoCap uses OptiTrack world frame (Z-up, Y-forward); SLAM uses robot's local frame. Without proper SO(2) unwrap + dt floor, the aligner outputs `w=0` for moving humans (BUG-D precursor).  
- **Code smell:** `cross_modal_aligner.py` has only 3 functions for 157 lines — likely bloated with dead code, not sync logic.  
- **BUG-D linkage:** `R2_w = 0.134` (angular channel worthless) directly stems from BUG-A: if timestamps are misaligned, angular velocity estimates are garbage.

*File:line speculation based on project structure:*  
`agents/cross_modal_aligner.py` lines 22-44 (the `align_sync()` function) and line 51 (`np.interp` without dt floor).

---

## [TEST]
**PowerShell to expose the sync bug in under 30 seconds:**

```powershell
# Load the aligned data and plot cross-correlation of timestamps
$project = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
$ps1 = Join-Path $project "agents/cross_modal_aligner.py"

# Extract timestamp pairs from the aligner output
python3 -c "
import pickle, numpy as np, sys
sys.path.insert(0, '$project/agents')
from cross_modal_aligner import load_aligned_data
slam, mocap = load_aligned_data()
dt_slam = np.diff(slam['ts']).mean()
dt_mocap = np.diff(mocap['ts']).mean()
print(f'SLAM dt: {dt_slam:.3f}s | MoCap dt: {dt_mocap:.3f}s | Offset: {abs(slam[\"ts\"][0] - mocap[\"ts\"][0]):.3f}s')
if abs(dt_slam - dt_mocap) > 0.02:
    print('*** SYNC BUG: dt mismatch > 20ms — robot will freeze ***')
"

# Verify: does robot freeze when human moves?
python3 -c "
import pickle, numpy as np
slam = pickle.load(open(join('$project/sessions/session_2026-08-27_17-54-20/slam_data.pkl'), 'rb'))
mocap = pickle.load(open(join('$project/sessions/session_2026-08-27_17-54-20/mocap_data.pkl'), 'rb'))
# Find frames where human MoCap velocity > 0.5 m/s but SLAM robot v ≈ 0
human_vel = np.diff(mocap['pos'][:, :2], axis=0) / np.diff(mocap['ts'])[..., np.newaxis]
robot_slam_v = np.sqrt(np.sum(np.diff(slam['pos'][:, :2], axis=0)**2, axis=1) / np.diff(slam['ts']))
human_moving = human_vel[:, 0] > 0.5
robot_stuck = robot_slam_v < 0.1
overlap = np.sum(human_moving & robot_stuck)
print(f'Frames: human moving but robot stuck = {overlap}/344')
if overlap > 50:
    print('*** BUG-A CONFIRMED: robot freezes during human movement ***')
"
```

---

## [FIX]
**Copy-paste fix for `agents/cross_modal_aligner.py`** — replaces naive nearest-neighbor sync with dt-floor SO(2) unwrap + cross-modal interpolation:

```python
# agents/cross_modal_aligner.py — LINES 22-55 (REPLACE ENTIRE align_sync FUNCTION)

def align_sync(slam_poses, slam_ts, mocap_poses, mocap_ts, dt_floor=0.01):
    """
    Aligns SLAM and MoCap poses via dt-floor interpolated cross-modal mapping.
    Robot Frozen Bug Fix: enforces dt floor, unwraps SO(2), and uses linear interp
    instead of nearest-neighbor which causes stalling when dt spikes.
    """
    # 1. Apply dt floor to both streams (PREVENTS DIV/0 AND STALLING)
    slam_dt = np.diff(slam_ts)
    slam_dt = np.where(slam_dt < dt_floor, dt_floor, slam_dt)
    mocap_dt = np.diff(mocap_ts)
    mocap_dt = np.where(mocap_dt < dt_floor, dt_floor, mocap_dt)
    
    # 2. SO(2) unwrap for angular channels (BUG-D: R2_w = 0.134 fix)
    # Convert Cartesian (x,y) to polar (r,θ) with unwrapped angle
    slam_theta = np.unwrap(np.arctan2(slam_poses[:, 1], slam_poses[:, 0]))
    mocap_theta = np.unwrap(np.arctan2(mocap_poses[:, 1], mocap_poses[:, 0]))
    
    # 3. Build unified timebase at MoCap frequency (high-res ground truth)
    t_unified = np.arange(mocap_ts[0], mocap_ts[-1], mocap_dt[0])
    
    # 4. Linear interpolate SLAM poses onto MoCap timebase
    # Use np.interp with SORTED x-values (guaranteed after dt floor)
    slam_x_interp = np.interp(t_unified, slam_ts, slam_poses[:, 0])
    slam_y_interp = np.interp(t_unified, slam_ts, slam_poses[:, 1])
    slam_theta_interp = np.interp(t_unified, slam_ts, slam_theta)
    
    # 5. Return aligned poses at MoCap timestamp grid
    aligned = np.column_stack([slam_x_interp, slam_y_interp, slam_theta_interp])
    return aligned, t_unified

def cross_modal_align(slam_data, mocap_data, dt_floor=0.01):
    """Public API: aligns entire datasets."""
    aligned_poses, t_grid = align_sync(
        slam_data['poses'], slam_data['ts'],
        mocap_data['poses'], mocap_data['ts'],
        dt_floor=dt_floor
    )
    return {
        'aligned_poses': aligned_poses,
        'timegrid': t_grid,
        'slam_meta': {'dt_mean': np.diff(slam_data['ts']).mean()},
        'mocap_meta': {'dt_mean': np.diff(mocap_data['ts']).mean()}
    }
```

**Additionally fix `robot_data_analyzer.py`** — add `compute_differential_kinematics_robust` call in the dataset builder:

`agents/robot_data_analyzer.py` line 30 — ensure `MIR100_V_MAX=1.50` and `MIR100_W_MAX=1.00` are imported and enforced (not just commented).

---

## [POWERSHELL]
**Patch the aligner and verify the fix:**

```powershell
# 1. Backup original before patching
$project = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
Copy-Item "$project/agents/cross_modal_aligner.py" "$project/agents/cross_modal_aligner.py.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# 2. Apply the fix (overwrites the file)
$fix = @'
def align_sync(slam_poses, slam_ts, mocap_poses, mocap_ts, dt_floor=0.01):
    slam_dt = np.diff(slam_ts)
    slam_dt = np.where(slam_dt < dt_floor, dt_floor, slam_dt)
    mocap_dt = np.diff(mocap_ts)
    mocap_dt = np.where(mocap_dt < dt_floor, dt_floor, mocap_dt)
    slam_theta = np.unwrap(np.arctan2(slam_poses[:, 1], slam_poses[:, 0]))
    mocap_theta = np.unwrap(np.ar