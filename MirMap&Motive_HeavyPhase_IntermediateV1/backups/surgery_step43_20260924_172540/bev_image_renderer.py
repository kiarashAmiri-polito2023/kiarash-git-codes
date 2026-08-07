"""
bev_image_renderer.py (v2.0 - Semantic SLAM Edition)
====================================================================
Politecnico di Torino - Reactive Collaborative Robotics Thesis
Operator: Kiarash Amiri (s322803) | Supervisor: Prof. Dario Antonelli

PURPOSE:
- Renders 448x448 RGB Bird's Eye View (BEV) PNG images.
- Fuses:
    1. Metric SLAM Occupancy Grid (Walls & Free space).
    2. Real-time LiDAR scan obstacle point clouds.
    3. MoCap 3D millimeter-accurate tracking (Robot, Hat, Wrists).
    4. YOLOv8 Semantic Objects (Chairs, Tables, Equipment).
- Feeds ground-truth spatial multimodal input directly into Qwen3-VL.
====================================================================
"""

import os
import json
import pickle
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
SESSIONS_DIR = os.path.join(ROOT_DIR, "sessions")

CANVAS_SIZE = 448
VIEW_RANGE_M = 8.0 # 8x8 meter local window centered on robot workspace
SCALE_PX_PER_M = CANVAS_SIZE / VIEW_RANGE_M # 56 pixels per meter


def world_to_bev(wx, wy, cx, cy):
    """Converts metric world coordinates (wx, wy) to BEV image pixel coords centered at (cx, cy)."""
    dx = wx - cx
    dy = wy - cy
    px = int(CANVAS_SIZE / 2.0 + dx * SCALE_PX_PER_M)
    py = int(CANVAS_SIZE / 2.0 - dy * SCALE_PX_PER_M) # Invert Y for image standard
    return px, py


def render_semantic_bev_frame(slam_grid, map_meta, robot_pose, lidar_points, mocap_human, semantic_objects):
    """Creates a single 448x448 RGB BEV image combining all multimodal sensor layers."""
    # Base background: Dark gray for unknown/outer space
    img = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (40, 44, 52))
    draw = ImageDraw.Draw(img)

    rx = robot_pose.get("x", 0.0)
    ry = robot_pose.get("y", 0.0)
    ryaw = robot_pose.get("yaw", 0.0)

    # 1. Render SLAM Grid layer
    if slam_grid is not None and map_meta is not None:
        res = map_meta.get("resolution", 0.05)
        w_px = map_meta.get("width", 1988)
        h_px = map_meta.get("height", 1056)
        
        # Subsample grid within local view window to keep high rendering speed
        step = 4
        for gy in range(0, h_px, step):
            for gx in range(0, w_px, step):
                val = slam_grid[gy, gx]
                if val >= 0: # Observed cell
                    wx = gx * res
                    wy = gy * res
                    px, py = world_to_bev(wx, wy, rx, ry)
                    if 0 <= px < CANVAS_SIZE and 0 <= py < CANVAS_SIZE:
                        if val > 50: # Wall / Occupied
                            color = (20, 20, 20)
                        else: # Free space
                            color = (210, 215, 220)
                        s = int(step * res * SCALE_PX_PER_M) + 1
                        draw.rectangle([px, py, px + s, py + s], fill=color)

    # 2. Render Semantic Objects (Chairs, Tables, Equipment from YOLO)
    for obj in semantic_objects:
        ox = obj.get("map_x_m", 0.0)
        oy = obj.get("map_y_m", 0.0)
        cls_name = obj.get("class", "object").upper()
        opx, opy = world_to_bev(ox, oy, rx, ry)

        if 0 <= opx < CANVAS_SIZE and 0 <= opy < CANVAS_SIZE:
            box_r = int(0.4 * SCALE_PX_PER_M) # 40cm radius box
            draw.rectangle([opx - box_r, opy - box_r, opx + box_r, opy + box_r], outline=(180, 100, 255), width=2)
            draw.text((opx - box_r, opy - box_r - 10), cls_name[:6], fill=(220, 180, 255))

    # 3. Render LiDAR Obstacle Points
    if lidar_points is not None and len(lidar_points) > 0:
        for pt in lidar_points:
            lx, ly = pt[0], pt[1]
            lpx, lpy = world_to_bev(lx, ly, rx, ry)
            if 0 <= lpx < CANVAS_SIZE and 0 <= lpy < CANVAS_SIZE:
                draw.ellipse([lpx - 2, lpy - 2, lpx + 2, lpy + 2], fill=(255, 60, 60))

    # 4. Render MoCap Human Operator (Hat + Wrists)
    if mocap_human:
        hx = mocap_human.get("hat_x", 0.0)
        hy = mocap_human.get("hat_y", 0.0)
        if hx != 0.0 or hy != 0.0:
            hpx, hpy = world_to_bev(hx, hy, rx, ry)
            if 0 <= hpx < CANVAS_SIZE and 0 <= hpy < CANVAS_SIZE:
                # Human Head
                draw.ellipse([hpx - 8, hpy - 8, hpx + 8, hpy + 8], fill=(46, 204, 113), outline=(255, 255, 255), width=2)
                draw.text((hpx + 10, hpy - 8), "OPERATOR", fill=(46, 204, 113))

        # Human Wrists
        for wx, wy in mocap_human.get("wrists", []):
            wpx, wpy = world_to_bev(wx, wy, rx, ry)
            if 0 <= wpx < CANVAS_SIZE and 0 <= wpy < CANVAS_SIZE:
                draw.ellipse([wpx - 4, wpy - 4, wpx + 4, wpy + 4], fill=(241, 196, 15))

    # 5. Render MiR100 Robot Body, Safety Halo & Heading
    r_center_px = int(CANVAS_SIZE / 2.0)
    r_center_py = int(CANVAS_SIZE / 2.0)

    # 1.2m Safety Zone Halo
    halo_r = int(1.2 * SCALE_PX_PER_M)
    draw.ellipse([r_center_px - halo_r, r_center_py - halo_r, r_center_px + halo_r, r_center_py + halo_r], 
                 outline=(230, 126, 34), width=2)

    # MiR100 footprint (0.9m length x 0.6m width)
    rw = int(0.6 * SCALE_PX_PER_M)
    rl = int(0.9 * SCALE_PX_PER_M)
    draw.rectangle([r_center_px - rw//2, r_center_py - rl//2, r_center_px + rw//2, r_center_py + rl//2],
                   fill=(52, 152, 219), outline=(255, 255, 255), width=2)

    # Heading Arrow
    arrow_len = int(1.0 * SCALE_PX_PER_M)
    tip_x = int(r_center_px + arrow_len * math.cos(ryaw))
    tip_y = int(r_center_py - arrow_len * math.sin(ryaw))
    draw.line([r_center_px, r_center_py, tip_x, tip_y], fill=(231, 76, 60), width=3)
    draw.ellipse([tip_x - 3, tip_y - 3, tip_x + 3, tip_y + 3], fill=(231, 76, 60))

    return img


def process_session(sname):
    sdir = os.path.join(SESSIONS_DIR, sname)
    slam_pkl = os.path.join(sdir, "slam_data.pkl")
    motive_pkl = os.path.join(sdir, "motive_data.pkl")
    odom_pkl = os.path.join(sdir, "mir_command_data.pkl")
    sem_map_json = os.path.join(sdir, "semantic_object_map.json")

    if not os.path.exists(slam_pkl) or not os.path.exists(odom_pkl):
        return False, "Missing SLAM or Odom data"

    print(f"=== Rendering Semantic BEV Frames: {sname} ===")

    # Load SLAM
    with open(slam_pkl, "rb") as f:
        slam_data = pickle.load(f)
    slam_grid = slam_data.get("map_grid")
    map_meta = slam_data.get("map_metadata", {})
    robot_states = slam_data.get("robot_states", [])
    obstacle_scans = slam_data.get("obstacle_scans", [])

    # Load MoCap
    mocap_data = {}
    if os.path.exists(motive_pkl):
        with open(motive_pkl, "rb") as f:
            mocap_data = pickle.load(f)
    rbs = mocap_data.get("rigid_bodies", {}) if isinstance(mocap_data, dict) else {}
    hat_samples = rbs.get("kia hat 002", {}).get("samples", [])
    rwrist_samples = rbs.get("kiarash_RightWrist", {}).get("samples", [])
    lwrist_samples = rbs.get("kiarash_leftwrist", {}).get("samples", [])

    # Load Semantic Objects
    semantic_objs = []
    if os.path.exists(sem_map_json):
        with open(sem_map_json, "r", encoding="utf-8") as f:
            sem_data = json.load(f)
            semantic_objs = sem_data.get("fused_objects", [])

    out_bev_dir = os.path.join(sdir, "bev_images")
    os.makedirs(out_bev_dir, exist_ok=True)

    n_frames = min(len(robot_states), 344) # Target 344 ground-truth action samples
    print(f"  Generating {n_frames} BEV frames (448x448 RGB) with {len(semantic_objs)} Semantic Objects...")

    for i in range(n_frames):
        rob_pose = robot_states[i] if i < len(robot_states) else {"x": 27.8, "y": 21.2, "yaw": 0.0}
        
        # Match nearest LiDAR scan
        lidar_pts = []
        if i < len(obstacle_scans):
            scan = obstacle_scans[i]
            lidar_pts = scan.get("points_global_frame", [])

        # Match MoCap Operator
        human_info = {"hat_x": 0.0, "hat_y": 0.0, "wrists": []}
        if i < len(hat_samples):
            hs = hat_samples[i]
            human_info["hat_x"] = hs.get("x_mm", 0.0) / 1000.0
            human_info["hat_y"] = hs.get("y_mm", 0.0) / 1000.0

        if i < len(rwrist_samples):
            rws = rwrist_samples[i]
            human_info["wrists"].append((rws.get("x_mm", 0.0)/1000.0, rws.get("y_mm", 0.0)/1000.0))

        # Render combined frame
        bev_img = render_semantic_bev_frame(slam_grid, map_meta, rob_pose, lidar_pts, human_info, semantic_objs)
        frame_filename = f"frame_{i:05d}.png"
        bev_img.save(os.path.join(out_bev_dir, frame_filename), "PNG")

    print(f"  [SUCCESS] Rendered {n_frames} Semantic BEV frames -> {out_bev_dir}\n")
    return True, f"Rendered {n_frames} frames"


def main():
    sessions = [d for d in os.listdir(SESSIONS_DIR) if os.path.isdir(os.path.join(SESSIONS_DIR, d))]
    for s in sorted(sessions):
        if "2026-08-27_17-54-20" in s: # Target golden session
            process_session(s)


if __name__ == "__main__":
    main()
