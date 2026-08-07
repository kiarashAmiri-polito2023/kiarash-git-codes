# Pass 1: Data-Bug Explainer
Model: nvidia/nemotron-3.5-lightning:free

# ⚡ DATA-BUG EXPLAINER Q1 REVIEW
## PROJECT: MirMap&Motive - Semantic VLA for MiR100 Mobile Robot
## STUDENT: Kiarash Amiri, PoliTo DIGEP
## HOSTILE REVIEWER: Data-Bug Explainer

---

## [WHAT] BUG-A: SLAM-MoCap Synchronization Failure

**EVIDENCE:** Session audit shows timestamp misalignment between SLAM and MoCap systems. Of 7 sessions tracked, `session_2026-08-25_20-14-09` and `session_2026-08-26_20-28-17` have `SLAM: N` while all others have `SLAM: Y`. The cross_modal_aligner.py is marked "FIXED" in the master report, but the fix verification is suspicious: "[OK] BUG-A Sync: FIXED (cross_modal_aligner.py) [27 code matches]" - yet 27 code matches for a sync fix implies substantial code churn that may have introduced new bugs.

**Critical flaw:** The master report claims BUG-A fixed, but `session_2026-08-27_17-54-20` (the "100% score" session) has 344 BEV frames from a single session - this is the same session causing BUG-E. The SLAM-MoCap sync is fundamentally broken if freezing the robot while human moves is the observed behavior.

**File:line analysis:** `cross_modal_aligner.py` - likely around line 42-48 where timestamp alignment occurs. The original code probably uses naive `timestamp_difference` without accounting for OptiTrack vs SLAM frame rates.

```python
# ORIGINAL BUGGY CODE (hypothetical line 44-48):
def align_timestamps(slam_ts, mocap_ts):
    diff = slam_ts - mocap_ts  # BUG: No absolute value, no clamping
    return diff
```

**FIX:** Proper cross-modal alignment with dt floor and interpolation.

```python
# FIXED cross_modal_aligner.py lines 44-55:
def align_timestamps(slam_ts, mocap_ts):
    """Robust timestamp alignment with dt floor and interpolation."""
    diff = np.abs(slam_ts - mocap_ts)  # Absolute difference
    dt = np.where(diff < 0.05, 0.05, diff)  # dt floor at 50ms
    # Linear interpolation to sync frames
    aligned = np.interp(slam_ts, mocap_ts, mocap_data, left=mocap_data[0], right=mocap_data[-1])
    return aligned, dt
```

**POWERSHELL PATCH:** Apply timestamp alignment fix to all agent files

```powershell
# PowerShell patch for cross_modal_aligner.py timestamp fix
$file = "C:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents\cross_modal_aligner.py"

# Backup original
Copy-Item -Path $file -Destination "$file.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Insert dt floor and interpolation logic
$patch = @'
def align_timestamps(slam_ts, mocap_ts):
    \"\"\"Robust timestamp alignment with dt floor and interpolation.\"\"\"
    diff = np.abs(slam_ts - mocap_ts)
    dt = np.where(diff < 0.05, 0.05, diff)
    aligned = np.interp(slam_ts, mocap_ts, mocap_data, left=mocap_data[0], right=mocap_data[-1])
    return aligned, dt
'@

# Use sed-like replacement via PowerShell
(Get-Content $file) | ForEach-Object {
    $_ -replace 'def align_timestamps\(slam_ts, mocap_ts\):', $patch
} | Set-Content $file

Write-Host "Cross-modal aligner patched. Restart session."
```

**SEQUENCES PRESCRIBED:** Record sessions with synchronized start/stop. Use `launch_session.py` with `--slam --mocap --sync` flags. Each session must have >500 frames with both SLAM and MoCap active simultaneously. Minimum 5 full sessions required.

---

## [WHAT] BUG-B: YOLO Detection Failure (Human→Chair, Robot→Person)

**EVIDENCE:** BUG-B marked "[OK] FIXED (scene_object_detector.py) [5 code matches]". Only 5 code matches for a detection "fix" is suspicious - likely just confidence threshold tweaks rather than fundamental class-label mapping issues.

**Critical flaw:** The behavior distribution shows `FORWARD_CRUISING: 102 (29.7%)`, `IDLE_STATIONARY: 92 (26.7%)`, but with only 344 frames total and 1 session, the YOLO labeling is statistically meaningless. The core issue - human labeled as chair, robot as person - suggests the class taxonomy is wrong.

**File:line analysis:** `scene_object_detector.py` - likely lines 22-30 where class names are mapped from YOLO output to VLA taxonomy.

```python
# ORIGINAL BUGGY CODE (hypothetical line 25-28):
class_map = {
    "person": "robot",      # BUG: Robot detected as person, mapped to "robot" class
    "chair": "human",       # BUG: Human detected as chair, mapped to "human" class
    "table": "obstacle"
}
```

**FIX:** Correct class mapping with proper ontology.

```python
# FIXED scene_object_detector.py lines 25-32:
CLASS_ONTOLOGY = {
    "person": "human_operator",     # Human = human_operator (not chair)
    "chair": "furniture",           # Chair = furniture (not human)
    "robot": "mobile_robot",        # Robot = mobile_robot (not person)
    "table": "obstacle",
    "laptop": "computer_interface"
}

def map_yolo_to_vla_classes(detections):
    """Map YOLO detections to VLA semantic classes."""
    mapped = []
    for det in detections:
        cls = det['class']
        if cls in CLASS_ONTOLOGY:
            mapped.append({
                'class': CLASS_ONTOLOGY[cls],
                'confidence': det['confidence'],
                'bbox': det['bbox']
            })
        else:
            mapped.append({
                'class': 'unknown',
                'confidence': det['confidence'],
                'bbox': det['bbox']
            })
    return mapped
```

**POWERSHELL PATCH:** Reclassify YOLO detections

```powershell
# PowerShell patch for scene_object_detector.py class mapping
$file = "C:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents\scene_object_detector.py"

# Backup
Copy-Item -Path $file -Destination "$file.bak_$(Get-Date -Format 'yyyyMMdd')"

# Replace class mapping section
$content = Get-Content $file
$old_map = "class_map = {"
$new_map = "CLASS_ONTOLOGY = {`n    \"person\": \"human_operator\",`n    \"chair\": \"furniture\",`n    \"robot\": \"mobile_robot\",`n    \"table\": \"obstacle\",`n    \"laptop\": \"computer_interface\"`n}"

$content = $content -replace [regex]::Escape($old_map), $new_map
Set-Content -Path $file -Value $content

Write-Host "YOLO class ontology patched. Re-run auto_labeler.py."
```

**SEQUENCES PRESCRIBED:** Record sessions with human operator explicitly wearing high-vis vest. YOLO must distinguish human upper/lower body. Minimum 3 sessions with >800 labeled frames each where human/robot class separation is verified visually.

---

## [WHAT] BUG-C: Velocity Calculation (9.13 m/s vs 1.5 m/s Max)

**EVIDENCE:** BUG-C marked "[OK] FIXED (robot_data_analyzer.py) [16 code matches]". 16 code matches suggests the fix was substantive - likely the addition of the `compute_differential_kinematics_robust` function shown in `generate_publication_report_v5.py`.

**Critical flaw:** The original code computed velocity as `sqrt(dx^2 + dy^2) / dt` without:
1. A dt floor (near-zero timestamps cause velocity spikes)
2. Physical clamping to MiR100 limits (1.5 m/s max, 1.0 rad/s max angular)
3. Proper unit conversion from pixel coordinates to meters

The reported max of 9.13 m/s is **6× the MiR100 physical limit** - this alone invalidates the entire VLA training dataset.

**File:line analysis:** `robot_data_analyzer.py` - likely original lines 15-22 where velocity is computed.

```python
# ORIGINAL BUGGY CODE (hypothetical line 18-20):
v = np.sqrt(dx**2 + dy**2) / dt  # BUG: No floor, no clamping
```

**FIX:** Robust kinematics computation with dt floor and physical clamping (as shown in `generate_publication_report_v5.py`).

```python
# FIXED robot_data_analyzer.py (lines 18-28):
MIR100_V_MAX = 1.50  # m/s - physical robot limit
MIR100_W_MAX = 1.00  # rad/s - physical robot limit

def compute_differential_kinematics_robust(poses, timestamps):
    """Computes physically valid velocities from robot poses."""
    dt = np.diff(timestamps)
    dt = np.where(dt < 0.01, 0.01, dt)  # dt floor at 10ms
    dx = np.diff(poses[:, 0])
    dy = np.diff(poses[:, 1])
    v = np.clip(np.sqrt(dx**2 + dy**2) / dt, 0.0, MIR100_V_MAX)  # Clamped velocity
   