#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slam_auto_namer.py - Automatic SLAM Cluster Naming (v1.0)

Propagates entity names from Motive to SLAM clusters using spatial matching.
Uses cross_modal_aligner output and links to EntityRegistry.
"""
import os, sys, pickle, math
from datetime import datetime, timezone

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def link_slam_to_entities(root_path, session_path, distance_threshold_m=0.5):
    """
    For each SLAM cluster in the session, find the closest Motive marker,
    then link that cluster to the entity that owns the marker.
    """
    sys.path.insert(0, os.path.join(root_path, "agents"))
    from entity_registry import EntityRegistry
    
    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path):
        print(f"[SlamAutoNamer] No fused data at {session_path}")
        return None
    
    with open(fused_path, "rb") as f:
        fused = pickle.load(f)
    
    session_name = os.path.basename(session_path)
    registry = EntityRegistry(root_path)
    
    # Build marker->entity lookup
    marker_to_entity = {}
    for eid, e in registry.entities.items():
        for m in e.get("motive_markers", []):
            marker_to_entity[m] = eid
    
    if not marker_to_entity:
        print("[SlamAutoNamer] No entities in registry. Run entity_registry.py --rebuild first.")
        return None
    
    # Extract SLAM clusters and Motive markers from fused data
    fused_objects = fused.get("fused_objects", [])
    
    motive_positions = {}  # marker_name -> avg position
    slam_positions = {}    # cluster_id -> avg position
    
    from collections import defaultdict
    motive_groups = defaultdict(list)
    slam_groups = defaultdict(list)
    
    for obs in fused_objects:
        src = obs.get("source", "")
        pos = obs.get("position_mir_frame_m")
        if pos is None:
            continue
        name = obs.get("object_name", "")
        if src == "motive":
            motive_groups[name].append(pos)
        elif src == "slam_lidar":
            slam_groups[name].append(pos)
    
    for m, positions in motive_groups.items():
        if positions:
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            motive_positions[m] = (sum(xs)/len(xs), sum(ys)/len(ys))
    
    for c, positions in slam_groups.items():
        if positions:
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            slam_positions[c] = (sum(xs)/len(xs), sum(ys)/len(ys))
    
    # Match each SLAM cluster to nearest Motive marker within threshold
    matches = []
    for cluster_id, cpos in slam_positions.items():
        best_marker = None
        best_dist = distance_threshold_m
        for marker, mpos in motive_positions.items():
            d = math.hypot(cpos[0]-mpos[0], cpos[1]-mpos[1])
            if d < best_dist:
                best_dist = d
                best_marker = marker
        if best_marker and best_marker in marker_to_entity:
            entity_id = marker_to_entity[best_marker]
            matches.append({
                "slam_cluster_id": cluster_id,
                "matched_marker": best_marker,
                "entity_id": entity_id,
                "entity_name": registry.entities[entity_id]["canonical_name"],
                "distance_m": best_dist,
                "confidence": max(0.0, 1.0 - best_dist / distance_threshold_m)
            })
            registry.link_slam_cluster(entity_id, cluster_id, session_name, 
                                        confidence=matches[-1]["confidence"])
    
    registry.save()
    
    # Save session-level match report
    out_pkl = os.path.join(session_path, "slam_entity_matches.pkl")
    with open(out_pkl, "wb") as f:
        pickle.dump({
            "session": session_name,
            "generated_at_utc": utc_now_iso(),
            "total_slam_clusters": len(slam_positions),
            "matched_clusters": len(matches),
            "unmatched_clusters": len(slam_positions) - len(matches),
            "matches": matches
        }, f)
    
    txt = os.path.join(session_path, "slam_entity_matches_summary.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n SLAM CLUSTER -> ENTITY MATCHES\n" + "=" * 60 + "\n")
        f.write(f"Session: {session_name}\n")
        f.write(f"Total SLAM clusters: {len(slam_positions)}\n")
        f.write(f"Matched: {len(matches)}\n")
        f.write(f"Unmatched: {len(slam_positions) - len(matches)}\n\n")
        for m in matches:
            f.write(f"  {m['slam_cluster_id']} -> {m['entity_name']} "
                    f"(dist={m['distance_m']:.2f}m, conf={m['confidence']:.2f})\n")
    
    print(f"[SlamAutoNamer] {len(matches)} clusters matched to entities")
    print(f"[SlamAutoNamer] Saved: {out_pkl}")
    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: python slam_auto_namer.py <session_path> [root_path]")
        sys.exit(1)
    session = sys.argv[1]
    root = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    link_slam_to_entities(root, session)


if __name__ == "__main__":
    main()
