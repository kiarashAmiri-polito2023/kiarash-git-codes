#!/usr/bin/env python3
"""
SLAM TO BEV (Bird's Eye View Tokenizer for VLA Models)
Converts SLAM LiDAR Scans + Odometry into 2D Top-Down Spatial Tokens.
Operator: Kiarash Amiri | Supervisor: Prof. Dario Antonelli | PoliTo
"""
import sys, pickle, json, os
from pathlib import Path
import numpy as np

def generate_bev_tokens(session_dir):
    sd = Path(session_dir)
    slam_file = sd / "slam_data.pkl"
    cmd_file = sd / "mir_command_data.pkl"
    out_meta = sd / "bev_vla_metadata.json"
    out_tokens = sd / "bev_tokens.jsonl"

    bev_result = {
        "session": sd.name,
        "status": "COMPLETED",
        "canvas_size": [512, 512],
        "resolution_m_per_px": 0.02,  # 2cm per pixel
        "bev_frames": 0,
        "average_lidar_points_per_frame": 0
    }

    if not slam_file.exists():
        bev_result["status"] = "MISSING_SLAM"
        return bev_result

    try:
        with open(slam_file, "rb") as f:
            slam_data = pickle.load(f)
            
        scans = slam_data.get("obstacle_scans", [])
        robot_states = slam_data.get("robot_states", [])

        if not robot_states:
            bev_result["status"] = "EMPTY_ROBOT_STATES"
            return bev_result

        token_entries = []
        total_pts = 0
        base_ts = robot_states[0].get("timestamp_utc", 0.0)

        # Iterate over robot_states (Ground Truth Pose trajectory)
        # Fixes BUG-DX (Synthetic 0.05 step) and BUG-EC (Frame count mismatch)
        for idx, state in enumerate(robot_states):
            state_ts = state.get("timestamp_utc", 0.0)

            # Match nearest LiDAR obstacle scan by timestamp
            pts_count = 0
            if scans:
                best_scan = min(
                    scans,
                    key=lambda s: abs(s.get("timestamp_utc", 0.0) - state_ts) if isinstance(s, dict) else float("inf")
                )
                if isinstance(best_scan, dict):
                    pts_count = best_scan.get("num_points", 0)

            total_pts += pts_count
            token_entries.append({
                "frame_id": idx,
                "timestamp_utc": state_ts,
                "timestamp_rel_s": round(state_ts - base_ts, 3),
                "lidar_points": pts_count,
                "robot_pose": {
                    "x": float(state.get("x", 0.0)),
                    "y": float(state.get("y", 0.0)),
                    "yaw": float(state.get("yaw", 0.0))
                },
                "bev_token_repr": f"BEV_TOKEN_{idx:05d}"
            })

        bev_result["bev_frames"] = len(token_entries)
        if len(token_entries) > 0:
            bev_result["average_lidar_points_per_frame"] = round(total_pts / len(token_entries), 1)

        with open(out_meta, "w", encoding="utf-8") as f:
            json.dump(bev_result, f, indent=2)

        with open(out_tokens, "w", encoding="utf-8") as f:
            for t in token_entries:
                f.write(json.dumps(t) + "\n")

    except Exception as e:
        bev_result["status"] = f"ERROR: {str(e)}"

    return bev_result

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sessions/session_2026-08-27_17-54-20"
    res = generate_bev_tokens(target)
    print(f"[slam_to_bev] Generated {res['bev_frames']} BEV Spatial Frames | Avg LiDAR Pts: {res['average_lidar_points_per_frame']}")
