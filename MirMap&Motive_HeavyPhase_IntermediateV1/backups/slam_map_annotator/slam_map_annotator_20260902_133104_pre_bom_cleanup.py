#!/usr/bin/env python3
"""
SLAM MAP ANNOTATOR - Industrial Production Grade
Fuses SLAM 2D Occupancy Grid with MoCap Rigid Body Ground Truth.
Operator: Kiarash Amiri | Supervisor: Prof. Dario Antonelli | PoliTo
"""
import sys, pickle, json, os
from pathlib import Path
import numpy as np

def annotate_slam_session(session_dir):
    sd = Path(session_dir)
    slam_file = sd / "slam_data.pkl"
    motive_file = sd / "motive_data.pkl"
    out_file = sd / "slam_semantic_map.json"
    
    report = {
        "session": sd.name,
        "status": "PROCESSED",
        "grid_shape": None,
        "total_robot_poses": 0,
        "total_scans": 0,
        "tracked_entities": [],
        "spatial_bounds": {}
    }
    
    if not slam_file.exists():
        report["status"] = "MISSING_SLAM_DATA"
        return report

    try:
        slam_data = pickle.load(open(slam_file, "rb"))
        
        # Grid metadata extraction
        grid = slam_data.get("map_grid")
        if grid is not None and hasattr(grid, "shape"):
            report["grid_shape"] = list(grid.shape)
            
        robot_states = slam_data.get("robot_states", [])
        report["total_robot_poses"] = len(robot_states)
        
        obstacle_scans = slam_data.get("obstacle_scans", [])
        report["total_scans"] = len(obstacle_scans)
        
        # Cross-reference with Motive rigid bodies
        if motive_file.exists():
            motive_data = pickle.load(open(motive_file, "rb"))
            rbs = motive_data.get("selected_rigid_bodies", [])
            report["tracked_entities"] = rbs
            
        # Calculate spatial bounds from robot states
        if robot_states:
            xs = [s.get("x", 0) for s in robot_states if isinstance(s, dict)]
            ys = [s.get("y", 0) for s in robot_states if isinstance(s, dict)]
            if xs and ys:
                report["spatial_bounds"] = {
                    "min_x_m": round(min(xs), 3), "max_x_m": round(max(xs), 3),
                    "min_y_m": round(min(ys), 3), "max_y_m": round(max(ys), 3),
                    "trajectory_length_m": round(sum(np.sqrt(np.diff(xs)**2 + np.diff(ys)**2)), 2) if len(xs) > 1 else 0.0
                }
                
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
    except Exception as e:
        report["status"] = f"ERROR: {str(e)}"
        
    return report

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sessions/session_2026-08-27_17-54-20"
    res = annotate_slam_session(target)
    print(f"[slam_map_annotator] Processed: {res['session']} | Poses: {res['total_robot_poses']} | Entities: {len(res['tracked_entities'])}")
