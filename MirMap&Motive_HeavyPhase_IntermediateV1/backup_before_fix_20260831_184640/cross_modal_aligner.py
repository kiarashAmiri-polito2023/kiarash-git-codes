#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/cross_modal_aligner.py - Cross-Modal Alignment (Motive <-> SLAM)
"""

import os
import sys
import json
import math
import pickle
import argparse
from datetime import datetime, timezone

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def hungarian_match(motive_names, motive_pos, slam_ids, slam_pos, max_dist=1.5):
    if not HAS_SCIPY:
        return greedy_match(motive_names, motive_pos, slam_ids, slam_pos, max_dist)
    if not motive_pos or not slam_pos:
        return []

    n_m, n_s = len(motive_pos), len(slam_pos)
    cost = np.zeros((n_m, n_s))
    for i in range(n_m):
        for j in range(n_s):
            cost[i][j] = math.hypot(motive_pos[i][0]-slam_pos[j][0],
                                     motive_pos[i][1]-slam_pos[j][1])
    cost[cost > max_dist] = 9999.0
    row_ind, col_ind = linear_sum_assignment(cost)

    matches = []
    for r, c in zip(row_ind, col_ind):
        if cost[r][c] < 9999.0:
            matches.append({
                "motive_name": motive_names[r], "slam_id": slam_ids[c],
                "distance_m": round(float(cost[r][c]), 3),
                "confidence": round(max(0, 1 - cost[r][c]/max_dist), 3),
                "method": "hungarian",
            })
    return matches


def greedy_match(motive_names, motive_pos, slam_ids, slam_pos, max_dist=1.5):
    pairs = []
    for i, m in enumerate(motive_names):
        for j, s in enumerate(slam_ids):
            d = math.hypot(motive_pos[i][0]-slam_pos[j][0], motive_pos[i][1]-slam_pos[j][1])
            if d <= max_dist:
                pairs.append((d, i, j))
    pairs.sort()
    matches, used_m, used_s = [], set(), set()
    for d, i, j in pairs:
        if i in used_m or j in used_s:
            continue
        matches.append({
            "motive_name": motive_names[i], "slam_id": slam_ids[j],
            "distance_m": round(d, 3), "confidence": round(max(0, 1-d/max_dist), 3),
            "method": "greedy",
        })
        used_m.add(i); used_s.add(j)
    return matches


def run_alignment(session_path, root_path, max_dist=1.5):
    print("\n" + "=" * 60)
    print(" CROSS-MODAL ALIGNER")
    print("=" * 60)

    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path):
        print("  No fused_data.pkl.")
        return

    with open(fused_path, "rb") as f:
        fused = pickle.load(f)

    motive_pos = {}
    for obs in fused.get("fused_objects", []):
        if obs.get("source") != "motive":
            continue
        n = obs.get("object_name", ""); p = obs.get("position_mir_frame_m")
        if n and p:
            motive_pos.setdefault(n, []).append(p)

    m_names, m_mean = [], []
    for n, ps in motive_pos.items():
        xs = [p[0] for p in ps]; ys = [p[1] for p in ps]
        m_names.append(n); m_mean.append([sum(xs)/len(xs), sum(ys)/len(ys)])

    s_ids, s_pos, seen = [], [], set()
    for obs in fused.get("fused_objects", []):
        if obs.get("source") != "slam_lidar":
            continue
        n = obs.get("object_name", ""); p = obs.get("position_mir_frame_m")
        if n and p and n not in seen:
            seen.add(n); s_ids.append(n); s_pos.append(p)

    print("  Motive: " + str(len(m_names)) + " | SLAM: " + str(len(s_ids)))
    if not m_names or not s_ids:
        print("  Nothing to match.")
        return

    matches = hungarian_match(m_names, m_mean, s_ids, s_pos, max_dist)
    print("  Matches: " + str(len(matches)))
    for m in matches:
        print("    " + m["motive_name"] + " <-> " + m["slam_id"] +
              "  d=" + str(m["distance_m"]) + "m conf=" + str(m["confidence"]))

    out_path = os.path.join(session_path, "cross_modal_matches.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps({
                "session": os.path.basename(session_path),
                **m, "human_confirmed": False,
                "timestamp_utc": utc_now_iso(),
            }, ensure_ascii=False) + "\n")
    print("  Saved: " + out_path)
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-distance", type=float, default=1.5)
    args = parser.parse_args()
    run_alignment(args.session, args.root, args.max_distance)


if __name__ == "__main__":
    main()
