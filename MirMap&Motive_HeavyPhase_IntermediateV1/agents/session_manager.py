#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_manager.py — Project Inspector + Memory Manager

Responsibilities:
  1. Bootstrap project root (only creates what's missing)
  2. Create new session folders
  3. Load / save persistent knowledge (environment_knowledge.pkl)
  4. Update knowledge from a completed session's fused_data.pkl
  5. Inspect project status (how many sessions, reports, etc.)

FIXED vs original:
  - bootstrap no longer overwrites existing knowledge
  - update_knowledge_from_session() actually exists now
  - default run = inspect mode, not create mode
"""

import os
import sys
import math
import glob
import pickle
import argparse
from datetime import datetime, timezone

import numpy as np

ROOT_FOLDER_NAME = "MirMap&Motive_HeavyPhase_IntermediateV1"

MATCH_DISTANCE_THRESHOLD_M = 0.5
CONFIDENCE_GROWTH_RATE = 0.25

ROBOT_NAME_KEYWORDS = ("mir", "robot")
REFERENCE_BODY_NAMES = {"Global Coordinate", "ground"}


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def utc_now_epoch():
    import time
    return time.time()


def _empty_knowledge():
    return {
        "schema_version": "knowledge_v2",
        "created_at_utc": utc_now_iso(),
        "last_updated_utc": utc_now_iso(),
        "total_sessions_processed": 0,
        "sessions_list": [],
        "objects": [],
    }


# ============================================================
# Load / Save persistent knowledge
# ============================================================
def load_persistent_knowledge(root_path):
    pkl_path = os.path.join(root_path, "persistent_knowledge",
                            "environment_knowledge.pkl")
    if not os.path.exists(pkl_path):
        return _empty_knowledge()
    try:
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        if not isinstance(data, dict) or "objects" not in data:
            return _empty_knowledge()
        return data
    except Exception:
        return _empty_knowledge()


def save_persistent_knowledge(root_path, knowledge):
    pk_dir = os.path.join(root_path, "persistent_knowledge")
    os.makedirs(pk_dir, exist_ok=True)

    pkl_path = os.path.join(pk_dir, "environment_knowledge.pkl")
    txt_path = os.path.join(pk_dir, "environment_knowledge_summary.txt")

    knowledge["last_updated_utc"] = utc_now_iso()

    tmp_path = pkl_path + ".tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(knowledge, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_path, pkl_path)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Persistent Environment Knowledge — Summary\n")
        f.write("=" * 50 + "\n")
        f.write(f"Last updated (UTC)      : {knowledge['last_updated_utc']}\n")
        f.write(f"Total sessions processed: {knowledge['total_sessions_processed']}\n")
        f.write(f"Total known objects     : {len(knowledge['objects'])}\n\n")

        if not knowledge["objects"]:
            f.write("No learned objects yet.\n")
        else:
            for obj in sorted(knowledge["objects"],
                              key=lambda o: -o["times_observed"]):
                f.write(
                    f"  [{obj['object_id']}] "
                    f"pos=({obj['estimated_position_m'][0]:.2f}, "
                    f"{obj['estimated_position_m'][1]:.2f}) m | "
                    f"seen={obj['times_observed']}x | "
                    f"static_conf={obj['is_static_confidence']:.2f} | "
                    f"class={obj['object_class']} | "
                    f"sources={sorted(obj['sources_seen'])}\n"
                )

    return pkl_path, txt_path


# ============================================================
# Bootstrap (only creates what is missing)
# ============================================================
def bootstrap_project_root(base_path="."):
    root_path = os.path.join(base_path, ROOT_FOLDER_NAME)

    subfolders = [
        "persistent_knowledge",
        "sessions",
        "reports",
        "agents",
        "calibration",
    ]

    for sub in subfolders:
        os.makedirs(os.path.join(root_path, sub), exist_ok=True)

    # Only create initial knowledge if file does NOT exist
    pkl_path = os.path.join(root_path, "persistent_knowledge",
                            "environment_knowledge.pkl")
    if not os.path.exists(pkl_path):
        knowledge = _empty_knowledge()
        save_persistent_knowledge(root_path, knowledge)
        print(f"[session_manager] Initial knowledge created.")
    else:
        print(f"[session_manager] Knowledge file already exists — not overwriting.")

    print(f"[session_manager] Project root ready: {root_path}")
    return root_path


# ============================================================
# Create new session folder
# ============================================================
def create_new_session_folder(root_path):
    timestamp_tag = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    session_path = os.path.join(root_path, "sessions",
                                f"session_{timestamp_tag}")
    os.makedirs(session_path, exist_ok=True)

    for sub in ["video", "raw", "processed"]:
        os.makedirs(os.path.join(session_path, sub), exist_ok=True)

    metadata_path = os.path.join(session_path, "session_metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write("Session Metadata\n")
        f.write("================\n")
        f.write(f"Created at UTC: {utc_now_iso()}\n")
        f.write(f"Session path  : {session_path}\n")

    print(f"[session_manager] New session: {session_path}")
    return session_path


# ============================================================
# UPDATE KNOWLEDGE FROM SESSION (was missing — this is the bug fix)
# ============================================================
def update_knowledge_from_session(root_path, session_path, calibration_path=None):
    """
    Reads fused_data.pkl from a completed session, extracts unique
    Motive objects, and merges them into persistent knowledge.
    """
    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path):
        print("[session_manager] No fused_data.pkl found — skipping "
              "knowledge update.")
        return

    with open(fused_path, "rb") as f:
        fusion = pickle.load(f)

    fused_objects = fusion.get("fused_objects", [])
    if not fused_objects:
        print("[session_manager] fused_data has no objects — skipping.")
        return

    # Group Motive objects by name (skip SLAM lidar points and robot)
    motive_observations = {}
    for obs in fused_objects:
        if obs.get("source") != "motive":
            continue
        name = obs.get("object_name", "")
        if any(k in name.lower() for k in ROBOT_NAME_KEYWORDS):
            continue
        if name in REFERENCE_BODY_NAMES:
            continue
        if name not in motive_observations:
            motive_observations[name] = []
        motive_observations[name].append(obs)

    if not motive_observations:
        print("[session_manager] No external Motive objects found in "
              "fused data.")
        return

    knowledge = load_persistent_knowledge(root_path)
    session_name = os.path.basename(session_path)

    # Check if this session was already processed
    if session_name in knowledge.get("sessions_list", []):
        print(f"[session_manager] Session {session_name} already in "
              f"knowledge — skipping duplicate.")
        return

    for name, obs_list in motive_observations.items():
        positions = np.array([o["position_mir_frame_m"] for o in obs_list])
        mean_pos = positions.mean(axis=0).tolist()
        variance = float(np.var(np.linalg.norm(
            positions - positions.mean(axis=0), axis=1)))
        heights = [o["height_m"] for o in obs_list if o.get("height_m")
                    is not None]
        mean_height = float(np.mean(heights)) if heights else None

        # Try to match with existing object
        matched = False
        for obj in knowledge["objects"]:
            dist = math.dist(obj["estimated_position_m"], mean_pos)
            if dist < MATCH_DISTANCE_THRESHOLD_M or name in obj.get(
                    "names_seen", []):
                # Update existing object
                n_old = obj["times_observed"]
                n_new = len(obs_list)
                n_total = n_old + n_new
                # Weighted average position
                obj["estimated_position_m"] = [
                    (obj["estimated_position_m"][0] * n_old +
                     mean_pos[0] * n_new) / n_total,
                    (obj["estimated_position_m"][1] * n_old +
                     mean_pos[1] * n_new) / n_total,
                ]
                obj["times_observed"] = n_total
                obj["position_variance_m2"] = (
                    (obj["position_variance_m2"] * n_old +
                     variance * n_new) / n_total
                )
                if mean_height is not None:
                    obj["mean_height_m"] = mean_height
                if name not in obj.get("names_seen", []):
                    obj.setdefault("names_seen", []).append(name)
                obj["sources_seen"].add("motive")
                obj["last_seen_session"] = session_name

                # Update classification
                if variance < 0.01:
                    obj["is_static_confidence"] = min(
                        1.0, obj["is_static_confidence"] +
                        CONFIDENCE_GROWTH_RATE)
                    if obj["is_static_confidence"] > 0.8:
                        obj["object_class"] = "static"
                elif variance > 0.5:
                    obj["is_static_confidence"] = max(
                        0.0, obj["is_static_confidence"] -
                        CONFIDENCE_GROWTH_RATE)
                    if obj["is_static_confidence"] < 0.2:
                        obj["object_class"] = "moving"

                matched = True
                break

        if not matched:
            # Classify new object
            if variance < 0.01:
                obj_class = "static"
                static_conf = 0.7
            elif variance > 0.5:
                obj_class = "moving"
                static_conf = 0.2
            else:
                obj_class = "unknown"
                static_conf = 0.5

            # Name-based hints
            name_lower = name.lower()
            if any(k in name_lower for k in ("hat", "wrist", "hand",
                                              "head")):
                obj_class = "human_marker"
                static_conf = 0.1
            elif any(k in name_lower for k in ("station", "warehouse",
                                                "table")):
                obj_class = "static_infrastructure"
                static_conf = 0.9

            new_obj = {
                "object_id": f"obj_{len(knowledge['objects']):04d}",
                "names_seen": [name],
                "estimated_position_m": mean_pos,
                "mean_height_m": mean_height,
                "times_observed": len(obs_list),
                "position_variance_m2": variance,
                "is_static_confidence": static_conf,
                "object_class": obj_class,
                "sources_seen": {"motive"},
                "first_seen_session": session_name,
                "last_seen_session": session_name,
            }
            knowledge["objects"].append(new_obj)

    knowledge["total_sessions_processed"] += 1
    knowledge.setdefault("sessions_list", []).append(session_name)

    save_persistent_knowledge(root_path, knowledge)

    print(f"[session_manager] Knowledge updated: "
          f"{len(knowledge['objects'])} objects, "
          f"{knowledge['total_sessions_processed']} sessions total.")


# ============================================================
# Project Inspector
# ============================================================
def inspect_project(root_path):
    """Print a summary of the current project state."""
    print("\n" + "=" * 60)
    print(" PROJECT INSPECTOR")
    print("=" * 60)
    print(f"Root: {root_path}")

    # Sessions
    sessions_dir = os.path.join(root_path, "sessions")
    sessions = sorted(glob.glob(os.path.join(sessions_dir, "session_*")))
    print(f"\nSessions: {len(sessions)}")
    if sessions:
        print(f"  First : {os.path.basename(sessions[0])}")
        print(f"  Latest: {os.path.basename(sessions[-1])}")

    # Reports
    reports_dir = os.path.join(root_path, "reports")
    reports = sorted(glob.glob(os.path.join(reports_dir,
                                            "copilot_report_v*.txt")))
    print(f"\nReports: {len(reports)}")
    if reports:
        print(f"  Latest: {os.path.basename(reports[-1])}")

    # Calibration
    calib_path = os.path.join(root_path, "calibration",
                              "latest_calibration.pkl")
    if os.path.exists(calib_path):
        with open(calib_path, "rb") as f:
            calib = pickle.load(f)
        print(f"\nCalibration: EXISTS")
        print(f"  Timestamp: {calib.get('timestamp_utc', 'unknown')}")
        print(f"  Verdict  : {calib.get('validation', {}).get('verdict', 'unknown')}")
    else:
        print(f"\nCalibration: NOT FOUND")

    # Knowledge
    knowledge = load_persistent_knowledge(root_path)
    print(f"\nPersistent Knowledge:")
    print(f"  Objects : {len(knowledge['objects'])}")
    print(f"  Sessions: {knowledge['total_sessions_processed']}")
    print(f"  Updated : {knowledge.get('last_updated_utc', 'never')}")

    # Deep learning memory
    dlm_path = os.path.join(root_path, "persistent_knowledge",
                            "deep_learning_memory.pkl")
    if os.path.exists(dlm_path):
        with open(dlm_path, "rb") as f:
            dlm = pickle.load(f)
        print(f"\nDeep Learning Memory: EXISTS")
        print(f"  Sessions analyzed: "
              f"{dlm.get('total_sessions_analyzed', 0)}")
        print(f"  Object tracks   : "
              f"{len(dlm.get('object_tracks', {}))}")
        print(f"  Safety events   : "
              f"{len(dlm.get('safety_events', []))}")
    else:
        print(f"\nDeep Learning Memory: NOT YET CREATED")

    print("\n" + "=" * 60)


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Project Inspector + Memory Manager")
    parser.add_argument("--base-path", type=str, default=".",
                        help="Base path for the project root.")
    parser.add_argument("--bootstrap", action="store_true",
                        help="Create missing folders/files only.")
    parser.add_argument("--new-session", action="store_true",
                        help="Create a new timestamped session folder.")
    parser.add_argument("--inspect", action="store_true",
                        help="Show full project status.")
    args = parser.parse_args()

    root_path = os.path.join(args.base_path, ROOT_FOLDER_NAME)

    if args.bootstrap or not os.path.exists(root_path):
        root_path = bootstrap_project_root(args.base_path)

    if args.new_session:
        create_new_session_folder(root_path)

    if args.inspect or (not args.bootstrap and not args.new_session):
        if os.path.exists(root_path):
            inspect_project(root_path)
        else:
            print("[session_manager] Project root not found. "
                  "Use --bootstrap first.")


if __name__ == "__main__":
    main()