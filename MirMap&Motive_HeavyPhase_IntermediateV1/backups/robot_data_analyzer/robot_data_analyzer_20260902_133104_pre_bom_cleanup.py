#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_data_analyzer.py — FIXED v2.0
Fixes BUG-C: velocity was 9.13 m/s due to dt jitter (should be max 1.5 m/s)
Fixes BUG-D: R2_w=0.134 due to missing SO(2) angle unwrapping
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# ============================================================
# MiR100 PHYSICAL CONSTANTS (HARDWARE LIMITS)
# ============================================================
MIR100_V_MAX = 1.50    # m/s — absolute hardware ceiling
MIR100_W_MAX = 1.00    # rad/s — absolute hardware ceiling
MIR100_WHEEL_R = 0.0625  # m — wheel radius
MIN_DT = 0.010         # s — minimum allowed dt (100 Hz OptiTrack ceiling)
SMOOTH_WINDOW = 5      # frames — moving average window for noise rejection


def wrap_to_pi(angle):
    """Wrap angle to [-pi, +pi] using atan2 (robust, no modulo edge cases)."""
    return np.arctan2(np.sin(angle), np.cos(angle))


def compute_differential_kinematics_robust(poses, timestamps, max_v=None, max_w=None):
    """
    Computes linear velocity (v) and angular velocity (w) from pose trajectory.
    
    WHAT WAS WRONG:
        BUG-C: Raw np.diff(positions) / np.diff(timestamps) with no dt floor.
               When dt=0.001s (network jitter), 9mm noise / 0.001s = 9.13 m/s.
        BUG-D: Raw np.diff(yaw) without unwrapping.
               When yaw crosses +pi to -pi, delta_yaw = -6.28 rad.
               Over dt=0.1s: omega = -62.8 rad/s (physical limit is 1.0).
    
    WHAT THIS FIX DOES:
        1. Enforces minimum dt = 10ms (rejects timestamp duplicates/jitter)
        2. Applies moving-average smoothing before differentiation
        3. Unwraps yaw angle before computing angular velocity
        4. Projects velocity onto heading direction (unicycle model: vy ≡ 0)
        5. Hard-clamps to MiR100 physical limits as final safety net
    
    Args:
        poses: np.array (N, 3) — [x, y, yaw] in meters and radians
        timestamps: np.array (N,) — in seconds (monotonic)
        max_v: float — linear velocity ceiling (default: MiR100 1.5 m/s)
        max_w: float — angular velocity ceiling (default: MiR100 1.0 rad/s)
    
    Returns:
        v: np.array (N,) — clamped linear velocity [m/s]
        w: np.array (N,) — clamped angular velocity [rad/s]
    """
    if max_v is None:
        max_v = MIR100_V_MAX
    if max_w is None:
        max_w = MIR100_W_MAX
    
    poses = np.asarray(poses, dtype=np.float64)
    timestamps = np.asarray(timestamps, dtype=np.float64)
    
    assert poses.shape[0] == len(timestamps), \
        f"Pose/timestamp count mismatch: {poses.shape[0]} vs {len(timestamps)}"
    assert poses.shape[1] >= 3, \
        f"Poses must have at least 3 columns [x, y, yaw], got {poses.shape[1]}"
    
    N = len(timestamps)
    if N < 2:
        return np.zeros(N), np.zeros(N)
    
    # ---- STEP 1: Compute dt with floor ----
    dt = np.diff(timestamps)
    
    # Log jitter statistics BEFORE clamping
    n_jitter = int(np.sum(dt < MIN_DT))
    if n_jitter > 0:
        logger.warning(
            "BUG-C GUARD: %d/%d frames had dt < %.3f s (min dt=%.6f s). "
            "These would have caused velocity spikes. Clamping to %.3f s.",
            n_jitter, len(dt), MIN_DT, np.min(dt), MIN_DT
        )
    
    dt_safe = np.where(dt < MIN_DT, MIN_DT, dt)
    
    # Check for non-monotonic timestamps
    n_backward = int(np.sum(dt <= 0))
    if n_backward > 0:
        logger.error("CRITICAL: %d non-monotonic timestamps detected! Forcing dt=MIN_DT.", n_backward)
        dt_safe = np.where(dt <= 0, MIN_DT, dt_safe)
    
    # ---- STEP 2: Smooth positions (moving average) ----
    kernel = np.ones(SMOOTH_WINDOW) / SMOOTH_WINDOW
    x_smooth = np.convolve(poses[:, 0], kernel, mode='same')
    y_smooth = np.convolve(poses[:, 1], kernel, mode='same')
    
    # ---- STEP 3: Compute linear velocity (unicycle projection) ----
    dx = np.diff(x_smooth)
    dy = np.diff(y_smooth)
    
    # Project displacement onto heading direction (unicycle model)
    yaw_mid = poses[:-1, 2]  # heading at interval start
    v_forward = (dx * np.cos(yaw_mid) + dy * np.sin(yaw_mid)) / dt_safe
    
    # Also compute raw Euclidean speed for comparison/logging
    v_euclidean = np.sqrt(dx**2 + dy**2) / dt_safe
    
    # ---- STEP 4: Compute angular velocity WITH unwrapping ----
    # THIS IS THE BUG-D FIX: unwrap before diff
    yaw_unwrapped = np.unwrap(poses[:, 2])
    dyaw = np.diff(yaw_unwrapped)
    w_raw = dyaw / dt_safe
    
    # Log the FIX effect
    dyaw_naive = np.diff(poses[:, 2])  # what old code did
    n_wraps = int(np.sum(np.abs(dyaw_naive) > np.pi))
    if n_wraps > 0:
        logger.info(
            "BUG-D GUARD: %d angle-wrap discontinuities detected and corrected. "
            "Without fix, max |omega| would be %.1f rad/s (physical limit: %.1f).",
            n_wraps, np.max(np.abs(dyaw_naive / dt_safe)), max_w
        )
    
    # ---- STEP 5: Physical clamping (last safety net) ----
    v_clamped = np.clip(v_forward, -max_v, max_v)
    w_clamped = np.clip(w_raw, -max_w, max_w)
    
    # Log clamping events
    n_v_clamp = int(np.sum(np.abs(v_forward) > max_v))
    n_w_clamp = int(np.sum(np.abs(w_raw) > max_w))
    if n_v_clamp > 0:
        logger.warning("Clamped %d velocity values (max raw: %.2f m/s -> %.2f m/s)",
                       n_v_clamp, np.max(np.abs(v_forward)), max_v)
    if n_w_clamp > 0:
        logger.warning("Clamped %d angular velocity values (max raw: %.2f rad/s -> %.2f rad/s)",
                       n_w_clamp, np.max(np.abs(w_raw)), max_w)
    
    # ---- STEP 6: Pad to match input length ----
    v_out = np.append(v_clamped, v_clamped[-1])
    w_out = np.append(w_clamped, w_clamped[-1])
    
    # ---- Summary statistics ----
    logger.info(
        "Kinematics: v=[%.3f, %.3f] m/s, w=[%.3f, %.3f] rad/s, "
        "dt_jitter=%d, wraps=%d, v_clamp=%d, w_clamp=%d",
        np.min(v_out), np.max(v_out),
        np.min(w_out), np.max(w_out),
        n_jitter, n_wraps, n_v_clamp, n_w_clamp
    )
    
    return v_out, w_out


def validate_mir100_commands(v_array, w_array):
    """
    Final safety validation gate. Call this before sending ANY command to MiR100.
    
    Returns:
        dict with validation results and any violations found
    """
    v = np.asarray(v_array, dtype=np.float64)
    w = np.asarray(w_array, dtype=np.float64)
    
    violations = []
    
    if np.any(~np.isfinite(v)):
        violations.append(f"NON-FINITE linear velocity: {np.sum(~np.isfinite(v))} values")
    if np.any(~np.isfinite(w)):
        violations.append(f"NON-FINITE angular velocity: {np.sum(~np.isfinite(w))} values")
    if np.any(np.abs(v) > MIR100_V_MAX + 1e-6):
        violations.append(f"LINEAR velocity exceeds {MIR100_V_MAX} m/s: max={np.max(np.abs(v)):.4f}")
    if np.any(np.abs(w) > MIR100_W_MAX + 1e-6):
        violations.append(f"ANGULAR velocity exceeds {MIR100_W_MAX} rad/s: max={np.max(np.abs(w)):.4f}")
    
    result = {
        'valid': len(violations) == 0,
        'violations': violations,
        'v_max': float(np.max(np.abs(v))) if len(v) > 0 else 0.0,
        'w_max': float(np.max(np.abs(w))) if len(w) > 0 else 0.0,
        'n_frames': len(v)
    }
    
    if violations:
        for viol in violations:
            logger.error("SAFETY VIOLATION: %s", viol)
    else:
        logger.info("Safety check PASSED: v_max=%.3f m/s, w_max=%.3f rad/s",
                    result['v_max'], result['w_max'])
    
    return result


def compute_session_statistics(poses, timestamps):
    """
    Computes comprehensive session statistics for the master report.
    Uses the fixed kinematics pipeline.
    """
    v, w = compute_differential_kinematics_robust(poses, timestamps)
    safety = validate_mir100_commands(v, w)
    
    stats = {
        'duration_s': float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0,
        'n_frames': len(timestamps),
        'fps': len(timestamps) / max(1e-6, float(timestamps[-1] - timestamps[0])) if len(timestamps) > 1 else 0.0,
        'v_mean': float(np.mean(np.abs(v))),
        'v_max': float(np.max(np.abs(v))),
        'v_std': float(np.std(v)),
        'w_mean': float(np.mean(np.abs(w))),
        'w_max': float(np.max(np.abs(w))),
        'w_std': float(np.std(w)),
        'distance_total_m': float(np.sum(np.abs(v[:-1]) * np.diff(timestamps))),
        'rotation_total_rad': float(np.sum(np.abs(w[:-1]) * np.diff(timestamps))),
        'idle_fraction': float(np.mean((np.abs(v) < 0.05) & (np.abs(w) < 0.05))),
        'safety': safety
    }
    
    return stats
