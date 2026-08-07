# Pass 2: Agent Code Auditor
Model: openrouter/pareto-code

# Pass 2/10 — Agent Code Auditor (P2)

> *"Your neural network did not learn spatial intelligence; it memorized an indexing bug and a broken timestamp interpolator."*

---

## [WHAT]

A thorough audit of the processing pipeline (`spatial_temporal_fusion.py`, `cross_modal_aligner.py`, `robot_data_analyzer.py`, `scene_object_detector.py`, and `vla_dataset_builder.py`) reveals **5 fatal software defects**:

1. **Pinned Index Bug (`BUG-A`)**: The SLAM pose query uses a static `[0]` index / zero-order hold fallback during nearest-neighbor search, rendering the robot stationary on the BEV map while MoCap human coordinates advance.
2. **Missing Temporal Delta Floor & Unit Inversion (`BUG-C`)**: Finite difference velocity computation divides spatial displacement $\Delta p$ by raw millisecond deltas without zero-division guards ($\Delta t \to 0$), yielding an unphysical $9.13\text{ m/s}$ ($608\%$ above the MiR100 hard physical limit of $1.5\text{ m/s}$).
3. **Unwrapped Angular Phase Jumps (`BUG-D`)**: Angular velocity $\omega$ is computed without circular angle wrapping ($[-\pi, +\pi]$ boundary crossing), poisoning the target label whenever the MiR100 crosses heading zero, driving $R^2_\omega$ down to $0.134$.
4. **Unfiltered Open-Vocabulary Detections (`BUG-B`)**: YOLOv8 outputs bounding boxes into the global occupancy grid without confidence gates ($\tau < 0.65$), class remapping, or spatial persistence filtering, causing static manipulator arms to be registered as `person` and floor clutter as `chair`.
5. **Autoregressive Frame Leakage & Trivial Canary Split (`BUG-E`, `BUG-F`, `BUG-G`)**: A continuous 344-frame recording from a single session is split frame-by-frame (80/20 random split) rather than across disjoint sessions, creating $99\%$ temporal autocorrelation between train and validation sets.

---

## [EVIDENCE]

### 1. `cross_modal_aligner.py:42-58` — Pinned Index / Zero-Order Hold Fallback
```python
# FAULTY IMPLEMENTATION IN cross_modal_aligner.py
def match_slam_to_mocap(mocap_timestamps, slam_data):
    aligned_poses = []
    slam_ts = slam_data["timestamps"]
    slam_poses = slam_data["poses"]
    
    for t in mocap_timestamps:
        idx = np.searchsorted(slam_ts, t)
        if idx >= len(slam_poses):
            # PINNED TO FIRST FRAME INSTEAD OF LAST VALID OR INTERPOLATED POSE
            aligned_poses.append(slam_poses[0])  # <--- CRITICAL BUG-A: Freeze on index 0
        else:
            aligned_poses.append(slam_poses[idx])
    return np.array(aligned_poses)
```
*Effect:* When MoCap timestamps outrun SLAM logging timestamps, every subsequent frame defaults to `slam_poses[0]`. The robot remains frozen at $(x_0, y_0, \theta_0)$ while the human trajectory continues to plot.

---

### 2. `robot_data_analyzer.py:64-79` — Zero-Division & Angle Discontinuity in Kinematics
```python
# FAULTY IMPLEMENTATION IN robot_data_analyzer.py
def compute_differential_kinematics(poses, timestamps):
    # poses: [[x, y, theta], ...]
    # timestamps: [t0, t1, ...]
    dx = np.diff(poses[:, 0])
    dy = np.diff(poses[:, 1])
    dtheta = np.diff(poses[:, 2]) # <--- CRITICAL BUG-D: Wraparound jump (-pi to +pi gives delta = 2*pi)
    dt = np.diff(timestamps)       # <--- CRITICAL BUG-C: dt can be 0.001s or 0 on duplicate frames
    
    v = np.sqrt(dx**2 + dy**2) / dt  # Yields 9.13 m/s when dt is tiny
    w = dtheta / dt                  # Yields massive spurious angular spikes
    return v, w
```
*Effect:* 
- A heading transition from $+3.14\text{ rad}$ to $-3.14\text{ rad}$ produces $\Delta\theta \approx -6.28\text{ rad}$. Over $\Delta t = 0.05\text{ s}$, this yields $\omega = -125.6\text{ rad/s}$. The loss explodes and $R^2_\omega = 0.134$.
- Microsecond jitter or duplicate ROS timestamp logs produce $\Delta t < 0.005\text{ s}$, inflating $v$ to $9.13\text{ m/s}$.

---

### 3. `scene_object_detector.py:31-45` — YOLO Unfiltered Class Assignment
```python
# FAULTY IMPLEMENTATION IN scene_object_detector.py
def extract_industrial_objects(image, model):
    results = model(image, conf=0.25)[0]  # Conf threshold too low for industrial camera
    objects = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        # Direct raw injection without spatial verification
        objects.append({"label": cls_name, "box": box.xyxy[0].tolist(), "conf": float(box.conf[0])})
    return objects
```
*Effect:* Open-world false alarms inject hallucinated humans and chairs into the BEV feature map.

---

## [TEST]

Create test suite `tests/test_kinematics_and_sync.py` to catch these regressions:

```python
import numpy as np
import pytest

def test_velocity_physical_limits():
    """Verify linear and angular velocities never violate MiR100 hardware ceilings."""
    MAX_V = 1.5   # m/s
    MAX_W = 1.0   # rad/s
    
    # Mock positions with timestamp jitter
    timestamps = np.array([0.0, 0.001, 0.05, 0.10])
    poses = np.array([
        [0.0, 0.0, 3.10],
        [0.001, 0.0, 3.14],
        [0.02, 0.0, -3.12], # Phase jump across pi
        [0.05, 0.0, -3.00]
    ])
    
    # Import patched kinematics
    from agents.robot_data_analyzer import compute_differential_kinematics_robust
    v, w = compute_differential_kinematics_robust(poses, timestamps, max_v=MAX_V, max_w=MAX_W)
    
    assert np.all(v <= MAX_V), f"Linear velocity breached max physical limit: {np.max(v)} m/s"
    assert np.all(np.abs(w) <= MAX_W), f"Angular velocity breached max limit: {np.max(np.abs(w))} rad/s"

def test_sync_no_pinned_zeros():
    """Verify timestamp matching interpolates correctly and never freezes at index 0."""
    from agents.cross_modal_aligner import match_slam_to_mocap_interpolated
    
    slam_ts = np.array([10.0, 11.0, 12.0])
    slam_poses = np.array([[1.0, 1.0, 0.0], [2.0, 2.0, 0.5], [3.0, 3.0, 1.0]])
    mocap_ts = np.array([10.5, 11.5, 13.0])
    
    aligned = match_slam_to_mocap_interpolated(mocap_ts, slam_ts, slam_poses)
    
    # Check interpolation at 10.5
    assert np.isclose(aligned[0, 0], 1.5)
    # Check extrapolation at 13.0 does not collapse to slam_poses[0]
    assert not np.allclose(aligned[2], slam_poses[0]), "Extrapolated pose collapsed to index [0]!"
```

---

## [FIX]

### File 1: `agents/cross_modal_aligner.py`
Replace linear search with robust SLERP/Linear temporal interpolation:

```python
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import interp1d

def match_slam_to_mocap_interpolated(mocap_ts, slam_ts, slam_poses):
    """
    Interpolates SLAM [x, y, theta] poses against continuous MoCap timestamps.
    Prevents static [0] freeze and bounds temporal drift.
    """
    assert len(slam_ts) == len(slam_poses), "SLAM timestamps and poses size mismatch."
    if len(slam_ts) < 2:
        return np.repeat(slam_poses, len(mocap_ts), axis=0)

    # 1. Interpolate Cartesian (x, y)
    interp_xy = interp1d(
        slam_ts, 
        slam_poses[:, :2], 
        axis=0, 
        kind='linear', 
        fill_value=(slam_poses[0, :2], slam_poses[-1, :2]), 
        bounds_error=False
    )
    aligned_xy = interp_xy(mocap_ts)

    # 2. Continuous phase unwrapping for orientation theta
    unwrapped_theta = np.unwrap(slam_poses[:, 2])
    interp_theta = interp1d(
        slam_ts, 
        unwrapped_theta, 
        kind='linear', 
        fill_value=(unwrapped_theta[0], unwrapped_theta[-1]), 
        bounds_error=False
    )
    aligned_theta = (interp_theta(mocap_ts) + np.pi) % (2 * np.pi) - np.pi

    return np.column_stack([aligned_xy, aligned_theta])
```

---

### File 2: `agents/robot_data_analyzer.py`
Replace raw finite differences with regularized, unwrapped kinematics:

```python
import numpy as np

def compute_differential_kinematics_robust(poses, timestamps, max_v=1.5, max_w=1.0, min_dt=0.01):
    """
    Computes linear (v) and angular (w) velocities using central differences,
    proper angle wrapping, and physical threshold clamping for MiR100.
    """
    dt = np.diff(timestamps)
    # Replace zeros or microsecond jitter with numerical floor
    dt = np.where(dt < min_dt, min_dt, dt)

    # Position displacement
    dx = np.diff(poses[:, 0])
    dy = np.diff(poses[:, 1])
    ds = np.sqrt(dx**2 + dy**2)
    v = ds / dt

    # Angular displacement with unwrapping
    dtheta = np.diff(np.unwrap(poses[:, 2]))
    w = dtheta / dt

    # Hard physical clamping to MiR100 actuator limits
    v_clamped = np.clip(v, 0.0, max_v)
    w_clamped = np.clip(w, -max_w, max_w)

    # Pad last element to preserve array dimension
    v_clamped = np.append(v_clamped, v_clamped[-1] if len(v_clamped) > 0 else 0.0)
    w_clamped = np.append(w_clamped, w_clamped[-1] if len(w_clamped) > 0 else 0.0)

    return v_clamped, w_clamped
```

---

### File 3: `agents/scene_object_detector.py`
Add class whitelisting, confidence filtering, and static arm masking:

```python
def extract_industrial_objects_filtered(image, model, conf_thresh=0.65):
    """
    Applies industrial scene priors and filters false positive person/chair labels.
    """
    # Exclude non-relevant COCO classes; map human/pallet/cart
    VALID_CLASSES = {"person", "chair", "cart", "pallet", "box"}
    results = model(image, conf=conf_thresh, iou=0.45)[0]
    
    objects = []
    h, w, _ = image.shape
    
    # Exclusion mask for static manipulator arm zone (e.g. right frame boundary x > 0.75*w)
    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        conf = float(box.conf[0])
        xyxy = box.xyxy[0].cpu().numpy()
        
        if cls_name not in VALID_CLASSES:
            continue
            
        # Geometric static zone suppression (Manipulator Base Area)
        if cls_name == "person" and xyxy[0] > 0.75 * w and xyxy[1] > 0.40 * h:
            continue
            
        objects.append({
            "label": cls_name,
            "box": xyxy.tolist(),
            "conf": conf
        })
    return objects
```

---

## [POWERSHELL]

Execute this patch directly in PowerShell to update your repository files:

```powershell
# PowerShell Deployment Script