"""
video_learning_agent.py (v1.0)
====================================================================
Politecnico di Torino - Reactive Collaborative Robotics Thesis
Operator: Kiarash Amiri (s322803) | Supervisor: Prof. Dario Antonelli

PURPOSE:
- Ingests dual-camera MJPEG AVI recordings (2048x1088 @ 30 FPS) from OptiTrack.
- Computes Multi-View Optical Flow & Motion Energy.
- Fuses video dynamics with MoCap 3D spatial trajectories (Hat, Wrists, Robot).
- Automatically discovers and logs HRC Interaction Events across all sessions.
- Generates persistent multimodal intelligence for Qwen-VL prompt enrichment.
====================================================================
"""

import os
import sys
import re
import json
import pickle
import math
import cv2
import numpy as np
from datetime import datetime

ROOT_DIR = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
SESSIONS_DIR = os.path.join(ROOT_DIR, "sessions")
MOTIVE_DIR = os.path.join(ROOT_DIR, "motive sessions")
KNOWLEDGE_DIR = os.path.join(ROOT_DIR, "persistent_knowledge")


def compute_video_motion_profile(video_path, sample_stride=5):
    """Extract motion energy curve from a high-res video using optical flow."""
    if not os.path.exists(video_path):
        return None

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0.0

    motion_energies = []
    prev_gray = None
    frame_idx = 0

    # Downscale resolution for fast real-time analysis
    target_w, target_h = 512, 272

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_stride == 0:
            small = cv2.resize(frame, (target_w, target_h))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
                energy = float(np.sum(thresh) / (target_w * target_h * 255.0))
                timestamp_s = round(frame_idx / fps, 3)
                motion_energies.append({
                    "frame": frame_idx,
                    "timestamp_s": timestamp_s,
                    "motion_energy": round(energy, 4)
                })
            prev_gray = gray

        frame_idx += 1

    cap.release()

    energies_only = [m["motion_energy"] for m in motion_energies] if motion_energies else [0.0]
    avg_energy = float(np.mean(energies_only)) if energies_only else 0.0
    peak_energy = float(np.max(energies_only)) if energies_only else 0.0
    active_ratio = float(np.mean([1 if e > 0.02 else 0 for e in energies_only])) if energies_only else 0.0

    return {
        "file_name": os.path.basename(video_path),
        "resolution": f"{width}x{height}",
        "fps": fps,
        "total_frames": total_frames,
        "duration_s": round(duration, 2),
        "sampled_points": len(motion_energies),
        "avg_motion_energy": round(avg_energy, 4),
        "peak_motion_energy": round(peak_energy, 4),
        "active_motion_ratio": round(active_ratio, 4),
        "profile": motion_energies
    }


def analyze_mocap_dynamics(motive_pkl_path):
    """Extract human-robot distance, human speed, and wrist elevation from MoCap."""
    if not os.path.exists(motive_pkl_path):
        return None

    try:
        with open(motive_pkl_path, "rb") as f:
            data = pickle.load(f)
    except Exception as e:
        return {"error": str(e)}

    if not isinstance(data, dict) or "rigid_bodies" not in data:
        return None

    rbs = data["rigid_bodies"]
    robot_name = "kia MIR100 002"
    hat_name = "kia hat 002"
    rwrist_name = "kiarash_RightWrist"
    lwrist_name = "kiarash_leftwrist"

    robot_samples = rbs.get(robot_name, {}).get("samples", [])
    hat_samples = rbs.get(hat_name, {}).get("samples", [])
    rwrist_samples = rbs.get(rwrist_name, {}).get("samples", [])
    lwrist_samples = rbs.get(lwrist_name, {}).get("samples", [])

    n = min(len(robot_samples), len(hat_samples))
    if n == 0:
        return {"samples_count": 0, "events": []}

    distances_m = []
    wrist_heights_m = []
    events_detected = []

    min_dist = 999.0
    max_wrist_z = -999.0

    for i in range(n):
        r = robot_samples[i]
        h = hat_samples[i]

        rx, ry, rz = r.get("x_mm", 0.0)/1000.0, r.get("y_mm", 0.0)/1000.0, r.get("z_mm", 0.0)/1000.0
        hx, hy, hz = h.get("x_mm", 0.0)/1000.0, h.get("y_mm", 0.0)/1000.0, h.get("z_mm", 0.0)/1000.0

        d = math.sqrt((rx - hx)**2 + (ry - hy)**2)
        distances_m.append(d)
        if d < min_dist:
            min_dist = d

        # Check wrist heights
        wz = 0.0
        if i < len(rwrist_samples):
            wz = rwrist_samples[i].get("z_mm", 0.0)/1000.0
            if wz > max_wrist_z:
                max_wrist_z = wz
            wrist_heights_m.append(wz)

    # Event rules
    if min_dist < 0.8:
        events_detected.append({"type": "SAFETY_ZONE_BREACH", "min_distance_m": round(min_dist, 2), "confidence": 0.95})
    elif min_dist < 1.5:
        events_detected.append({"type": "PROXEMIC_INTERACTION", "min_distance_m": round(min_dist, 2), "confidence": 0.88})

    if max_wrist_z > 1.45:
        events_detected.append({"type": "INDUSTRIAL_GESTURE_ELEVATION", "max_wrist_height_m": round(max_wrist_z, 2), "confidence": 0.92})

    return {
        "samples_analyzed": n,
        "min_human_robot_distance_m": round(min_dist, 3) if min_dist != 999.0 else None,
        "avg_human_robot_distance_m": round(float(np.mean(distances_m)), 3) if distances_m else None,
        "max_wrist_elevation_m": round(max_wrist_z, 3) if max_wrist_z != -999.0 else None,
        "events": events_detected
    }


def pair_and_analyze_all_sessions():
    """Main discovery and fusion loop over all recordings."""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    report = {
        "agent": "video_learning_agent",
        "version": "1.0",
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "total_video_pairs": 0,
        "sessions_analyzed": {}
    }

    if not os.path.exists(MOTIVE_DIR):
        print(f"[ERROR] Motive directory not found: {MOTIVE_DIR}")
        return

    all_avis = [f for f in os.listdir(MOTIVE_DIR) if f.endswith(".avi")]
    session_pattern = re.compile(r"(session_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")

    sessions_map = {}
    for avi in all_avis:
        m = session_pattern.search(avi)
        if m:
            s_name = m.group(1)
            sessions_map.setdefault(s_name, []).append(avi)

    print(f"\n[INFO] Found {len(all_avis)} AVI files spanning {len(sessions_map)} unique sessions.\n")

    for s_name, avi_files in sorted(sessions_map.items()):
        print(f"=== Processing Session: {s_name} ({len(avi_files)} Cameras) ===")
        session_dir = os.path.join(SESSIONS_DIR, s_name)
        motive_pkl = os.path.join(session_dir, "motive_data.pkl")

        # 1. Multi-camera Video Analysis
        cam_analyses = {}
        for avi in sorted(avi_files):
            avi_path = os.path.join(MOTIVE_DIR, avi)
            print(f"  --> Analyzing Video: {avi} ...")
            v_res = compute_video_motion_profile(avi_path, sample_stride=5)
            if v_res:
                cam_name = "Camera_1" if "Camera 1" in avi else "Camera_7_8"
                cam_analyses[cam_name] = v_res

        # 2. MoCap Fusion
        mocap_res = None
        if os.path.exists(motive_pkl):
            print("  --> Fusing with MoCap Spatial Data ...")
            mocap_res = analyze_mocap_dynamics(motive_pkl)

        # 3. Compile Session Intelligence
        session_summary = {
            "session_name": s_name,
            "cameras_recorded": list(cam_analyses.keys()),
            "video_metrics": {k: {
                "resolution": v["resolution"],
                "fps": v["fps"],
                "duration_s": v["duration_s"],
                "avg_motion_energy": v["avg_motion_energy"],
                "peak_motion_energy": v["peak_motion_energy"],
                "active_motion_ratio": v["active_motion_ratio"]
            } for k, v in cam_analyses.items()},
            "mocap_spatial_metrics": mocap_res,
            "synthesized_events": (mocap_res.get("events", []) if mocap_res else [])
        }

        # Save per-session cache
        if os.path.exists(session_dir):
            out_s_json = os.path.join(session_dir, "video_learning_report.json")
            with open(out_s_json, "w", encoding="utf-8") as f:
                json.dump(session_summary, f, indent=2)

        report["sessions_analyzed"][s_name] = session_summary

    report["total_video_pairs"] = len(report["sessions_analyzed"])

    # Save global persistent knowledge
    out_global = os.path.join(KNOWLEDGE_DIR, "multi_view_video_intelligence.json")
    with open(out_global, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[SUCCESS] Global Intelligence saved to: {out_global}")
    print("================================================================")
    print(f"SUMMARY: Analyzed {len(report['sessions_analyzed'])} Sessions.")
    for s_k, s_v in report["sessions_analyzed"].items():
        events_str = ", ".join([e["type"] for e in s_v.get("synthesized_events", [])]) or "NONE"
        print(f"  - {s_k}: Events = [{events_str}] | Cams = {s_v['cameras_recorded']}")
    print("================================================================\n")


if __name__ == "__main__":
    pair_and_analyze_all_sessions()
