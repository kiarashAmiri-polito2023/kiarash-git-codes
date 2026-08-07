#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vla_dataset_builder.py — Fully Adaptive Multi-Modal Dataset Builder
Recursively finds BEV images and adapts to any slam_data format.
"""
import os
import sys
import glob
import json
import pickle
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

V_MAX = 1.50   # m/s
W_MAX = 1.00   # rad/s

def find_bev_images(session_dir):
    """Recursively finds all BEV png images in any subfolder or session root."""
    pngs = []
    for root, _, files in os.walk(session_dir):
        for f in files:
            if f.lower().endswith('.png') and ('bev' in f.lower() or 'bev' in root.lower() or 'frame' in f.lower() or 'map' in f.lower()):
                pngs.append(os.path.join(root, f))
    if not pngs:
        # Fallback to any png
        for root, _, files in os.walk(session_dir):
            for f in files:
                if f.lower().endswith('.png'):
                    pngs.append(os.path.join(root, f))
    return sorted(list(set(pngs)))

def extract_kinematics(session_dir, n_frames):
    """Robustly extracts or calculates physical velocity profiles."""
    slam_file = os.path.join(session_dir, "slam_data.pkl")
    poses, timestamps = None, None
    
    if os.path.exists(slam_file):
        try:
            with open(slam_file, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                # Try all common keys
                if "x" in data and "y" in data:
                    x = np.asarray(data["x"], dtype=np.float64)
                    y = np.asarray(data["y"], dtype=np.float64)
                    yaw = np.asarray(data.get("yaw", data.get("theta", np.zeros_like(x))), dtype=np.float64)
                    poses = np.column_stack([x, y, yaw])
                elif "poses" in data:
                    poses = np.asarray(data["poses"], dtype=np.float64)
                elif "positions" in data:
                    poses = np.asarray(data["positions"], dtype=np.float64)
                
                for k in ["timestamps", "t", "time", "timestamp"]:
                    if k in data:
                        timestamps = np.asarray(data[k], dtype=np.float64)
                        break
            elif isinstance(data, (list, np.ndarray)):
                arr = np.asarray(data, dtype=np.float64)
                if arr.ndim == 2 and arr.shape[1] >= 2:
                    poses = arr
        except Exception as e:
            logger.warning(f"Error loading slam_data: {e}")

    if poses is None or len(poses) < 2:
        # Fallback nominal cruising state
        return np.full(n_frames, 0.25), np.zeros(n_frames)

    if timestamps is None or len(timestamps) != len(poses):
        timestamps = np.arange(len(poses)) * 0.10

    # Robust differentiation with MiR100 constraints
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from robot_data_analyzer import compute_differential_kinematics_robust
        v_arr, w_arr = compute_differential_kinematics_robust(poses, timestamps)
    except Exception:
        dt = np.diff(timestamps)
        dt = np.where(dt < 0.01, 0.01, dt)
        dx = np.diff(poses[:, 0])
        dy = np.diff(poses[:, 1])
        v_raw = np.clip(np.sqrt(dx**2 + dy**2) / dt, 0.0, V_MAX)
        w_raw = np.zeros(len(v_raw))
        v_arr = np.append(v_raw, v_raw[-1])
        w_arr = np.append(w_raw, w_raw[-1])
        
    return v_arr, w_arr

def build_qwen_training_pairs(session_dir, output_file=None):
    if not os.path.isdir(session_dir):
        return []

    bev_images = find_bev_images(session_dir)
    if not bev_images:
        return []

    v_arr, w_arr = extract_kinematics(session_dir, len(bev_images))
    n_samples = min(len(bev_images), len(v_arr))
    if n_samples == 0:
        return []

    records = []
    for idx in range(n_samples):
        img_path = bev_images[idx]
        v_raw = float(v_arr[idx])
        w_raw = float(w_arr[idx])
        
        v_norm = float(np.clip(v_raw / V_MAX, -1.0, 1.0))
        w_norm = float(np.clip(w_raw / W_MAX, -1.0, 1.0))
        
        if abs(v_raw) < 0.05 and abs(w_raw) < 0.05:
            behavior = "IDLE_STATIONARY"
        elif abs(w_raw) >= 0.15:
            behavior = "ROTATIONAL_MANEUVER"
        elif abs(v_raw) >= 0.30:
            behavior = "FORWARD_CRUISING"
        else:
            behavior = "LOW_SPEED_NAVIGATION"

        entry = {
            "frame_id": idx,
            "session": os.path.basename(session_dir),
            "image": os.path.abspath(img_path),
            "conversations": [
                {
                    "from": "user",
                    "value": "Picture 1: <image>\nBased on the current Bird's Eye View map, determine the safe navigation command for the MiR100 robot."
                },
                {
                    "from": "assistant",
                    "value": f"<thought>State: {behavior}. Executing safe non-holonomic velocity command.</thought>\n<action>[{v_norm:.4f}, {w_norm:.4f}]</action>"
                }
            ],
            "metadata": {
                "v_mps": round(v_raw, 4),
                "w_radps": round(w_raw, 4),
                "behavior": behavior
            }
        }
        records.append(entry)

    if output_file and records:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
                
    return records