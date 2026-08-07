from pathlib import Path
import os
import sys
import json
import pickle
import numpy as np
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
SESSIONS_DIR = ROOT_DIR / "sessions"
GRID_SIZE = 448
PPM = 20.0
OFFSET_X = 224
OFFSET_Y = 224

COLOR_BG = (20, 20, 25)
COLOR_GRID = (40, 40, 50)
COLOR_ROBOT = (0, 255, 128)
COLOR_HEADING = (255, 255, 0)
COLOR_LIDAR = (0, 180, 255)
COLOR_HUMAN = (255, 80, 80)
COLOR_SEMANTIC = (180, 100, 255)


def world_to_bev(wx, wy, rx, ry, ryaw):
    dx = wx - rx
    dy = wy - ry
    cos_a = np.cos(-ryaw)
    sin_a = np.sin(-ryaw)
    lx = cos_a * dx - sin_a * dy
    ly = sin_a * dx + cos_a * dy
    px = int(OFFSET_X - ly * PPM)
    py = int(OFFSET_Y - lx * PPM)
    return px, py


def render_semantic_bev_frame(slam_grid, map_meta, rob_pose, lidar_pts, human_info, semantic_objs):
    img = Image.new("RGB", (GRID_SIZE, GRID_SIZE), COLOR_BG)
    draw = ImageDraw.Draw(img)

    for i in range(0, GRID_SIZE, int(PPM)):
        draw.line([(i, 0), (i, GRID_SIZE)], fill=COLOR_GRID, width=1)
        draw.line([(0, i), (GRID_SIZE, i)], fill=COLOR_GRID, width=1)

    rx = rob_pose.get("x", 27.8)
    ry = rob_pose.get("y", 21.2)
    ryaw = rob_pose.get("yaw", 0.0)

    if lidar_pts:
        for pt in lidar_pts:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                px, py = world_to_bev(pt[0], pt[1], rx, ry, ryaw)
                if 0 <= px < GRID_SIZE and 0 <= py < GRID_SIZE:
                    draw.rectangle([px - 1, py - 1, px + 1, py + 1], fill=COLOR_LIDAR)

    if semantic_objs:
        for obj in semantic_objs:
            ox = obj.get("x", 0.0)
            oy = obj.get("y", 0.0)
            px, py = world_to_bev(ox, oy, rx, ry, ryaw)
            if 0 <= px < GRID_SIZE and 0 <= py < GRID_SIZE:
                draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=COLOR_SEMANTIC, outline=(255, 255, 255))

    if human_info:
        hx = human_info.get("hat_x", 0.0)
        hy = human_info.get("hat_y", 0.0)
        if hx != 0.0 or hy != 0.0:
            px, py = world_to_bev(hx, hy, rx, ry, ryaw)
            if 0 <= px < GRID_SIZE and 0 <= py < GRID_SIZE:
                draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=COLOR_HUMAN, outline=(255, 255, 255))
                draw.text((px + 10, py - 6), "Operator", fill=(255, 255, 255))

    cx, cy = OFFSET_X, OFFSET_Y
    rw, rh = 12, 16
    draw.rectangle([cx - rw, cy - rh, cx + rw, cy + rh], fill=COLOR_ROBOT, outline=(255, 255, 255))
    draw.line([(cx, cy), (cx, cy - 24)], fill=COLOR_HEADING, width=3)
    return img


def process_session(session_input):
    if isinstance(session_input, (str, Path)):
        p = Path(session_input)
        sdir = p if p.is_dir() and p.exists() else SESSIONS_DIR / str(session_input)
    else:
        sdir = SESSIONS_DIR / str(session_input)

    sdir = Path(sdir)
    slam_pkl = sdir / "slam_data.pkl"
    motive_pkl = sdir / "motive_data.pkl"
    sem_map_json = sdir / "semantic_object_map.json"

    if not slam_pkl.exists():
        return False, f"Missing SLAM data in {sdir.name}"

    print(f"=== Rendering Semantic BEV Frames: {sdir.name} ===")

    with open(slam_pkl, "rb") as f:
        slam_data = pickle.load(f)
    slam_grid = slam_data.get("map_grid")
    map_meta = slam_data.get("map_metadata", {})
    robot_states = slam_data.get("robot_states", [])
    obstacle_scans = slam_data.get("obstacle_scans", [])

    mocap_data = {}
    if motive_pkl.exists():
        try:
            with open(motive_pkl, "rb") as f:
                mocap_data = pickle.load(f)
        except Exception:
            mocap_data = {}

    rbs = mocap_data.get("rigid_bodies", {}) if isinstance(mocap_data, dict) else {}

    hat_samples = []
    rwrist_samples = []
    lwrist_samples = []
    for bname, bdata in rbs.items():
        low = bname.lower()
        if "hat" in low or "head" in low:
            hat_samples = bdata.get("samples", [])
        elif "rightwrist" in low or "rwrist" in low:
            rwrist_samples = bdata.get("samples", [])
        elif "leftwrist" in low or "lwrist" in low:
            lwrist_samples = bdata.get("samples", [])

    semantic_objs = []
    if sem_map_json.exists():
        try:
            with open(sem_map_json, "r", encoding="utf-8") as f:
                sem_data = json.load(f)
                semantic_objs = sem_data.get("fused_objects", [])
        except Exception:
            semantic_objs = []

    out_bev_dir = sdir / "bev_images"
    out_bev_dir.mkdir(parents=True, exist_ok=True)

    n_frames = len(robot_states)
    print(f"  Generating {n_frames} BEV frames (448x448 RGB) with {len(semantic_objs)} Semantic Objects...")

    for i in range(n_frames):
        state = robot_states[i]
        rob_pose = state if isinstance(state, dict) else {"x": 27.8, "y": 21.2, "yaw": 0.0}
        state_ts = rob_pose.get("timestamp_utc", 0.0)

        lidar_pts = []
        if obstacle_scans:
            best_scan = min(
                obstacle_scans,
                key=lambda s: abs(s.get("timestamp_utc", 0.0) - state_ts) if isinstance(s, dict) and "timestamp_utc" in s else float("inf")
            )
            if isinstance(best_scan, dict):
                lidar_pts = best_scan.get("points_global_frame", [])

        human_info = {"hat_x": 0.0, "hat_y": 0.0, "wrists": []}
        if i < len(hat_samples):
            hs = hat_samples[i]
            human_info["hat_x"] = hs.get("x_mm", 0.0) / 1000.0
            human_info["hat_y"] = hs.get("y_mm", 0.0) / 1000.0

        if i < len(rwrist_samples):
            rws = rwrist_samples[i]
            human_info["wrists"].append((rws.get("x_mm", 0.0) / 1000.0, rws.get("y_mm", 0.0) / 1000.0))

        bev_img = render_semantic_bev_frame(slam_grid, map_meta, rob_pose, lidar_pts, human_info, semantic_objs)
        frame_filename = f"frame_{i:05d}.png"
        bev_img.save(out_bev_dir / frame_filename, "PNG")

    print(f"  [SUCCESS] Rendered {n_frames} Semantic BEV frames -> {out_bev_dir}")
    return True, f"Rendered {n_frames} frames"


def main():
    if len(sys.argv) > 1:
        sname = sys.argv[1]
    else:
        sname = "session_2026-08-27_17-54-20"
    process_session(sname)


if __name__ == "__main__":
    main()
