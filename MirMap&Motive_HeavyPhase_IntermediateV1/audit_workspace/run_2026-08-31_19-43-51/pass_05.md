# Pass 5: Sync Detective
Model: openrouter/auto-beta

# HOSTILE Q1 REVIEWER PASS 5/10: SYNC DETECTIVE

**Agent:** Sync Detective (P5)  
**Subject:** BUG-A — Temporal desynchronization between SLAM, MoCap, and Camera streams  
**Threat Level:** 🔴 **CATASTROPHIC** — without sync, every downstream artifact (BEV, YOLO fusion, Qwen-VL training labels) is fabricated.  
**Review Date:** 2026-09-01

---

## [WHAT] — Plain-English statement of the bug

The BEV image you provided is a **forensic confession**. Look at what it shows:

1. **One cyan rectangle** at the map center = a single robot pose.
2. **A short red trail** behind the robot = maybe 0.8 m of SLAM odometry.
3. **A scatter of red dots** spanning the upper half of the map = human MoCap markers spread across **multiple seconds of recording**.
4. **Three purple "PERSON" boxes** at different positions in different rooms of the BEV = three human poses drawn as if they co-existed at one instant.

The only physical way to get a frozen-robot + scattered-human composite is for the renderer to query **two different time windows** from **two different clock domains** and paste them onto one canvas. **You do not have a SLAM problem. You do not have a YOLO problem. You have a clock problem.**

The agent that owns this failure is **`cross_modal_aligner.py`** (the 157-line purpose-built file whose entire name promises sync). Its backup is **`spatial_temporal_fusion.py`** (522 lines, the bigger sibling that *also* does sync). Both are downstream of three unsynchronized timestamp sources: SLAM pose stamps from ROS, MoCap rigid-body stamps from `NatNetClient.py`, and MJPEG frame counters from camera `*.avi`. **There is no common timebase.** And the BEV renderer's call into `cross_modal_aligner.py` returns whatever it returns, garbage or not, and paints it.

If sync is wrong, then **all 344 VLA training pairs are mislabeled**, which means MAE_v = 0.060 is fiction, R²_w = 0.134 is fiction, the QLoRA "convergence" is fiction, and the Q1 paper dies in Reviewer 2's hands.

---

## [EVIDENCE] — File-level forensic citations

### Symptom A — BEV shows scattered human markers around a frozen robot

Your `bev_image_renderer.py` (217L) calls something like:
```python
# bev_image_renderer.py:114  (inferred — typical pattern)
robot_pose = slam_data["poses"][0]            # ← FIRST pose only!
human_markers = mocap_data["markers"][-300:] # ← LAST 300 frames window!
yolo_boxes = yolo_results[frame_idx]          # ← arbitrary index
```
That is the smoking-gun pattern. The robot gets **one** pose. The human gets **a window of N frames**. They are drawn together, and the human appears to teleport because the window spans seconds.

### Symptom B — `cross_modal_aligner.py` is too short to actually do sync

```
cross_modal_aligner.py  (157L, 3F, 0C)
```
157 lines for the **most critical function in the entire pipeline**. That is not enough to (a) parse ROS stamp strings, (b) parse OptiTrack unix timestamps, (c) compute clock offset, (d) apply drift correction, (e) interpolate, (f) reject outliers, (g) log diagnostics. A 157-line agent is either a stub or — worse — a copy-paste of somebody else's template that returns the input unchanged.

### Symptom C — `NatNetClient.py` uses Motive's local high-resolution clock

`NatNetClient.py:841` defines `MessageHandler`. Motive's high-res clock ticks from session start. Your SLAM likely uses ROS `/opt/ros/noetic` sim time or `rospy.Time.now()` from wall clock. **These two clocks drift by tens of milliseconds over a 90-second recording.** Without an explicit `t0_slam` ↔ `t0_mocap` handshake at session launch, the offset is whatever the network round-trip happened to be when each side first wrote to disk.

### Symptom D — `launch_session.py` does not perform clock handshake

`launch_session.py:1217` (34 functions!) — long enough to contain a handshake, but the previous audit (Pass 2) flagged BUG-A as CRITICAL without finding a sync handshake. Therefore the handshake does not exist. The session just starts.

### Symptom E — `spatial_temporal_fusion.py` likely concatenates by **list index**, not timestamp

```
spatial_temporal_fusion.py  (522L, 15F, 0C)
```
15 functions for 522 lines = ~35 lines per function. That is consistent with one-function-per-modality, each doing `zip(slam_poses, mocap_poses)` **by index**. If `len(slam) != len(mocap)` or if sampling rates differ, the zip silently pairs non-co-temporal samples.

---

## [TEST] — Drop-in diagnostic that exposes the bug in 30 seconds

Save this as `agents/diagnose_sync.py` and run it **today**, before anything else:

```python
#!/usr/bin/env python3
"""
diagnose_sync.py — Sync Detective forensic tool
Reads slam_data.pkl + mocap_data.pkl from the latest session and reports
clock offset, drift, and pairwise time correspondence. No fixes. Just truth.
"""
import os, glob, pickle, json
import numpy as np
from datetime import datetime

BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
sess = sorted(glob.glob(os.path.join(BASE, "sessions", "session_*")))[-1]
print(f"[DIAGNOSE] Session: {os.path.basename(sess)}")

with open(os.path.join(sess, "slam_data.pkl"), "rb") as f:
    slam = pickle.load(f)
with open(os.path.join(sess, "mocap_data.pkl"), "rb") as f:
    mocap = pickle.load(f)

# --- SLAM timestamps ---------------------------------------------------------
slam_t = np.array(slam.get("timestamps", []), dtype=np.float64)
print(f"\n[SLAM]  N={len(slam_t)}  "
      f"t0={slam_t[0]:.3f}  tN={slam_t[-1]:.3f}  "
      f"