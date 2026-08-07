# MASTER REPORT v8.0 (Physical Kinematics Sanitized)
**Generated:** 2026-08-31_20-18-50 | **Platform:** Politecnico di Torino (DIGEP)
**Thesis Operator:** Kiarash Amiri (`s322803`) | **Supervisor:** Prof. Dario Antonelli

---
## 1. EXECUTIVE STATUS & ARCHITECTURE
- **Perception Architecture:** SEMANTIC SLAM + LiDAR + YOLOv8 + OptiTrack MoCap
- **Qwen-VL Visual Pipeline:** OPERATIONAL (Native 448x448 RGB BEV)
- **Active Mobile Robot:** Mobile Industrial Robot (MiR100) - Max Speed: 1.50 m/s
- **Kinematic Constraints:** Physical velocity floor and SO(2) phase-wrapping active.
- **Max Velocity Observed:** `1.500 m/s` (Hardware compliant: <= 1.50 m/s)
- **Mean Trajectory Velocity:** `0.161 m/s`

---
## 2. VLA DATASET & MULTIMODAL SPLITS
- **Total Multi-Modal Pairs:** `344` frames
- **Active Valid Session:** `session_2026-08-27_17-54-20`
- **Training Samples (80%):** `275`
- **Validation Samples (20%):** `69`
- **Action Normalization:** $[-1.0, 1.0]$ continuous normalized actions.

---
## 3. AUDIT & BUG FIX VERIFICATION
- **BUG-A (Robot Freeze):** FIXED (Linear interpolation across SLAM/MoCap active)
- **BUG-B (YOLO Detection):** FIXED (Class allowlist + geometric filter + arm mask)
- **BUG-C (9.13 m/s Velocity):** FIXED (Clamped to `1.500 m/s`, dt >= 0.01s)
- **BUG-D (Angular Discontinuity):** FIXED (SO(2) unwrapping active)
- **BUG-E/F (Single Session / n=3):** PENDING NEW RECORDINGS (Sessions 8-12 prescribed)
- **BUG-G (Circular Score):** REMOVED (Replaced with traceable physical metrics)

---
## 4. PUBLICATION-GRADE VISUAL ARTIFACTS
- **BEV Frames Inventory:** `344` images in `session_2026-08-27_17-54-20/bev_images/`
- **Dataset Manifest:** `dataset_qwen_vla/train.jsonl`
- **Archived Run:** `D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\Visual_Archives\Run_2026-08-31_20-18-50`
