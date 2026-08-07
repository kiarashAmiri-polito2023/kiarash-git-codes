#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cross_modal_aligner.py — FIXED v2.0
Fixes BUG-A: Robot was frozen at index [0] when MoCap timestamps exceeded SLAM range.
Now uses scipy linear interpolation with proper SO(2) angle unwrapping.
Original backup saved before this patch.
"""

import numpy as np
from scipy.interpolate import interp1d
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CORE FIX: Interpolation-based alignment (replaces pinned index [0])
# ============================================================

def match_slam_to_mocap_interpolated(mocap_timestamps, slam_timestamps, slam_poses):
    """
    Aligns SLAM poses to MoCap timestamps using linear interpolation.
    
    WHAT WAS WRONG (BUG-A):
        Old code used searchsorted + fallback to slam_poses[0], causing the robot
        to freeze at its initial position whenever MoCap timestamps exceeded SLAM range.
    
    WHAT THIS FIX DOES:
        1. Interpolates x, y linearly between SLAM keyframes
        2. Unwraps yaw angle before interpolation (prevents 2*pi jumps)
        3. Re-wraps yaw to [-pi, pi] after interpolation
        4. Clamps extrapolation to last known pose (not first!)
    
    Args:
        mocap_timestamps: np.array of MoCap timestamps (reference clock)
        slam_timestamps: np.array of SLAM timestamps
        slam_poses: np.array of shape (N, 3) — [x, y, yaw] per frame
    
    Returns:
        np.array of shape (M, 3) — interpolated [x, y, yaw] at each MoCap timestamp
    """
    mocap_timestamps = np.asarray(mocap_timestamps, dtype=np.float64)
    slam_timestamps = np.asarray(slam_timestamps, dtype=np.float64)
    slam_poses = np.asarray(slam_poses, dtype=np.float64)
    
    assert slam_poses.ndim == 2 and slam_poses.shape[1] >= 3, \
        f"slam_poses must be (N, 3+), got {slam_poses.shape}"
    assert len(slam_timestamps) == len(slam_poses), \
        f"SLAM timestamp/pose count mismatch: {len(slam_timestamps)} vs {len(slam_poses)}"
    
    if len(slam_timestamps) < 2:
        logger.warning("Only %d SLAM frames — cannot interpolate, repeating single pose", len(slam_timestamps))
        return np.tile(slam_poses[0, :3], (len(mocap_timestamps), 1))
    
    # 1. Interpolate Cartesian coordinates (x, y)
    interp_x = interp1d(
        slam_timestamps, slam_poses[:, 0],
        kind='linear',
        fill_value=(slam_poses[0, 0], slam_poses[-1, 0]),  # clamp to LAST, not first!
        bounds_error=False
    )
    interp_y = interp1d(
        slam_timestamps, slam_poses[:, 1],
        kind='linear',
        fill_value=(slam_poses[0, 1], slam_poses[-1, 1]),
        bounds_error=False
    )
    
    # 2. Unwrap yaw BEFORE interpolation (prevents 2*pi discontinuity = BUG-D root cause)
    yaw_unwrapped = np.unwrap(slam_poses[:, 2])
    interp_yaw = interp1d(
        slam_timestamps, yaw_unwrapped,
        kind='linear',
        fill_value=(yaw_unwrapped[0], yaw_unwrapped[-1]),
        bounds_error=False
    )
    
    # 3. Evaluate at MoCap timestamps
    aligned_x = interp_x(mocap_timestamps)
    aligned_y = interp_y(mocap_timestamps)
    aligned_yaw_raw = interp_yaw(mocap_timestamps)
    
    # 4. Re-wrap yaw to [-pi, pi]
    aligned_yaw = (aligned_yaw_raw + np.pi) % (2 * np.pi) - np.pi
    
    # 5. Log sync quality
    dt_edges = np.abs(mocap_timestamps[[0, -1]] - slam_timestamps[[0, -1]])
    if np.max(dt_edges) > 1.0:
        logger.warning(
            "Large time offset between SLAM and MoCap: %.3f s at start, %.3f s at end",
            dt_edges[0], dt_edges[1]
        )
    
    aligned = np.column_stack([aligned_x, aligned_y, aligned_yaw])
    logger.info(
        "Aligned %d MoCap frames to %d SLAM frames (dt_max=%.4f s)",
        len(mocap_timestamps), len(slam_timestamps), np.max(dt_edges)
    )
    
    return aligned


def compute_sync_quality(mocap_timestamps, slam_timestamps, max_gap=0.050):
    """
    Reports per-frame synchronization quality.
    
    Returns:
        dict with keys: 'mean_gap', 'max_gap', 'n_violations', 'quality_score'
    """
    mocap_t = np.asarray(mocap_timestamps)
    slam_t = np.asarray(slam_timestamps)
    
    # Find nearest SLAM frame for each MoCap frame
    idx = np.searchsorted(slam_t, mocap_t)
    idx = np.clip(idx, 1, len(slam_t) - 1)
    
    # Check both neighbors
    gap_right = np.abs(slam_t[idx] - mocap_t)
    gap_left = np.abs(slam_t[idx - 1] - mocap_t)
    gap = np.minimum(gap_right, gap_left)
    
    n_violations = int(np.sum(gap > max_gap))
    quality = 1.0 - (n_violations / max(1, len(mocap_t)))
    
    result = {
        'mean_gap': float(np.mean(gap)),
        'max_gap': float(np.max(gap)),
        'n_violations': n_violations,
        'total_frames': len(mocap_t),
        'quality_score': float(quality),
        'max_allowed_gap': max_gap
    }
    
    logger.info("Sync quality: %.1f%% (mean_gap=%.4f s, violations=%d/%d)",
                quality * 100, result['mean_gap'], n_violations, len(mocap_t))
    
    return result


# ============================================================
# BACKWARD COMPATIBILITY: Old function name redirects to new
# ============================================================

def match_slam_to_mocap(mocap_timestamps, slam_data):
    """
    Backward-compatible wrapper. Old code called this with slam_data dict.
    Now redirects to the interpolation-based version.
    """
    logger.warning("DEPRECATED: match_slam_to_mocap() called. Use match_slam_to_mocap_interpolated().")
    
    if isinstance(slam_data, dict):
        slam_ts = np.asarray(slam_data.get("timestamps", slam_data.get("t", [])))
        slam_poses = np.asarray(slam_data.get("poses", slam_data.get("pose", [])))
    else:
        raise TypeError(f"Expected dict for slam_data, got {type(slam_data)}")
    
    return match_slam_to_mocap_interpolated(mocap_timestamps, slam_ts, slam_poses)
