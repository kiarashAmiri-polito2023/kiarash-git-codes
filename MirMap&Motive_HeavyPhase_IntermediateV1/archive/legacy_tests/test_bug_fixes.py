#!/usr/bin/env python3
"""Verification tests for BUG-A, BUG-C, BUG-D fixes."""
import numpy as np
import sys

print("=" * 60)
print(" VERIFICATION TESTS FOR BUG FIXES")
print("=" * 60)

errors = []

# ---- TEST 1: BUG-A — Robot should NOT freeze at index 0 ----
print("\n[TEST 1] BUG-A: Robot freeze fix...")
try:
    sys.path.insert(0, r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents")
    from cross_modal_aligner import match_slam_to_mocap_interpolated
    
    slam_ts = np.array([10.0, 11.0, 12.0, 13.0])
    slam_poses = np.array([
        [1.0, 1.0, 0.0],
        [2.0, 2.0, 0.5],
        [3.0, 3.0, 1.0],
        [4.0, 4.0, 1.5]
    ])
    mocap_ts = np.array([10.5, 11.5, 12.5, 14.0])  # 14.0 is BEYOND SLAM range
    
    aligned = match_slam_to_mocap_interpolated(mocap_ts, slam_ts, slam_poses)
    
    # Check interpolation at 10.5 (should be between pose[0] and pose[1])
    assert abs(aligned[0, 0] - 1.5) < 0.01, f"Interpolation failed: x={aligned[0, 0]}, expected 1.5"
    
    # CRITICAL: Check that extrapolation at 14.0 does NOT collapse to slam_poses[0]
    assert not np.allclose(aligned[3], slam_poses[0]), \
        f"BUG-A STILL PRESENT: pose at t=14.0 collapsed to index [0]! Got {aligned[3]}"
    
    # Should clamp to LAST known pose
    assert abs(aligned[3, 0] - 4.0) < 0.01, f"Extrapolation wrong: x={aligned[3, 0]}, expected 4.0"
    
    print("  PASSED: Robot no longer freezes at index [0]")
except Exception as e:
    errors.append(f"TEST 1 FAILED: {e}")
    print(f"  FAILED: {e}")

# ---- TEST 2: BUG-C — Velocity must not exceed 1.5 m/s ----
print("\n[TEST 2] BUG-C: Velocity physical limit...")
try:
    from robot_data_analyzer import compute_differential_kinematics_robust
    
    # Simulate network jitter: 9mm displacement in 1ms
    timestamps = np.array([0.0, 0.001, 0.05, 0.10, 0.15])
    poses = np.array([
        [0.0, 0.0, 0.0],
        [0.009, 0.0, 0.0],   # 9mm jump in 1ms = old bug gave 9.13 m/s
        [0.02, 0.0, 0.1],
        [0.05, 0.0, 0.2],
        [0.08, 0.0, 0.3]
    ])
    
    v, w = compute_differential_kinematics_robust(poses, timestamps)
    
    assert np.max(np.abs(v)) <= 1.5 + 1e-6, \
        f"BUG-C STILL PRESENT: v_max={np.max(np.abs(v)):.2f} m/s exceeds 1.5 m/s!"
    
    print(f"  PASSED: v_max = {np.max(np.abs(v)):.4f} m/s (limit: 1.5)")
except Exception as e:
    errors.append(f"TEST 2 FAILED: {e}")
    print(f"  FAILED: {e}")

# ---- TEST 3: BUG-D — Angular velocity at pi boundary ----
print("\n[TEST 3] BUG-D: Angle wrapping at pi boundary...")
try:
    from robot_data_analyzer import compute_differential_kinematics_robust
    
    timestamps = np.array([0.0, 0.1, 0.2, 0.3])
    poses = np.array([
        [0.0, 0.0, 3.10],     # near +pi
        [0.01, 0.0, 3.14],    # at +pi
        [0.02, 0.0, -3.12],   # crossed to -pi (OLD BUG: delta = -6.26 rad!)
        [0.03, 0.0, -3.00]
    ])
    
    v, w = compute_differential_kinematics_robust(poses, timestamps)
    
    assert np.max(np.abs(w)) <= 1.0 + 1e-6, \
        f"BUG-D STILL PRESENT: w_max={np.max(np.abs(w)):.2f} rad/s exceeds 1.0!"
    
    # The actual angular change from 3.14 to -3.12 is only about 0.02 rad
    # (going through pi), NOT 6.26 rad
    print(f"  PASSED: w_max = {np.max(np.abs(w)):.4f} rad/s (limit: 1.0)")
except Exception as e:
    errors.append(f"TEST 3 FAILED: {e}")
    print(f"  FAILED: {e}")

# ---- SUMMARY ----
print("\n" + "=" * 60)
if errors:
    print(f" RESULT: {len(errors)} TEST(S) FAILED!")
    for e in errors:
        print(f"   {e}")
    sys.exit(1)
else:
    print(" ALL 3 TESTS PASSED — BUGS A, C, D ARE FIXED!")
    sys.exit(0)
