#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/offline_processor.py - Standalone processor for existing sessions

When videos are already recorded, run this instead of launch_session.
It runs the full pipeline on existing data without recording new session.
"""

import os
import sys
import glob
import subprocess

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)


def find_project_root():
    parent = os.path.dirname(THIS_DIR)
    return parent


def list_sessions(root):
    sessions_dir = os.path.join(root, "sessions")
    if not os.path.isdir(sessions_dir):
        return []
    return sorted(glob.glob(os.path.join(sessions_dir, "session_*")))


def pick_session(sessions):
    print("\nAvailable sessions:")
    for i, s in enumerate(sessions, 1):
        print("  [" + str(i) + "] " + os.path.basename(s))
    print("")
    while True:
        ans = input("Pick session number (or 'all'): ").strip()
        if ans.lower() == "all":
            return sessions
        try:
            idx = int(ans) - 1
            if 0 <= idx < len(sessions):
                return [sessions[idx]]
        except ValueError:
            pass
        print("Invalid choice.")


def run_stage(name, cmd, cwd):
    print("\n" + "=" * 60)
    print(" STAGE: " + name)
    print("=" * 60)
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=False)
        return result.returncode == 0
    except Exception as e:
        print("  ERROR: " + str(e))
        return False


def process_session(root, session_path):
    print("\n\n" + "#" * 60)
    print(" PROCESSING: " + os.path.basename(session_path))
    print("#" * 60)

    py = sys.executable
    calib = os.path.join(root, "calibration", "latest_calibration.pkl")
    if not os.path.exists(calib):
        alt = os.path.join(os.path.dirname(root), "calibration_results",
                            "latest_calibration.pkl")
        if os.path.exists(alt):
            calib = alt

    # Stage 1: fusion
    run_stage("Spatial-Temporal Fusion",
              [py, os.path.join(THIS_DIR, "spatial_temporal_fusion.py"),
               session_path, calib], THIS_DIR)

    # Stage 2: knowledge engine
    run_stage("Knowledge Engine (SAFE)",
              [py, os.path.join(THIS_DIR, "knowledge_engine.py"),
               "--safe", session_path, root], THIS_DIR)

    # Stage 3: quality gate (already integrated in run_session_analysis)
    # Stage 4: label registry auto
    run_stage("Label Registry Auto",
              [py, os.path.join(THIS_DIR, "label_registry_auto.py"),
               root, session_path], THIS_DIR)

    # Stage 5: cross-modal aligner
    run_stage("Cross-Modal Aligner",
              [py, os.path.join(THIS_DIR, "cross_modal_aligner.py"),
               "--session", session_path, "--root", root], THIS_DIR)

    # Stage 6: ask about CVAT / auto_labeler
    print("\n" + "=" * 60)
    print(" NEXT: VIDEO ANNOTATION (CVAT / Auto-Labeler)")
    print("=" * 60)
    print("  Video files for this session are in: motive sessions/")
    print("  Options:")
    print("    1. Run auto_labeler.py on a video")
    print("    2. Open CVAT (http://localhost:8080) manually")
    print("    3. Skip for now")
    ans = input("  Choice [3]: ").strip() or "3"

    if ans == "1":
        motive_dir = os.path.join(os.path.dirname(root), "motive sessions")
        if not os.path.isdir(motive_dir):
            motive_dir = os.path.join(root, "motive sessions")
        sess_name = os.path.basename(session_path)
        videos = glob.glob(os.path.join(motive_dir, sess_name + "*.avi"))
        if not videos:
            print("  No videos found for this session.")
        else:
            for i, v in enumerate(videos, 1):
                print("    [" + str(i) + "] " + os.path.basename(v))
            v_ans = input("  Pick video: ").strip()
            try:
                v_idx = int(v_ans) - 1
                if 0 <= v_idx < len(videos):
                    out_xml = os.path.join(session_path, "auto_labels.xml")
                    run_stage("Auto Labeler",
                              [py, os.path.join(THIS_DIR, "auto_labeler.py"),
                               "--video", videos[v_idx],
                               "--output", out_xml], THIS_DIR)
            except ValueError:
                pass

    print("\n[DONE] Session processing complete.")


def main():
    root = find_project_root()
    print("=" * 60)
    print(" OFFLINE PROCESSOR")
    print("=" * 60)
    print(" Root: " + root)

    sessions = list_sessions(root)
    if not sessions:
        print(" No sessions found.")
        return

    picked = pick_session(sessions)
    for s in picked:
        process_session(root, s)

    print("\n\n" + "=" * 60)
    print(" ALL DONE.")
    print("=" * 60)


if __name__ == "__main__":
    main()
