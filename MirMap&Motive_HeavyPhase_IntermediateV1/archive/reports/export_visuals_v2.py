import os, sys, json, shutil, pickle
from pathlib import Path
from datetime import datetime
import numpy as np
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw
log = lambda m: print(m, flush=True)
log("="*70)
log("[VISUAL COMPILER v2.1] Historical Archive Mode - Python 3.10 Fixed")
log("="*70)
def get_desktop():
    u = os.environ.get("USERPROFILE")
    if u:
        d = Path(u) / "Desktop"
        if d.exists(): return d
    return Path.cwd() / "visual_exports"
project_root = Path.cwd()
sessions_root = project_root / "sessions"
session_dirs = sorted([d for d in sessions_root.glob("session_*") if d.is_dir()])
if not session_dirs:
    log("[X] No sessions found in sessions/ folder. Exiting.")
    sys.exit(1)
latest_session = session_dirs[-1]
session_name = latest_session.name.replace("session_", "S_")
log(f"[*] Latest session detected: {latest_session.name}")
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
kiarash_root = get_desktop() / "Kiarash1234"
kiarash_root.mkdir(parents=True, exist_ok=True)
run_folder = kiarash_root / f"Run_{timestamp}_{session_name}"
run_folder.mkdir(parents=True, exist_ok=True)
bev_dest = run_folder / "1_Semantic_BEV_Frames"
yolo_dest = run_folder / "2_YOLO_Camera_Detections"
traj_dest = run_folder / "3_SLAM_Trajectory_Map"
for p in [bev_dest, yolo_dest, traj_dest]:
    p.mkdir(parents=True, exist_ok=True)
log(f"[*] Archive folder created: {run_folder.name}")
log("")
log("[Step 1/4] Copying Semantic BEV frames...")
bev_src = latest_session / "bev_images"
bev_count = 0
if bev_src.exists():
    bevs = sorted(list(bev_src.glob("*.png")))
    step = max(1, len(bevs) // 25)
    for i in range(0, len(bevs), step):
        shutil.copy(bevs[i], bev_dest / bevs[i].name)
        bev_count += 1
    log(f"    [OK] {bev_count} BEV frames copied")
else:
    log("    [!] No BEV images found in this session")
log("")
log("[Step 2/4] Extracting camera frames with YOLO boxes...")
yolo_count = 0
try:
    import cv2
    video_path = None
    videos_folder = latest_session / "videos"
    if videos_folder.exists():
        candidates = sorted(list(videos_folder.glob("*.avi")))
        if candidates: video_path = candidates[0]
    yolo_json = latest_session / "yolo_detections.json"
    if video_path and video_path.exists() and yolo_json.exists():
        with open(yolo_json, "r", encoding="utf-8") as f:
            yolo_data = json.load(f)
        cap = cv2.VideoCapture(str(video_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        indices = np.linspace(0, total - 1, 15, dtype=int)
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret: continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            d = ImageDraw.Draw(pil)
            dets = yolo_data.get(str(int(idx)), [])
            if not dets: dets = yolo_data.get(f"frame_{int(idx):05d}", [])
            if isinstance(yolo_data, list) and int(idx) < len(yolo_data):
                item = yolo_data[int(idx)]
                if isinstance(item, dict): dets = item.get("detections") or item.get("box_data", [])
            for obj in dets:
                if isinstance(obj, dict):
                    box = obj.get("box") or obj.get("bbox")
                    cname = obj.get("class_name") or obj.get("name", "Object")
                    conf = float(obj.get("confidence", 0.9))
                    if box and len(box) == 4:
                        x1, y1, x2, y2 = map(int, box)
                        d.rectangle([x1, y1, x2, y2], outline="red", width=3)
                        d.text((x1 + 4, y1 + 4), f"{cname} {conf:.2f}", fill="yellow")
            pil.save(yolo_dest / f"yolo_frame_{int(idx):05d}.jpg")
            yolo_count += 1
        cap.release()
        log(f"    [OK] {yolo_count} annotated camera frames saved")
    else:
        log("    [!] Video or YOLO JSON missing")
except Exception as e:
    log(f"    [!] YOLO step error: {e}")
log("")
log("[Step 3/4] Plotting SLAM trajectory...")
traj_ok = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    slam_pkl = latest_session / "slam_data.pkl"
    if slam_pkl.exists():
        with open(slam_pkl, "rb") as f:
            data = pickle.load(f)
        states = data.get("robot_states", []) if isinstance(data, dict) else []
        xs, ys = [], []
        for s in states:
            if isinstance(s, dict):
                x = s.get("pose_x", s.get("x"))
                y = s.get("pose_y", s.get("y"))
                if x is not None and y is not None:
                    xs.append(float(x)); ys.append(float(y))
        if xs and ys:
            plt.figure(figsize=(10, 8))
            plt.plot(xs, ys, color="magenta", linewidth=2.5, label="Robot Path", zorder=2)
            plt.scatter([xs[0]], [ys[0]], color="green", s=180, label="Start", zorder=3, edgecolors="black")
            plt.scatter([xs[-1]], [ys[-1]], color="red", s=180, label="End", zorder=3, edgecolors="black")
            plt.title(f"MiR100 SLAM Trajectory - {latest_session.name}", fontsize=13, fontweight="bold")
            plt.xlabel("X (meters)", fontsize=11)
            plt.ylabel("Y (meters)", fontsize=11)
            plt.grid(True, linestyle="--", alpha=0.4)
            plt.legend(fontsize=11, loc="best")
            plt.axis("equal")
            plt.tight_layout()
            plt.savefig(traj_dest / "mir100_slam_trajectory.png", dpi=200)
            plt.close()
            log(f"    [OK] Trajectory plot saved ({len(xs)} points)")
            traj_ok = True
        else:
            log("    [!] No trajectory points extracted")
    else:
        log("    [!] slam_data.pkl not found")
except Exception as e:
    log(f"    [!] Trajectory error: {e}")
log("")
log("[Step 4/4] Writing SUMMARY report...")
summary_lines = []
summary_lines.append("="*70)
summary_lines.append("KIARASH THESIS - VISUAL ARCHIVE RUN REPORT")
summary_lines.append("="*70)
summary_lines.append(f"Run Timestamp:    {timestamp}")
summary_lines.append(f"Session Source:   {latest_session.name}")
summary_lines.append(f"Archive Location: {run_folder}")
summary_lines.append("")
summary_lines.append("CONTENTS:")
summary_lines.append(f"  Folder 1 (BEV):        {bev_count} semantic frames")
summary_lines.append(f"  Folder 2 (YOLO):       {yolo_count} annotated camera frames")
traj_status = "generated" if traj_ok else "skipped"
summary_lines.append(f"  Folder 3 (Trajectory): {traj_status}")
summary_lines.append("")
eval_json = project_root / "eval_results_v3.json"
if eval_json.exists():
    try:
        with open(eval_json, "r", encoding="utf-8") as f:
            e = json.load(f)
        mae_v_val = e.get("mae_v", 0.0)
        mae_w_val = e.get("mae_w", 0.0)
        z_bl_v = e.get("z_bl", [0.0, 0.0])[0]
        z_bl_w = e.get("z_bl", [0.0, 0.0])[1]
        m_bl_v = e.get("m_bl", [0.0, 0.0])[0]
        m_bl_w = e.get("m_bl", [0.0, 0.0])[1]
        summary_lines.append("VLA MODEL BENCHMARK (from eval_results_v3.json):")
        summary_lines.append(f"  MODEL MAE_v:    {mae_v_val:.4f} m/s")
        summary_lines.append(f"  MODEL MAE_w:    {mae_w_val:.4f} rad/s")
        summary_lines.append(f"  Zero Baseline:  MAE_v={z_bl_v:.4f} / MAE_w={z_bl_w:.4f}")
        summary_lines.append(f"  Mean Baseline:  MAE_v={m_bl_v:.4f} / MAE_w={m_bl_w:.4f}")
        shutil.copy(eval_json, run_folder / "eval_results_v3.json")
        summary_lines.append("")
        summary_lines.append("  [Full eval_results_v3.json also copied to this folder]")
    except Exception as ex:
        summary_lines.append(f"  (eval read error: {ex})")
else:
    summary_lines.append("VLA Benchmark: Not yet generated for this session.")
summary_lines.append("")
summary_lines.append("="*70)
with open(run_folder / "SUMMARY.txt", "w", encoding="utf-8") as f:
    f.write("\\n".join(summary_lines))
log("    [OK] SUMMARY.txt written")
log("")
log("="*70)
log("[SUCCESS] Archive complete!")
log(f"Location: {run_folder}")
log("="*70)
try:
    all_runs = sorted([d for d in kiarash_root.glob("Run_*") if d.is_dir()])
    log(f"[HISTORY] You now have {len(all_runs)} archived run(s) in Kiarash1234/:")
    for r in all_runs[-5:]:
        log(f"    - {r.name}")
except: pass
