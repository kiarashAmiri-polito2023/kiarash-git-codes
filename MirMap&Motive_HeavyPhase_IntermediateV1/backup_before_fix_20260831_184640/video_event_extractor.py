"""
Video Event Extractor Agent
Author: Kiarash Amiri (PoliTo / DIGEP)
Extracts visual motion cues, activity regions, and temporal events from raw Motive AVI videos
using OpenCV without heavy compute overhead. Caches results in session directories.
"""

import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
VIDEOS_DIR = ROOT / "motive sessions"
SESSIONS_DIR = ROOT / "sessions"

def analyze_video_file(video_path, max_frames=600):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_step = max(1, total_frames // max_frames)
    prev_gray = None
    motion_energy = []
    
    frame_idx = 0
    sampled_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step == 0:
            small = cv2.resize(frame, (320, 180))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                score = float(np.mean(diff))
                motion_energy.append({
                    "frame_sampled": sampled_idx,
                    "rel_time_s": round(frame_idx / fps, 2),
                    "motion_score": round(score, 3)
                })
                sampled_idx += 1
            prev_gray = gray

        frame_idx += 1

    cap.release()

    if not motion_energy:
        avg_motion = 0.0
        peak_motion = 0.0
    else:
        scores = [m["motion_score"] for m in motion_energy]
        avg_motion = round(float(np.mean(scores)), 3)
        peak_motion = round(float(np.max(scores)), 3)

    return {
        "filename": video_path.name,
        "fps": round(fps, 1),
        "total_frames": total_frames,
        "duration_s": round(total_frames / fps, 2),
        "resolution": f"{width}x{height}",
        "avg_motion_energy": avg_motion,
        "peak_motion_energy": peak_motion,
        "active_motion_ratio": round(len([m for m in motion_energy if m["motion_score"] > 2.5]) / max(1, len(motion_energy)), 2)
    }

def process_all_sessions():
    if not VIDEOS_DIR.exists():
        print("[SKIP] motive sessions directory not found.")
        return

    video_files = list(VIDEOS_DIR.glob("*.avi"))
    print(f"[VIDEO_EXTRACTOR] Found {len(video_files)} video recordings.")

    for s_dir in sorted(SESSIONS_DIR.glob("session_*")):
        s_name = s_dir.name
        # Match videos belonging to this session
        matched = [vf for vf in video_files if s_name in vf.name]
        if not matched:
            continue

        cache_file = s_dir / "video_events.json"
        if cache_file.exists():
            continue

        print(f"[VIDEO_EXTRACTOR] Analyzing {len(matched)} videos for {s_name}...")
        results = {}
        for vf in matched:
            analysis = analyze_video_file(vf)
            if analysis:
                results[vf.name] = analysis

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"[OK] Saved video analysis to {cache_file.name}")

if __name__ == "__main__":
    process_all_sessions()
