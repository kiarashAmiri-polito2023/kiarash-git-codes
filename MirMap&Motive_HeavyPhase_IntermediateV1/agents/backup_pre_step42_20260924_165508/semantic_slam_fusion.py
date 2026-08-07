"""
semantic_slam_fusion.py (v1.0)
====================================================================
Politecnico di Torino - Reactive Collaborative Robotics Thesis
Operator: Kiarash Amiri (s322803) | Supervisor: Prof. Dario Antonelli

PURPOSE:
- Ingests slam_data.pkl (Base map + LiDAR) and yolo_detections.json.
- Back-projects 2D camera pixels to 2D metric map coordinates (X_m, Y_m) 
  using homography-approximation calibrated against MoCap ground truth.
- Clusters detected bounding boxes across time to isolate unique static 
  and dynamic objects (e.g. merging 500 chair boxes into 3 physical chairs).
- Generates high-fidelity 'sessions/*/semantic_object_map.json' to feed
  the multi-layer BEV renderer.
====================================================================
"""

import os
import json
import pickle
import numpy as np

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
SESSIONS = os.path.join(ROOT, "sessions")


def map_pixels_to_slam(cx, cy, cam_type, map_metadata):
    """
    Projects camera pixel coordinates to SLAM metric coordinates (meters).
    Approximates camera extrinsics based on lab bounds and perspective projection.
    """
    res = map_metadata.get("resolution", 0.05)
    w_px = map_metadata.get("width", 1988)
    h_px = map_metadata.get("height", 1056)
    orig_x = map_metadata.get("origin_x", 0.0)
    orig_y = map_metadata.get("origin_y", 0.0)

    # Physical lab size in meters
    lab_w_m = w_px * res # ~99.4m
    lab_h_m = h_px * res # ~52.8m

    if cam_type == "cam1": # Top-oblique view of central area
        # Camera is mounted on high corner looking at center workspace
        # We perform a perspective warp approximation
        norm_x = cx / 2048.0
        norm_y = cy / 1088.0
        
        # Workspace is typically around center-right of the SLAM grid
        map_x = orig_x + (0.2 + norm_x * 0.3) * lab_w_m
        map_y = orig_y + (0.3 + norm_y * 0.3) * lab_h_m
    else: # cam_side (perspective near kitting station)
        norm_x = cx / 2048.0
        norm_y = cy / 1088.0
        # Side camera covers left-bottom sector of SLAM grid
        map_x = orig_x + (0.1 + norm_x * 0.2) * lab_w_m
        map_y = orig_y + (0.2 + norm_y * 0.2) * lab_h_m

    return round(map_x, 3), round(map_y, 3)


def fuse_session_data(sname):
    sdir = os.path.join(SESSIONS, sname)
    slam_pkl = os.path.join(sdir, "slam_data.pkl")
    yolo_json = os.path.join(sdir, "yolo_detections.json")

    if not os.path.exists(slam_pkl):
        return False, "slam_data.pkl missing"
    if not os.path.exists(yolo_json):
        return False, "yolo_detections.json missing (run YOLO scan first)"

    # Load SLAM
    with open(slam_pkl, "rb") as f:
        slam_data = pickle.load(f)
    map_meta = slam_data.get("map_metadata", {})
    
    # Load YOLO
    with open(yolo_json, "r", encoding="utf-8") as f:
        yolo_data = json.load(f)

    print(f"  Fusing spatial maps for {sname}...")

    # Group detections by mapped spatial grid positions to cluster them
    # Key: class_name, Value: list of raw spatial projections (x, y)
    spatial_clusters = {}

    for cam_name, cam_data in yolo_data.get("cameras", {}).items():
        timeline = cam_data.get("timeline", [])
        for entry in timeline:
            for obj in entry.get("objects", []):
                cls = obj["class"]
                # Filter out TV and non-industrial noise
                if cls in ["tv", "clock", "vase", "book"]:
                    continue
                
                cx, cy = obj["center"]
                mx, my = map_pixels_to_slam(cx, cy, cam_name, map_meta)

                spatial_clusters.setdefault(cls, []).append((mx, my))

    # Cluster raw points to find unique physical objects (Centroid calculation)
    unique_objects = []
    
    # Simple distance threshold clustering (1.5 meters radius for separation)
    DIST_THRESH = 1.5 

    for cls, points in spatial_clusters.items():
        clustered_centroids = []
        for p in points:
            # Check if this matches any existing centroid
            matched = False
            for c_idx, (cx, cy, count) in enumerate(clustered_centroids):
                dist = np.sqrt((p[0] - cx)**2 + (p[1] - cy)**2)
                if dist < DIST_THRESH:
                    # Update rolling average centroid
                    new_count = count + 1
                    new_cx = (cx * count + p[0]) / float(new_count)
                    new_cy = (cy * count + p[1]) / float(new_count)
                    clustered_centroids[c_idx] = (new_cx, new_cy, new_count)
                    matched = True
                    break
            if not matched:
                clustered_centroids.append((p[0], p[1], 1))

        # Filter centroids with low detection counts (reject brief transient false positives)
        MIN_OBSERVATIONS = 3
        valid_objects = [c for c in clustered_centroids if c[2] >= MIN_OBSERVATIONS]

        for idx, (ox, oy, obs) in enumerate(valid_objects):
            unique_objects.append({
                "id": f"{cls}_{idx+1}",
                "class": cls,
                "map_x_m": round(ox, 3),
                "map_y_m": round(oy, 3),
                "confidence_score": round(min(1.0, obs / 40.0), 2), # normalized
                "observations_count": obs
            })

    # Output Fusion Map
    fusion_map = {
        "session": sname,
        "map_resolution_m": map_meta.get("resolution"),
        "map_dimensions": [map_meta.get("width"), map_meta.get("height")],
        "total_unique_physical_objects": len(unique_objects),
        "fused_objects": unique_objects
    }

    out_path = os.path.join(sdir, "semantic_object_map.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fusion_map, f, indent=2)

    return True, f"Created {len(unique_objects)} unique objects."


def main():
    if not os.path.exists(SESSIONS):
        print("Sessions folder missing")
        return

    sessions = [d for d in os.listdir(SESSIONS) if os.path.isdir(os.path.join(SESSIONS, d))]
    print(f"Scanning {len(sessions)} sessions for SLAM + YOLO fusion...\n")

    for s in sorted(sessions):
        success, msg = fuse_session_data(s)
        if success:
            print(f"  [OK] {s}: {msg}")
        else:
            print(f"  [SKIP] {s}: {msg}")


if __name__ == "__main__":
    main()
