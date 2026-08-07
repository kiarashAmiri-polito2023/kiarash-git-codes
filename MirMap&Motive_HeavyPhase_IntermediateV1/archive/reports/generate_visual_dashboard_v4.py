import os, sys, glob, json, pickle, traceback, shutil
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
DESKTOP = os.path.join(os.environ["USERPROFILE"], "Desktop", "Kiarash1234")
STAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
RUN = os.path.join(DESKTOP, "Visual_Master_v4_" + STAMP)
D1 = os.path.join(RUN, "1_Semantic_BEV_Frames")
D2 = os.path.join(RUN, "2_YOLO_Camera_Detections")
D3 = os.path.join(RUN, "3_SLAM_Trajectory_Map")
D4 = os.path.join(RUN, "4_VLA_Canary_and_Benchmarks")
D5 = os.path.join(RUN, "5_Decision_Composite_Dashboards")
for d in (D1, D2, D3, D4, D5):
    os.makedirs(d, exist_ok=True)

ERR = open(os.path.join(RUN, "ERROR_LOG.txt"), "w", encoding="utf-8")
def log_err(where):
    tb = traceback.format_exc()
    ERR.write("### " + where + "\n" + tb + "\n\n"); ERR.flush()
    print("  [!] " + where + " FAILED -> see ERROR_LOG.txt")

def nfiles(d):
    return len([f for f in glob.glob(os.path.join(d, "*")) if os.path.isfile(f)])

print("=" * 62)
print("VISUAL MASTER v4.0 - SELF-DISCOVERING")
print("RUN DIR: " + RUN)
print("=" * 62)

# ---------------- DISCOVERY ----------------
sessions = sorted(glob.glob(os.path.join(BASE, "sessions", "session_*")))
S = None
for cand in reversed(sessions):
    has_slam = os.path.exists(os.path.join(cand, "slam_data.pkl"))
    n_bev = len(glob.glob(os.path.join(cand, "bev*", "*.png")))
    if has_slam and n_bev > 0:
        S = cand; break
if S is None:
    for cand in reversed(sessions):
        if os.path.exists(os.path.join(cand, "slam_data.pkl")):
            S = cand; break
print("[DISCOVERY] session  : " + (os.path.basename(S) if S else "NONE!"))

bev_pngs = []
if S:
    for sub in glob.glob(os.path.join(S, "bev*")):
        if os.path.isdir(sub):
            bev_pngs += glob.glob(os.path.join(sub, "*.png"))
    bev_pngs.sort()
if not bev_pngs:
    from collections import Counter
    c = Counter(os.path.dirname(p) for p in glob.glob(os.path.join(BASE, "**", "*.png"), recursive=True))
    if c:
        bev_pngs = sorted(glob.glob(os.path.join(c.most_common(1)[0][0], "*.png")))
print("[DISCOVERY] BEV pngs : " + str(len(bev_pngs)))

stamp = os.path.basename(S).replace("session_", "") if S else ""
vids = []
motive_dir = os.path.join(BASE, "motive sessions")
if os.path.isdir(motive_dir):
    vids = [v for v in glob.glob(os.path.join(motive_dir, "*", "*.avi")) + glob.glob(os.path.join(motive_dir, "*", "*.mp4")) if stamp in v]
if not vids:
    vids = glob.glob(os.path.join(BASE, "sessions", "**", "*.avi"), recursive=True)
if not vids:
    vids = glob.glob(os.path.join(motive_dir, "**", "*.avi"), recursive=True)
vids = [v for v in vids if stamp in v] or vids
vids.sort()
print("[DISCOVERY] videos   : " + str([os.path.basename(v) for v in vids]))

robot_states = []
slam_meta = {}
map_grid = None
# ---------------- TASK 1: SLAM MAPS ----------------
try:
    with open(os.path.join(S, "slam_data.pkl"), "rb") as f:
        slam = pickle.load(f)
    robot_states = slam.get("robot_states", [])
    map_grid = slam.get("map_grid", None)
    slam_meta = slam.get("map_metadata", {}) or {}
    x = np.array([st["x"] for st in robot_states])
    y = np.array([st["y"] for st in robot_states])
    t = np.array([st["timestamp_utc"] for st in robot_states])
    yaw = np.array([float(st.get("yaw", 0.0)) for st in robot_states])
    dtn = np.diff(t); dtn[dtn <= 0] = 1e-6
    v = np.concatenate([[0.0], np.hypot(np.diff(x), np.diff(y)) / dtn])
    k = max(3, min(15, len(v) // 20))
    v_s = np.convolve(v, np.ones(k) / k, mode="same")

    res = 0.05
    for kk in ("resolution", "res", "resolution_m_per_px"):
        if kk in slam_meta:
            try: res = float(slam_meta[kk]); break
            except Exception: pass

    def render(origin_lower, suffix):
        plt.figure(figsize=(12, 8), dpi=150)
        if map_grid is not None:
            g = np.asarray(map_grid)
            if g.ndim == 2:
                h, w = g.shape
                plt.imshow(g, cmap="gray", origin=("lower" if origin_lower else "upper"),
                           extent=(0, w * res, 0, h * res), alpha=0.9)
        sc = plt.scatter(x, y, c=v_s, cmap="turbo", s=10, zorder=3)
        plt.colorbar(sc, label="linear velocity v (m/s)")
        plt.plot(x[0], y[0], "g^", ms=14, label="start", zorder=4)
        plt.plot(x[-1], y[-1], "rs", ms=12, label="end", zorder=4)
        stq = max(1, len(x) // 30)
        plt.quiver(x[::stq], y[::stq], np.cos(yaw[::stq]), np.sin(yaw[::stq]),
                   color="deepskyblue", scale=45, width=0.004, alpha=0.85, zorder=3)
        plt.title("MiR100 SLAM trajectory + occupancy grid | " + os.path.basename(S))
        plt.xlabel("x (m)"); plt.ylabel("y (m)")
        plt.legend(); plt.grid(alpha=0.2); plt.tight_layout()
        plt.savefig(os.path.join(D3, "trajectory_velocity_" + suffix + ".png")); plt.close()

    render(True, "v1_origin_lower")
    render(False, "v2_origin_upper")

    plt.figure(figsize=(11, 4), dpi=150)
    plt.plot(t - t[0], v_s, lw=1.4, color="teal")
    plt.xlabel("time (s)"); plt.ylabel("v (m/s)")
    plt.title("Velocity profile derived from SLAM poses (finite differences)")
    plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(D3, "velocity_timeseries.png")); plt.close()

    try:
        fp = os.path.join(S, "fused_data.pkl")
        if os.path.exists(fp):
            with open(fp, "rb") as f:
                fused = pickle.load(f)
            hx, hy = [], []
            for o in fused.get("fused_objects", []):
                nm = str(o.get("object_name", "")).lower()
                if o.get("source") == "motive" and "kiarash" in nm:
                    p = o.get("position_mir_frame_m")
                    if p is not None and len(p) >= 2:
                        hx.append(float(p[0])); hy.append(float(p[1]))
            if len(hx) > 10:
                plt.figure(figsize=(12, 8), dpi=150)
                g = np.asarray(map_grid) if map_grid is not None else None
                if g is not None and g.ndim == 2:
                    h, w = g.shape
                    plt.imshow(g, cmap="gray", origin="lower", extent=(0, w * res, 0, h * res), alpha=0.9)
                plt.plot(x, y, "-b", lw=2, label="MiR100 robot (SLAM)", zorder=3)
                plt.plot(hx, hy, "-m", lw=2, alpha=0.8, label="Human operator (MoCap fused)", zorder=3)
                plt.title("Robot vs Human spatial behavior | " + os.path.basename(S))
                plt.xlabel("x (m)"); plt.ylabel("y (m)"); plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(D3, "robot_vs_human_map.png")); plt.close()
                print("      bonus: robot-vs-human map rendered (" + str(len(hx)) + " human points)")
    except Exception:
        log_err("human overlay")

    print("  [1/5] SLAM maps OK -> " + str(nfiles(D3)) + " files | robot_states=" + str(len(robot_states)))
except Exception:
    log_err("TASK1 slam")

# ---------------- TASK 2: CAMERA + REAL YOLO ----------------
frames_meta = []
try:
    NPV = 8
    for vid in vids[:2]:
        cap = cv2.VideoCapture(vid)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release(); continue
        idxs = np.linspace(0, total - 1, NPV).astype(int)
        tag = os.path.splitext(os.path.basename(vid))[0].replace(" ", "_")[-45:]
        for fi in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
            ok, img = cap.read()
            if ok:
                cv2.imwrite(os.path.join(D2, tag + "_f" + str(int(fi)).zfill(6) + ".jpg"), img)
                frames_meta.append((tag, int(fi), img))
        cap.release()
    print("  [2/5] camera frames -> " + str(nfiles(D2)) + " files")

    yj = glob.glob(os.path.join(S, "yolo*.json")) if S else []
    if yj and frames_meta:
        with open(yj[0], "r", encoding="utf-8") as f:
            yd = json.load(f)
        per_frame = {}
        def harvest(fk, dets):
            arr = []
            for d in dets:
                box = None; lbl = "?"; conf = 0.0
                if isinstance(d, dict):
                    for kk in ("bbox", "box", "xyxy", "bbox_xyxy"):
                        if kk in d: box = d[kk]; break
                    if box is None and "x1" in d:
                        box = [d["x1"], d["y1"], d["x2"], d["y2"]]
                    lbl = str(d.get("label", d.get("class", d.get("name", "?"))))
                    try: conf = float(d.get("conf", d.get("confidence", d.get("score", 0))) or 0)
                    except Exception: conf = 0.0
                elif isinstance(d, (list, tuple)) and len(d) >= 4:
                    box = list(d[:4])
                    if len(d) >= 6:
                        lbl = str(d[4])
                        try: conf = float(d[5])
                        except Exception: conf = 0.0
                if box is not None and len(box) >= 4:
                    try: arr.append(([float(box[0]), float(box[1]), float(box[2]), float(box[3])], lbl, conf))
                    except Exception: pass
            if arr:
                per_frame[fk] = arr
        def walk(node):
            if isinstance(node, dict):
                fk = node.get("frame_index", node.get("frame", node.get("frame_id", node.get("frame_number"))))
                dd = node.get("detections", node.get("boxes", node.get("objects")))
                if fk is not None and dd is not None:
                    harvest(fk, dd); return
                for vv in node.values(): walk(vv)
            elif isinstance(node, list):
                for it in node: walk(it)
        walk(yd)
        if per_frame:
            n_over = 0
            int_keys = [kk for kk in per_frame if str(kk).isdigit()]
            for tag, fi, img in frames_meta:
                dets = per_frame.get(fi)
                if dets is None and int_keys:
                    near = min(int_keys, key=lambda kk: abs(int(kk) - fi))
                    if abs(int(near) - fi) <= 15: dets = per_frame.get(near)
                if not dets: continue
                im = img.copy()
                for (x1, y1, x2, y2), lbl, conf in dets:
                    cv2.rectangle(im, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(im, lbl + " " + format(conf, ".2f"), (int(x1), max(15, int(y1) - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.imwrite(os.path.join(D2, "YOLO_" + tag + "_f" + str(fi).zfill(6) + ".jpg"), im)
                n_over += 1
            print("      REAL YOLO boxes overlaid on " + str(n_over) + " frames")
        else:
            print("      note: yolo json exists but no frame-boxes parsed -> raw frames kept")
except Exception:
    log_err("TASK2 camera/yolo")

# ---------------- TASK 3: BEV ----------------
try:
    if bev_pngs:
        nsel = min(20, len(bev_pngs))
        sel = np.linspace(0, len(bev_pngs) - 1, nsel).astype(int)
        for i in sel:
            shutil.copy2(bev_pngs[i], os.path.join(D1, os.path.basename(bev_pngs[i])))
        print("  [3/5] BEV sampled -> " + str(nfiles(D1)) + " files (source: " + os.path.basename(os.path.dirname(bev_pngs[0])) + ")")
    else:
        print("  [3/5] NO BEV pngs found anywhere!")
except Exception:
    log_err("TASK3 bev")

# ---------------- TASK 4: VLA CHARTS ----------------
try:
    epochs_c = [1, 2, 3, 4, 5, 6]
    can_v = [0.250, 0.440, 0.414, 0.480, 0.540, 0.538]
    can_w = [-0.151, -0.044, -0.159, -0.156, -0.156, -0.156]
    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(epochs_c, can_v, "o-", color="#1f77b4", lw=2.5, label="predicted v")
    plt.axhline(0.561, color="#1f77b4", ls="--", lw=1.5, label="GT v = 0.561 m/s")
    plt.plot(epochs_c, can_w, "s-", color="#d62728", lw=2.5, label="predicted w")
    plt.axhline(-0.189, color="#d62728", ls="--", lw=1.5, label="GT w = -0.189 rad/s")
    plt.title("Canary Test Convergence (hard sample GT=[0.561, -0.189])")
    plt.xlabel("epoch"); plt.ylabel("output"); plt.xticks(epochs_c)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(D4, "1_canary_evolution.png")); plt.close()

    loss_series = None
    hp = os.path.join(BASE, "models", "qwen3_vla_mir100_lora_v2", "training_history.json")
    if os.path.exists(hp):
        with open(hp, "r", encoding="utf-8") as f:
            hist = json.load(f)
        def find_loss(node):
            if isinstance(node, dict):
                for kk, vv in node.items():
                    if isinstance(vv, list) and len(vv) >= 2 and all(isinstance(z, (int, float)) for z in vv) and "loss" in kk.lower():
                        return vv
                    r = find_loss(vv)
                    if r: return r
            elif isinstance(node, list) and node and all(isinstance(z, dict) for z in node):
                for keyl in ("loss", "train_loss", "epoch_loss"):
                    if all(keyl in z for z in node):
                        return [z[keyl] for z in node]
            elif isinstance(node, list):
                for it in node:
                    r = find_loss(it)
                    if r: return r
            return None
        loss_series = find_loss(hist)
    if loss_series:
        ep = list(range(1, len(loss_series) + 1))
        plt.figure(figsize=(9, 5), dpi=150)
        plt.plot(ep, loss_series, "d-", color="#2ca02c", lw=2.5)
        plt.yscale("log"); plt.grid(True, which="both", ls="--", alpha=0.5)
        plt.title("QLoRA Training Loss (from training_history.json)")
        plt.xlabel("epoch"); plt.ylabel("loss (log)")
        plt.tight_layout()
        plt.savefig(os.path.join(D4, "2_training_loss_curve.png")); plt.close()
        print("      loss curve plotted from REAL history: " + str([round(z, 4) for z in loss_series]))
    else:
        print("      loss series not found in history json -> logged")
        ERR.write("### loss-series-not-found\n")

    ev = os.path.join(BASE, "eval_results_v3.json")
    pairs = []
    if os.path.exists(ev):
        with open(ev, "r", encoding="utf-8") as f:
            ed = json.load(f)
        def find_pairs(node):
            if isinstance(node, dict):
                g = p = None
                for kk in ("gt_action", "ground_truth", "gt"):
                    if kk in node: g = node[kk]; break
                for kk in ("pred_action", "predicted", "pred"):
                    if kk in node: p = node[kk]; break
                if isinstance(g, (list, tuple)) and isinstance(p, (list, tuple)) and len(g) == 2 and len(p) == 2:
                    try: pairs.append(([float(g[0]), float(g[1])], [float(p[0]), float(p[1])])); return
                    except Exception: pass
                for vv in node.values(): find_pairs(vv)
            elif isinstance(node, list):
                for it in node: find_pairs(it)
        find_pairs(ed)
    if len(pairs) >= 10:
        gv = [a[0][0] for a in pairs]; pv = [a[1][0] for a in pairs]
        gw = [a[0][1] for a in pairs]; pw = [a[1][1] for a in pairs]
        plt.figure(figsize=(11, 5), dpi=150)
        plt.subplot(1, 2, 1)
        plt.scatter(gv, pv, alpha=0.75, edgecolors="k")
        lims = [min(min(gv), min(pv)) - 0.05, max(max(gv), max(pv)) + 0.05]
        plt.plot(lims, lims, "r--", lw=1.5)
        plt.title("Linear velocity: GT vs Pred"); plt.xlabel("GT v"); plt.ylabel("pred v"); plt.grid(alpha=0.3)
        plt.subplot(1, 2, 2)
        plt.scatter(gw, pw, alpha=0.75, edgecolors="k", color="seagreen")
        lims2 = [min(min(gw), min(pw)) - 0.1, max(max(gw), max(pw)) + 0.1]
        plt.plot(lims2, lims2, "r--", lw=1.5)
        plt.title("Angular velocity: GT vs Pred"); plt.xlabel("GT w"); plt.ylabel("pred w"); plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(D4, "3_gt_vs_pred_scatter.png")); plt.close()
        print("      scatter plotted from " + str(len(pairs)) + " real eval samples")
    else:
        print("      eval pairs not parseable -> logged")
        ERR.write("### eval-pairs-not-found\n")

    cats = ["IDLE", "LOW_SPD", "ROT", "CRUISE", "OVERALL"]
    ours = [0.0247, 0.0342, 0.0360, 0.1040, 0.0600]
    base0 = [0.0000, 0.0850, 0.0920, 0.3800, 0.1582]
    xi = np.arange(len(cats)); wd = 0.35
    plt.figure(figsize=(9, 5), dpi=150)
    plt.bar(xi - wd / 2, ours, wd, label="Qwen3-VL policy", color="#21918c")
    plt.bar(xi + wd / 2, base0, wd, label="Zero baseline", color="#440154", alpha=0.65)
    plt.xticks(xi, cats); plt.ylabel("MAE v (m/s)")
    plt.title("MAE by behavior class vs baseline")
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(D4, "4_behavior_mae_benchmarks.png")); plt.close()
    print("  [4/5] VLA charts -> " + str(nfiles(D4)) + " files")
except Exception:
    log_err("TASK4 vla charts")

# ---------------- TASK 5: DASHBOARDS ----------------
try:
    bev_list = sorted(glob.glob(os.path.join(D1, "*.png")))
    if frames_meta and bev_list:
        vmax = float(np.max([st.get("x", 0) for st in robot_states]) * 0)  # placeholder
        vm = 0.0
        if robot_states:
            try:
                xs = np.array([st["x"] for st in robot_states])
                ys = np.array([st["y"] for st in robot_states])
                ts = np.array([st["timestamp_utc"] for st in robot_states])
                dtn = np.diff(ts); dtn[dtn <= 0] = 1e-6
                vv = np.concatenate([[0], np.hypot(np.diff(xs), np.diff(ys)) / dtn])
                vm = float(np.mean(vv)); vmax = float(np.max(vv))
            except Exception:
                pass
        n = min(len(frames_meta), len(bev_list))
        for i in range(n):
            tag, fi, cam = frames_meta[i]
            bev = cv2.imread(bev_list[i])
            camr = cv2.resize(cam, (448, 336))
            bevr = cv2.resize(bev, (336, 336))
            pan = np.zeros((336, 340, 3), dtype=np.uint8) + 25
            cv2.putText(pan, "VLA MISSION DASHBOARD", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.putText(pan, "cam: " + tag, (12, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
            cv2.putText(pan, "video frame #" + str(fi), (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
            cv2.line(pan, (12, 95), (328, 95), (90, 90, 90), 1)
            cv2.putText(pan, "SESSION GT STATS (SLAM):", (12, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 200, 255), 1)
            cv2.putText(pan, "mean v = " + format(vm, ".3f") + " m/s", (24, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            cv2.putText(pan, "max  v = " + format(vmax, ".3f") + " m/s", (24, 172), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            cv2.line(pan, (12, 190), (328, 190), (90, 90, 90), 1)
            cv2.putText(pan, "CANARY (hardest sample):", (12, 212), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 100), 1)
            cv2.putText(pan, "pred [0.538, -0.156]", (24, 238), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(pan, "GT   [0.561, -0.189]", (24, 263), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(pan, "MAE_v = 0.060 | MAE_w = 0.080", (12, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1)
            comp = np.hstack([camr, bevr, pan])
            cv2.imwrite(os.path.join(D5, "dashboard_" + str(i + 1).zfill(2) + ".jpg"), comp)
        print("  [5/5] dashboards -> " + str(nfiles(D5)) + " files")
    else:
        print("  [5/5] skipped (need camera frames + bev)")
except Exception:
    log_err("TASK5 dashboards")

# ---------------- MANIFEST ----------------
ERR.close()
man = []
man.append("=" * 70)
man.append("VISUAL MASTER v4.0 RUN  |  " + STAMP)
man.append("session used : " + (os.path.basename(S) if S else "?"))
man.append("bev source   : " + (os.path.dirname(bev_pngs[0]) if bev_pngs else "?"))
man.append("videos used  : " + "; ".join(os.path.basename(v) for v in vids[:2]))
man.append("=" * 70)
man.append("1_Semantic_BEV_Frames        : " + str(nfiles(D1)) + " files")
man.append("2_YOLO_Camera_Detections     : " + str(nfiles(D2)) + " files")
man.append("3_SLAM_Trajectory_Map        : " + str(nfiles(D3)) + " files")
man.append("4_VLA_Canary_and_Benchmarks  : " + str(nfiles(D4)) + " files")
man.append("5_Decision_Composite_Dashboards: " + str(nfiles(D5)) + " files")
nerr = open(os.path.join(RUN, "ERROR_LOG.txt"), "r", encoding="utf-8").read().strip()
man.append("errors logged: " + str(nerr.count("###")))
with open(os.path.join(RUN, "MANIFEST.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(man))

print("")
print("=" * 62)
for line in man:
    print(line)
print("=" * 62)
print(">>> OPENING FOLDER IN EXPLORER NOW <<<")
try:
    os.startfile(RUN)
except Exception:
    import subprocess; subprocess.Popen(["explorer.exe", RUN])


