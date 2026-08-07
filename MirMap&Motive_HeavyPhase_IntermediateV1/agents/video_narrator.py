#!/usr/bin/env python3
"""
VIDEO NARRATOR & QWEN-VLA DATASET GENERATOR
Synthesizes MoCap, SLAM and Action trajectories into Qwen2-VL training pairs.
Operator: Kiarash Amiri | Supervisor: Prof. Dario Antonelli | PoliTo
"""
import sys, pickle, json, os
from pathlib import Path
import numpy as np

def build_vla_narrative_and_dataset(session_dir):
    sd = Path(session_dir)
    cmd_file = sd / "mir_command_data.pkl"
    motive_file = sd / "motive_data.pkl"
    slam_file = sd / "slam_data.pkl"
    
    out_timeline = sd / "session_narrative_timeline.json"
    out_vla_dataset = sd / "qwen_vla_dataset.jsonl"
    
    summary = {
        "session": sd.name,
        "total_actions": 0,
        "vla_training_samples": 0,
        "timeline_events": [],
        "detected_behaviors": []
    }
    
    if not cmd_file.exists():
        summary["status"] = "MISSING_ACTION_DATA"
        return summary
        
    try:
        cmd_data = pickle.load(open(cmd_file, "rb"))
        odom = cmd_data.get("odom_log", [])
        summary["total_actions"] = len(odom)
        
        training_samples = []
        timeline = []
        
        if odom:
            t0 = odom[0].get("timestamp_utc", 0)
            
            # Behavioral classification
            for i in range(0, len(odom), 10): # Sample at 4Hz (every 10 odom steps at 40Hz)
                entry = odom[i]
                t_rel = round(entry.get("timestamp_utc", t0) - t0, 2)
                vx = entry.get("actual_linear_x_mps", 0.0)
                wz = entry.get("actual_angular_z_rps", 0.0)
                
                # Determine state
                if abs(vx) < 0.02 and abs(wz) < 0.02:
                    state = "IDLE_STATIONARY"
                    instruct = "Robot is waiting for navigation commands in the workspace. Maintain zero velocity."
                elif abs(vx) > 0.1 and abs(wz) < 0.1:
                    state = "FORWARD_CRUISING"
                    instruct = "Path is clear. Cruise forward at target velocity avoiding obstacles."
                elif abs(wz) >= 0.1:
                    state = "ROTATIONAL_MANEUVER"
                    instruct = "Obstacle proximity detected in LiDAR/MoCap space. Adjust heading smoothly."
                else:
                    state = "LOW_SPEED_NAVIGATION"
                    instruct = "Navigate cautiously in constrained workspace."
                    
                if len(timeline) == 0 or timeline[-1]["state"] != state:
                    timeline.append({"time_s": t_rel, "state": state, "linear_v": round(vx, 3), "angular_w": round(wz, 3)})
                
                # Build QwenVLA Training Sample
                sample = {
                    "id": f"{sd.name}_{i:05d}",
                    "timestamp_s": t_rel,
                    "conversations": [
                        {"from": "human", "value": f"<image>\nTask: {instruct}\nPredict the next motion action for MiR100 robot."},
                        {"from": "gpt", "value": f"<action> linear_x: {vx:.3f} m/s, angular_z: {wz:.3f} rad/s </action>"}
                    ],
                    "ground_truth_action": [round(vx, 4), round(wz, 4)],
                    "bev_token_ref": f"BEV_FRAME_{i//10:04d}"
                }
                training_samples.append(sample)
                
        summary["vla_training_samples"] = len(training_samples)
        summary["timeline_events"] = timeline
        summary["detected_behaviors"] = list(set(e["state"] for e in timeline))
        
        with open(out_timeline, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        with open(out_vla_dataset, "w", encoding="utf-8") as f:
            for s in training_samples:
                f.write(json.dumps(s) + "\n")
                
    except Exception as e:
        summary["status"] = f"ERROR: {str(e)}"
        
    return summary

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sessions/session_2026-08-27_17-54-20"
    res = build_vla_narrative_and_dataset(target)
    print(f"[video_narrator] Built {res['vla_training_samples']} Qwen-VLA Training Pairs | Behaviors: {res['detected_behaviors']}")
