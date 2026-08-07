#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash Amiri Polito
Email: s322803@studenti.polito.it
GitHub: https://github.com/kiarashAmiri-polito2023/kiarash-git-codes.git

Description:
  MiR <-> OptiTrack/Motive Calibration Tool - v4 (FINAL, Confirmed Axes,
  Lever-Arm Aware, One-Shot-Safe)

  Confirmed project convention (from live Motive settings check):
    - Motive Up Axis = Z  ->  Motive GROUND PLANE = (X, Y), VERTICAL = Z.
    - This matches MiR's own convention: MiR ground plane is also (X, Y).
    - So NO axis-swap is needed between the two systems' ground planes;
      we simply compare mir(x,y) against motive(x,y), and keep motive(z)
      as a separate, independent height/vertical measurement.

  Physical lever-arm (VERY IMPORTANT, confirmed by user):
    - When multiple markers are rigidly attached together, Motive computes
      ONE pivot point (the rigid body origin) and streams THAT single point.
    - This pivot point is NOT at the same physical location as the MiR
      API's own reference point (usually the center of the wheel axis).
    - The vector between these two points is FIXED in the robot's own body
      frame, but its direction in the GLOBAL frame rotates with the robot's
      yaw. A plain rigid/similarity fit (scale+rotation+translation only)
      cannot absorb this correctly if yaw varies across calibration points
      -- it needs to be solved for explicitly, jointly with the global
      transform. That is exactly what this script does.

  What this script does, end to end:
    1. Connects to Motive (NatNet, local loopback) and to the MiR REST API.
    2. Auto-detects the robot's rigid body in Motive.
    3. Guides you through N calibration points (default 10, minimum 8),
       explicitly asking you to spread them across the WHOLE usable floor
       area (grid-like, not a line) and to use VARIED robot orientations
       (this makes the lever-arm mathematically observable).
    4. At each point, records: MiR (x, y, yaw) from the REST API, and
       Motive (x, y, z) of the robot rigid body -- FULL 3D, not just 2.
    5. Runs a sanity check on the Z (vertical) spread: it should be SMALL
       compared to the X/Y spread. If it isn't, something is physically
       wrong (tilted mount, wrong rigid body, sloped floor) and you are
       warned before wasting the whole session.
    6. Jointly fits (scale, rotation, translation, local lever-arm vector)
       via nonlinear least squares (scipy), using ALL points at once.
    7. Detects per-point outliers and lets you re-capture ONLY those points
       (without restarting from zero).
    8. Runs a REAL-TIME VALIDATION AGENT: drive the robot around freely,
       the agent compares predicted-vs-actual Motive position live, checks
       that Motive data is actually updating (catches silent freezes),
       checks that the robot actually moved (catches "forgot to drive it"),
       and prints a final PASS / WARNING / FAIL verdict with statistics.
    9. Saves EVERYTHING: a timestamped .pkl (raw points, fit, validation
       log, axis convention used), a timestamped .npy (2x3 similarity
       matrix, MiR->Motive), a "latest" copy of both for convenience, the
       INVERSE matrix (Motive->MiR) as a bonus .npy, and a human-readable
       .txt summary report.
   10. Data is saved incrementally after point collection and after fitting
       (not only at the very end), so a crash never loses your points.

  Output units: millimeters (mm) for all position/translation values,
  matching the convention already used in the rest of the project's
  Motive-side tooling. Radians for rotation internally; degrees also
  printed for human readability.
"""

import os
import sys
import time
import math
import pickle
import threading
import traceback
from datetime import datetime, timezone

import numpy as np
import requests

try:
    import cv2
except ImportError:
    cv2 = None  # optional, only used for a good initial guess

try:
    from scipy.optimize import least_squares
except ImportError:
    print("[ERROR] scipy is required (pip install scipy). Exiting.")
    sys.exit(1)

try:
    from NatNetClient import NatNetClient
except ImportError:
    print("[ERROR] NatNetClient.py not found. Please place it in the same directory.")
    sys.exit(1)


# ===========================================================================
# Configuration
# ===========================================================================
DEFAULT_MIR_IP = "192.168.12.20"
DEFAULT_NUM_POINTS = 10
MIN_NUM_POINTS = 8
SETTLING_TIME_SEC = 2.0

OUTPUT_DIR = "calibration_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTLIER_ABS_THRESHOLD_MM = 40.0
OUTLIER_STD_MULTIPLIER = 2.0

MIN_COLLINEARITY_RATIO = 0.05

# Sanity check: vertical (Z) spread should be much smaller than ground
# plane (X,Y) spread. If not, warn loudly.
MAX_ACCEPTABLE_VERTICAL_RATIO = 0.25  # vertical_range / ground_range

VALIDATION_DEFAULT_DURATION_SEC = 40.0
VALIDATION_PASS_THRESHOLD_MM = 80.0
VALIDATION_WARN_THRESHOLD_MM = 150.0
MIN_MEANINGFUL_MOVEMENT_MM = 500.0

# If Motive's reported position hasn't changed at all for this long during
# validation, we treat it as STALE data (Motive frozen / not streaming),
# not as "robot standing still".
MOTIVE_STALE_TIMEOUT_SEC = 1.0
MOTIVE_STALE_POSITION_EPS_MM = 0.05

AXIS_NAMES = ['x', 'y', 'z']
GROUND_IDX = [0, 1]   # CONFIRMED: Motive ground plane = (X, Y)
VERTICAL_IDX = 2      # CONFIRMED: Motive vertical axis = Z


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def safe_pickle_dump(obj, path):
    """Write to a temp file then rename, so a crash mid-write never
    corrupts the previous good file (lesson learned from the v10 incident)."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_path, path)


# ===========================================================================
# Motive / NatNet connector - records FULL 3D position + last-update time
# ===========================================================================
class MotiveConnector:
    def __init__(self):
        self.natnet_client = None
        self.id_to_name = {}
        self.rb_names = []
        self.latest_motive_pos = {}     # name -> (x_mm, y_mm, z_mm) or None
        self.latest_update_time = {}    # name -> time.time() of last update
        self.model_def_received = False

    def _on_model_definitions(self, data_descs):
        self.id_to_name = {}
        self.rb_names = []
        for desc in data_descs.rigid_body_list:
            rb_id = getattr(desc, 'id_num', getattr(desc, 'rigid_body_id', None))
            rb_name = getattr(desc, 'sz_name', getattr(desc, 'rb_name', None))
            if rb_id is not None and rb_name is not None:
                if isinstance(rb_name, bytes):
                    rb_name = rb_name.decode('utf-8', errors='ignore')
                self.id_to_name[rb_id] = rb_name
                if rb_name not in self.rb_names:
                    self.rb_names.append(rb_name)
        self.model_def_received = True

    def _on_rigid_body(self, new_id, position, rotation):
        if new_id not in self.id_to_name:
            return
        name = self.id_to_name[new_id]
        if position is not None and not np.isnan(position[0]):
            self.latest_motive_pos[name] = (
                position[0] * 1000.0, position[1] * 1000.0, position[2] * 1000.0
            )
        else:
            self.latest_motive_pos[name] = None
        self.latest_update_time[name] = time.time()

    def connect(self):
        client = NatNetClient()
        client.set_client_address('127.0.0.1')
        client.set_server_address('127.0.0.1')
        client.set_use_multicast(True)
        client.rigid_body_listener = self._on_rigid_body
        client.model_def_listener = self._on_model_definitions

        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        time.sleep(1.5)
        self.natnet_client = client

    def build_rigid_body_map(self):
        timeout_sock = 0
        while (not hasattr(self.natnet_client, 'command_socket')
               or self.natnet_client.command_socket is None) and timeout_sock < 30:
            time.sleep(0.1)
            timeout_sock += 1
        try:
            if self.natnet_client.command_socket is not None:
                self.natnet_client.send_request(
                    self.natnet_client.command_socket,
                    self.natnet_client.NAT_REQUEST_MODELDEF,
                    "",
                    (self.natnet_client.server_ip_address, self.natnet_client.command_port)
                )
        except Exception:
            pass

        timeout = 0
        while not self.model_def_received and timeout < 30:
            time.sleep(0.2)
            timeout += 1

    def is_fresh(self, name, max_age_sec=MOTIVE_STALE_TIMEOUT_SEC):
        t = self.latest_update_time.get(name)
        if t is None:
            return False
        return (time.time() - t) <= max_age_sec

    def shutdown(self):
        try:
            self.natnet_client.shutdown()
        except Exception:
            pass


# ===========================================================================
# MiR REST API connector
# ===========================================================================
class MirRobotAPI:
    def __init__(self, mir_ip):
        self.mir_ip = mir_ip
        self.status_url = f"http://{mir_ip}/api/v2.0.0/status"
        self.headers = {"Accept-Language": "en_US", "Content-Type": "application/json"}
        self._warned_no_orientation = False

    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=3)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None

    def get_pose_mm_rad(self, status=None):
        if status is None:
            status = self.get_status()
        if status is None:
            return None
        pos = status.get("position", {})
        if "x" not in pos or "y" not in pos:
            return None
        x_mm = pos["x"] * 1000.0
        y_mm = pos["y"] * 1000.0

        orientation_deg = pos.get("orientation", None)
        if orientation_deg is None:
            orientation_deg = status.get("orientation", None)
        if orientation_deg is None:
            if not self._warned_no_orientation:
                print("[WARNING] Could not find 'orientation' field in MiR status. "
                      "Yaw recorded as 0.0 -- lever-arm correction will be less accurate.")
                self._warned_no_orientation = True
            yaw_rad = 0.0
        else:
            yaw_rad = math.radians(orientation_deg)

        return x_mm, y_mm, yaw_rad


# ===========================================================================
# Calibration math: joint fit of (scale, rotation, translation, lever-arm)
# ===========================================================================
def initial_guess_from_similarity(mir_xy, motive_xy):
    if cv2 is not None:
        M, _ = cv2.estimateAffinePartial2D(
            mir_xy.astype(np.float32), motive_xy.astype(np.float32)
        )
        if M is not None:
            a, b = M[0, 0], M[1, 0]
            scale = math.hypot(a, b)
            theta = math.atan2(b, a)
            tx, ty = M[0, 2], M[1, 2]
            return scale, theta, tx, ty

    mu_src = mir_xy.mean(axis=0)
    mu_dst = motive_xy.mean(axis=0)
    src_c = mir_xy - mu_src
    dst_c = motive_xy - mu_dst
    cov = dst_c.T @ src_c / len(mir_xy)
    U, S, Vt = np.linalg.svd(cov)
    R = U @ Vt
    theta = math.atan2(R[1, 0], R[0, 0])
    var_src = (src_c ** 2).sum() / len(mir_xy)
    scale = np.sum(S) / var_src if var_src > 1e-9 else 1.0
    t = mu_dst - scale * (R @ mu_src)
    return scale, theta, t[0], t[1]


def residual_function(params, mir_xy, mir_yaw, motive_xy):
    scale, theta, tx, ty, lx, ly = params
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    cos_y = np.cos(mir_yaw)
    sin_y = np.sin(mir_yaw)
    lever_x = cos_y * lx - sin_y * ly
    lever_y = sin_y * lx + cos_y * ly

    marker_x = mir_xy[:, 0] + lever_x
    marker_y = mir_xy[:, 1] + lever_y

    pred_x = scale * (cos_t * marker_x - sin_t * marker_y) + tx
    pred_y = scale * (sin_t * marker_x + cos_t * marker_y) + ty

    res_x = pred_x - motive_xy[:, 0]
    res_y = pred_y - motive_xy[:, 1]
    return np.concatenate([res_x, res_y])


def fit_calibration(mir_xy, mir_yaw, motive_xy):
    scale0, theta0, tx0, ty0 = initial_guess_from_similarity(mir_xy, motive_xy)
    x0 = np.array([scale0, theta0, tx0, ty0, 0.0, 0.0])

    result = least_squares(
        residual_function, x0,
        args=(mir_xy, mir_yaw, motive_xy),
        method='lm', max_nfev=30000
    )
    scale, theta, tx, ty, lx, ly = result.x

    n = len(mir_xy)
    res = result.fun.reshape(2, n).T
    per_point_err_mm = np.linalg.norm(res, axis=1)

    similarity_matrix = np.array([
        [scale * math.cos(theta), -scale * math.sin(theta), tx],
        [scale * math.sin(theta),  scale * math.cos(theta), ty],
    ], dtype=np.float64)

    # Also compute the inverse transform (Motive -> MiR), handy for fusion
    # code that might need to go the other direction.
    inv_scale = 1.0 / scale
    inv_theta = -theta
    cos_i, sin_i = math.cos(inv_theta), math.sin(inv_theta)
    # Invert: p_mir = R^-1/scale * (p_motive - t)
    inv_R = np.array([[cos_i, -sin_i], [sin_i, cos_i]])
    t_vec = np.array([tx, ty])
    inv_t = -inv_scale * (inv_R @ t_vec)
    inverse_matrix = np.array([
        [inv_scale * cos_i, -inv_scale * sin_i, inv_t[0]],
        [inv_scale * sin_i,  inv_scale * cos_i, inv_t[1]],
    ], dtype=np.float64)

    return {
        "scale": float(scale),
        "rotation_rad": float(theta),
        "rotation_deg": float(math.degrees(theta)),
        "translation_mm": [float(tx), float(ty)],
        "lever_arm_local_mm": [float(lx), float(ly)],
        "similarity_matrix_mir_to_motive": similarity_matrix,
        "similarity_matrix_motive_to_mir": inverse_matrix,
        "per_point_residual_mm": per_point_err_mm.tolist(),
        "mean_error_mm": float(np.mean(per_point_err_mm)),
        "max_error_mm": float(np.max(per_point_err_mm)),
        "std_error_mm": float(np.std(per_point_err_mm)),
    }


def check_collinearity(mir_xy):
    centered = mir_xy - mir_xy.mean(axis=0)
    _, s, _ = np.linalg.svd(centered)
    if s[0] < 1e-9:
        return 0.0
    return float(s[1] / s[0])


def check_vertical_sanity(motive_xyz):
    ground = motive_xyz[:, GROUND_IDX]
    vertical = motive_xyz[:, VERTICAL_IDX]
    ground_range = float(np.max(ground.max(axis=0) - ground.min(axis=0)))
    vertical_range = float(vertical.max() - vertical.min())
    ratio = vertical_range / ground_range if ground_range > 1e-6 else float('inf')
    return {
        "ground_range_mm": ground_range,
        "vertical_range_mm": vertical_range,
        "ratio": ratio,
        "looks_sane": ratio <= MAX_ACCEPTABLE_VERTICAL_RATIO,
    }


# ===========================================================================
# Interactive calibration point collection
# ===========================================================================
class CalibrationSession:
    def __init__(self, target_rb_name, motive: MotiveConnector, mir_api: MirRobotAPI, autosave_path):
        self.target_rb_name = target_rb_name
        self.motive = motive
        self.mir_api = mir_api
        self.points = {}
        self.autosave_path = autosave_path

    def _autosave(self):
        try:
            safe_pickle_dump({"points_in_progress": self.points,
                               "saved_at_utc": utc_now_iso()}, self.autosave_path)
        except Exception as e:
            print(f"[WARNING] Could not autosave progress: {e}")

    def collect_point(self, index, total):
        while True:
            print("\n-----------------------------------------------------")
            input(f"POINT {index}/{total}: Drive the robot to a NEW spot via the dashboard.\n"
                  f"  - Spread points across the WHOLE floor (grid pattern, not a line).\n"
                  f"  - Orientation (yaw) does NOT need to match other points -- vary it freely.\n"
                  f"Press ENTER once the robot has arrived and is idle...")

            print("Monitoring MiR state API...")
            while True:
                status = self.mir_api.get_status()
                if status is None:
                    print("[WARNING] Waiting for MiR network connection...")
                    time.sleep(1)
                    continue

                if status.get("state_text", "") == "Ready":
                    print(f"Robot state is 'Ready'. Settling for {SETTLING_TIME_SEC}s...")
                    time.sleep(SETTLING_TIME_SEC)

                    final_status = self.mir_api.get_status()
                    if not final_status or final_status.get("state_text") != "Ready":
                        print("[INFO] State changed during settling. Resuming monitoring...")
                        time.sleep(0.5)
                        continue

                    pose = self.mir_api.get_pose_mm_rad(final_status)
                    if pose is None:
                        print("[ERROR] Could not read MiR position/orientation. Retrying...")
                        time.sleep(0.5)
                        continue

                    if not self.motive.is_fresh(self.target_rb_name, max_age_sec=2.0):
                        print(f"[ERROR] Motive data for '{self.target_rb_name}' looks STALE "
                              f"(not updating). Check the streaming connection.")
                        time.sleep(0.5)
                        continue

                    motive_pos = self.motive.latest_motive_pos.get(self.target_rb_name)
                    if motive_pos is None:
                        print(f"[ERROR] Motive lost track of '{self.target_rb_name}'!")
                        print("--> RETRYING this point. Fix tracking and press ENTER again.")
                        break

                    mir_x, mir_y, mir_yaw = pose
                    self.points[index] = {
                        "mir_x_mm": mir_x,
                        "mir_y_mm": mir_y,
                        "mir_yaw_rad": mir_yaw,
                        "mir_yaw_deg": math.degrees(mir_yaw),
                        "motive_x_mm": motive_pos[0],
                        "motive_y_mm": motive_pos[1],
                        "motive_z_mm": motive_pos[2],
                        "timestamp_utc": utc_now_iso(),
                    }
                    self._autosave()
                    print(f"\n[SYNCED] Point {index} captured!")
                    print(f"   MiR    (mm): X={mir_x:.1f}, Y={mir_y:.1f}, yaw={math.degrees(mir_yaw):.1f} deg")
                    print(f"   Motive (mm): X={motive_pos[0]:.1f}, Y={motive_pos[1]:.1f}, Z={motive_pos[2]:.1f}")
                    return True

                time.sleep(0.5)


# ===========================================================================
# Real-time validation agent
# ===========================================================================
def run_validation_agent(motive: MotiveConnector, mir_api: MirRobotAPI,
                          target_rb_name, fit, duration_sec):
    print("\n=====================================================")
    print(" REAL-TIME VALIDATION AGENT")
    print("=====================================================")
    print(f"Please ACTUALLY DRIVE the robot around for about {duration_sec:.0f} seconds.")
    print("Cover different positions AND orientations. Do not leave it parked.")
    print("The agent is watching... (Ctrl+C to stop early)\n")

    scale = fit["scale"]
    theta = fit["rotation_rad"]
    tx, ty = fit["translation_mm"]
    lx, ly = fit["lever_arm_local_mm"]
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    samples = []
    mir_positions_seen = []
    stale_warnings = 0
    start = time.time()
    last_print = 0.0
    last_motive_xy_for_freeze_check = None
    freeze_since = None

    try:
        while (time.time() - start) < duration_sec:
            status = mir_api.get_status()
            pose = mir_api.get_pose_mm_rad(status) if status else None
            motive_pos = motive.latest_motive_pos.get(target_rb_name)
            fresh = motive.is_fresh(target_rb_name)

            if not fresh:
                stale_warnings += 1
                if stale_warnings % 20 == 1:
                    print("  [WARNING] Motive data is STALE right now (not updating). "
                          "Check the streaming connection / marker visibility.")
                time.sleep(0.1)
                continue

            # Detect a frozen-value bug: same exact motive xy for too long
            # while status claims "fresh" (defensive double-check).
            if motive_pos is not None:
                cur_xy = (round(motive_pos[0], 3), round(motive_pos[1], 3))
                if last_motive_xy_for_freeze_check == cur_xy:
                    if freeze_since is None:
                        freeze_since = time.time()
                    elif time.time() - freeze_since > 3.0:
                        print("  [WARNING] Motive XY value has not changed at all for 3+ seconds. "
                              "If the robot IS moving, this indicates a data-freeze bug.")
                        freeze_since = time.time()  # avoid spamming
                else:
                    freeze_since = None
                last_motive_xy_for_freeze_check = cur_xy

            if pose is not None and motive_pos is not None:
                mir_x, mir_y, yaw = pose
                mir_positions_seen.append((mir_x, mir_y))

                cos_y, sin_y = math.cos(yaw), math.sin(yaw)
                lever_x = cos_y * lx - sin_y * ly
                lever_y = sin_y * lx + cos_y * ly
                marker_x = mir_x + lever_x
                marker_y = mir_y + lever_y

                pred_x = scale * (cos_t * marker_x - sin_t * marker_y) + tx
                pred_y = scale * (sin_t * marker_x + cos_t * marker_y) + ty

                actual_x = motive_pos[GROUND_IDX[0]]
                actual_y = motive_pos[GROUND_IDX[1]]

                err = math.hypot(pred_x - actual_x, pred_y - actual_y)
                samples.append({
                    "t": time.time() - start,
                    "predicted_motive_xy_mm": [pred_x, pred_y],
                    "actual_motive_xy_mm": [actual_x, actual_y],
                    "vertical_mm": motive_pos[VERTICAL_IDX],
                    "error_mm": err,
                })

                now = time.time() - start
                if now - last_print >= 1.0:
                    running_mean = np.mean([s["error_mm"] for s in samples])
                    print(f"  [t={now:5.1f}s] current_error={err:6.1f} mm | "
                          f"running_mean={running_mean:6.1f} mm | samples={len(samples)}")
                    last_print = now

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[INFO] Validation stopped early by user (Ctrl+C).")

    if not samples:
        print("\n[WARNING] No validation samples collected. Skipping verdict.")
        return {"ran": True, "num_samples": 0, "verdict": "NO_DATA"}

    mir_arr = np.array(mir_positions_seen)
    movement_span_mm = float(np.linalg.norm(mir_arr.max(axis=0) - mir_arr.min(axis=0))) if len(mir_arr) > 1 else 0.0

    errors = np.array([s["error_mm"] for s in samples])
    mean_err = float(np.mean(errors))
    max_err = float(np.max(errors))
    std_err = float(np.std(errors))

    movement_ok = movement_span_mm >= MIN_MEANINGFUL_MOVEMENT_MM

    if not movement_ok:
        verdict, symbol = "INCONCLUSIVE_NO_MOVEMENT", "[??]"
    elif mean_err <= VALIDATION_PASS_THRESHOLD_MM:
        verdict, symbol = "PASS", "[OK]"
    elif mean_err <= VALIDATION_WARN_THRESHOLD_MM:
        verdict, symbol = "WARNING", "[!!]"
    else:
        verdict, symbol = "FAIL", "[XX]"

    print("\n=====================================================")
    print(f" {symbol} VALIDATION AGENT VERDICT: {verdict}")
    print("=====================================================")
    print(f"   Robot movement span : {movement_span_mm:.0f} mm "
          f"({'OK' if movement_ok else 'TOO SMALL -- re-run and actually drive the robot'})")
    print(f"   Stale-data warnings : {stale_warnings}")
    print(f"   Samples collected   : {len(samples)}")
    print(f"   Mean error          : {mean_err:.1f} mm")
    print(f"   Max error           : {max_err:.1f} mm")
    print(f"   Std deviation       : {std_err:.1f} mm")

    if verdict == "PASS":
        print("   -> Calibration is GOOD. Safe to use in production sessions.")
    elif verdict == "WARNING":
        print("   -> Calibration is usable but noisy. Consider re-checking marker rigidity.")
    elif verdict == "INCONCLUSIVE_NO_MOVEMENT":
        print("   -> The robot barely moved during this test -- this validation proves nothing.")
    else:
        print("   -> Calibration quality is POOR. Something is still wrong (localization? "
              "marker mount loose? wrong rigid body?). Do not proceed until this is FAIL-free.")

    return {
        "ran": True, "duration_sec": duration_sec, "num_samples": len(samples),
        "movement_span_mm": movement_span_mm, "movement_ok": movement_ok,
        "stale_warnings": stale_warnings,
        "mean_error_mm": mean_err, "max_error_mm": max_err, "std_error_mm": std_err,
        "verdict": verdict, "samples": samples,
    }


# ===========================================================================
# Human-readable report writer
# ===========================================================================
def write_text_report(path, calibration_result):
    fit = calibration_result
    with open(path, "w", encoding="utf-8") as f:
        f.write("MiR <-> Motive Calibration Report\n")
        f.write("==================================\n")
        f.write(f"Timestamp (UTC)      : {calibration_result['timestamp_utc']}\n")
        f.write(f"MiR IP               : {calibration_result['mir_ip']}\n")
        f.write(f"Target rigid body    : {calibration_result['target_rigid_body']}\n")
        f.write(f"Num points used      : {calibration_result['num_points']}\n")
        f.write(f"Ground-plane axes    : Motive (X, Y)   [CONFIRMED Z-up project]\n")
        f.write(f"Vertical axis        : Motive Z\n\n")
        f.write("--- Fit result ---\n")
        f.write(f"scale                : {fit['scale']:.4f}  (expect close to 1.0)\n")
        f.write(f"rotation (deg)       : {fit['rotation_deg']:.2f}\n")
        f.write(f"translation (mm)     : {fit['translation_mm']}\n")
        f.write(f"lever_arm local (mm) : {fit['lever_arm_local_mm']}\n")
        f.write(f"mean error (mm)      : {fit['mean_error_mm']:.2f}\n")
        f.write(f"max error (mm)       : {fit['max_error_mm']:.2f}\n\n")
        f.write("--- Validation ---\n")
        v = calibration_result.get("validation", {})
        if v.get("ran"):
            f.write(f"verdict              : {v.get('verdict')}\n")
            f.write(f"mean error (mm)      : {v.get('mean_error_mm', 'n/a')}\n")
            f.write(f"movement span (mm)   : {v.get('movement_span_mm', 'n/a')}\n")
        else:
            f.write("Validation was not run.\n")
        f.write("\n--- Matrices ---\n")
        f.write("mir_to_motive (2x3, apply to MiR-frame points to get Motive-frame):\n")
        f.write(str(fit['similarity_matrix_mir_to_motive']) + "\n\n")
        f.write("motive_to_mir (2x3, inverse):\n")
        f.write(str(fit['similarity_matrix_motive_to_mir']) + "\n")


# ===========================================================================
# Main workflow
# ===========================================================================
def main():
    print("=====================================================")
    print("  MiR - OptiTrack Calibration Tool v4 (FINAL)")
    print("  Confirmed convention: Motive Up-Axis = Z,")
    print("  Ground plane = Motive(X, Y) <-> MiR(X, Y)")
    print("=====================================================\n")

    mir_ip = input(f"Enter the MiR robot IP address (default {DEFAULT_MIR_IP}): ").strip()
    if not mir_ip:
        mir_ip = DEFAULT_MIR_IP
        print(f"Using default IP: {mir_ip}")

    mir_api = MirRobotAPI(mir_ip)

    print("\nConnecting to local Motive stream (127.0.0.1)...")
    motive = MotiveConnector()
    motive.connect()
    motive.build_rigid_body_map()

    if not motive.rb_names:
        print("[CRITICAL] No Rigid Bodies found in Motive. Ensure streaming is ON.")
        return

    candidate_rb = None
    for name in motive.rb_names:
        if "mir" in name.lower() or "robot" in name.lower():
            candidate_rb = name
            break

    if candidate_rb:
        confirm = input(f"\nTarget robot detected as '{candidate_rb}'. Correct? (y/n) [y]: ").strip().lower()
        target_rb_name = candidate_rb if confirm in ('', 'y') else None
    else:
        target_rb_name = None

    if target_rb_name is None:
        print("\nAvailable Rigid Bodies in Motive:")
        for name in motive.rb_names:
            print(f"   - {name}")
        target_rb_name = input("\nEnter the exact name of the Robot's Rigid Body: ").strip()

    if target_rb_name not in motive.rb_names:
        print(f"[ERROR] '{target_rb_name}' not found. Exiting.")
        return

    print(f"\n[SUCCESS] Locked onto Rigid Body: '{target_rb_name}'.")

    num_points_input = input(
        f"\nHow many calibration points? (recommended {DEFAULT_NUM_POINTS}, "
        f"minimum {MIN_NUM_POINTS}) [default {DEFAULT_NUM_POINTS}]: "
    ).strip()
    try:
        num_points = int(num_points_input) if num_points_input else DEFAULT_NUM_POINTS
    except ValueError:
        num_points = DEFAULT_NUM_POINTS
    num_points = max(num_points, MIN_NUM_POINTS)

    print(f"\n[GUIDANCE -- read carefully, this is your LAST calibration run]:")
    print(f"  1) Spread the {num_points} points across the ENTIRE usable floor area,")
    print(f"     ideally in a grid pattern (e.g. corners + center + edges).")
    print(f"  2) Vary the robot's ORIENTATION between points as much as possible")
    print(f"     (this is what makes the lever-arm mathematically solvable).")
    print(f"  3) Do NOT rush the settling time -- let the robot fully stop.")
    print(f"  4) Watch for '[ERROR] Motive lost track' messages -- fix marker")
    print(f"     visibility before continuing if that happens.")

    autosave_path = os.path.join(OUTPUT_DIR, "_autosave_in_progress.pkl")
    session = CalibrationSession(target_rb_name, motive, mir_api, autosave_path)

    try:
        idx = 1
        while idx <= num_points:
            session.collect_point(idx, num_points)
            idx += 1

        def build_arrays(points_dict):
            indices = sorted(points_dict.keys())
            mir_xy = np.array([[points_dict[i]["mir_x_mm"], points_dict[i]["mir_y_mm"]] for i in indices])
            mir_yaw = np.array([points_dict[i]["mir_yaw_rad"] for i in indices])
            motive_xyz = np.array([[points_dict[i]["motive_x_mm"],
                                     points_dict[i]["motive_y_mm"],
                                     points_dict[i]["motive_z_mm"]] for i in indices])
            return indices, mir_xy, mir_yaw, motive_xyz

        # ---- Vertical-axis sanity check (should already be sane, this is
        #      a safety net in case something is physically off) ----
        indices, mir_xy, mir_yaw, motive_xyz = build_arrays(session.points)
        vsanity = check_vertical_sanity(motive_xyz)
        print("\n=====================================================")
        print(" VERTICAL AXIS SANITY CHECK")
        print("=====================================================")
        print(f"   Ground-plane (X,Y) range : {vsanity['ground_range_mm']:.1f} mm")
        print(f"   Vertical (Z) range       : {vsanity['vertical_range_mm']:.1f} mm")
        print(f"   Ratio (vertical/ground)  : {vsanity['ratio']:.3f} "
              f"(should be <= {MAX_ACCEPTABLE_VERTICAL_RATIO})")
        if not vsanity["looks_sane"]:
            print("   [WARNING] Vertical spread is unexpectedly large relative to the "
                  "ground-plane spread. Double-check: is this really the robot's rigid "
                  "body? Is the floor flat? Is the marker mount loose/tilted?")
            proceed = input("   Proceed anyway? (y/n) [n]: ").strip().lower()
            if proceed != 'y':
                print("Aborting. Please investigate before re-running.")
                return
        else:
            print("   [OK] Vertical axis behaves as expected (nearly constant height).")

        # ---- Fit, check collinearity & outliers, allow re-capture ----
        collinearity_ratio = None
        fit = None
        for attempt in range(4):
            indices, mir_xy, mir_yaw, motive_xyz = build_arrays(session.points)
            motive_xy = motive_xyz[:, GROUND_IDX]

            collinearity_ratio = check_collinearity(mir_xy)
            if collinearity_ratio < MIN_COLLINEARITY_RATIO:
                print(f"\n[WARNING] Points look nearly COLLINEAR (ratio={collinearity_ratio:.3f}). "
                      f"Fit may be unreliable -- consider adding more spread-out points.")

            fit = fit_calibration(mir_xy, mir_yaw, motive_xy)

            print("\n=====================================================")
            print(f"FIT RESULT (attempt {attempt + 1}):")
            print(f"   scale             = {fit['scale']:.4f}  (should be close to 1.0)")
            print(f"   rotation          = {fit['rotation_deg']:.2f} deg")
            print(f"   translation (mm)  = {fit['translation_mm']}")
            print(f"   lever_arm (mm)    = {fit['lever_arm_local_mm']}")
            print(f"   mean error (mm)   = {fit['mean_error_mm']:.2f}")
            print(f"   max error (mm)    = {fit['max_error_mm']:.2f}")
            print("\n   Per-point residuals (mm):")
            for i, err in zip(indices, fit["per_point_residual_mm"]):
                flag = ""
                if err > max(OUTLIER_ABS_THRESHOLD_MM,
                             fit["mean_error_mm"] + OUTLIER_STD_MULTIPLIER * fit["std_error_mm"]):
                    flag = "   <-- OUTLIER?"
                print(f"      Point {i}: {err:6.2f} mm{flag}")

            if abs(fit["scale"] - 1.0) > 0.15:
                print(f"\n[WARNING] Fitted scale ({fit['scale']:.3f}) deviates from 1.0 by "
                      f"more than 15%. With confirmed correct axes, this now most likely "
                      f"points to a MiR localization problem during data collection "
                      f"(not an axis bug anymore). Consider checking robot localization "
                      f"quality before proceeding.")

            outlier_indices = [
                i for i, err in zip(indices, fit["per_point_residual_mm"])
                if err > max(OUTLIER_ABS_THRESHOLD_MM,
                             fit["mean_error_mm"] + OUTLIER_STD_MULTIPLIER * fit["std_error_mm"])
            ]

            if not outlier_indices:
                print("\n[OK] No outlier points detected. Proceeding with this fit.")
                break

            answer = input(f"\nPoints {outlier_indices} look like outliers. Re-capture them? (y/n) [y]: ").strip().lower()
            if answer == 'n':
                print("Proceeding with current fit despite outliers.")
                break

            for i in outlier_indices:
                session.collect_point(i, num_points)

        # ---- Save calibration result (before validation, so it's never lost) ----
        timestamp_tag = datetime.now().strftime('%Y%m%d_%H%M%S')

        calibration_result = {
            "schema_version": "calib_v4_final",
            "timestamp_utc": utc_now_iso(),
            "mir_ip": mir_ip,
            "target_rigid_body": target_rb_name,
            "units": "mm",
            "num_points": len(session.points),
            "raw_points": session.points,
            "axis_convention": {
                "ground_axes": ["x", "y"],
                "vertical_axis": "z",
                "note": "Confirmed via Motive project settings: Up Axis = Z."
            },
            "vertical_sanity_check": vsanity,
            "collinearity_ratio": collinearity_ratio,
            **fit,
            "validation": {"ran": False},
        }

        pkl_path = os.path.join(OUTPUT_DIR, f"calibration_{timestamp_tag}.pkl")
        pkl_path_latest = os.path.join(OUTPUT_DIR, "latest_calibration.pkl")
        npy_path_ts = os.path.join(OUTPUT_DIR, f"mir_to_motive_matrix_{timestamp_tag}.npy")
        npy_path_latest = os.path.join(OUTPUT_DIR, "mir_to_motive_matrix.npy")
        npy_inv_path_ts = os.path.join(OUTPUT_DIR, f"motive_to_mir_matrix_{timestamp_tag}.npy")
        npy_inv_path_latest = os.path.join(OUTPUT_DIR, "motive_to_mir_matrix.npy")
        txt_report_path = os.path.join(OUTPUT_DIR, f"calibration_report_{timestamp_tag}.txt")

        safe_pickle_dump(calibration_result, pkl_path)
        safe_pickle_dump(calibration_result, pkl_path_latest)
        np.save(npy_path_ts, fit["similarity_matrix_mir_to_motive"])
        np.save(npy_path_latest, fit["similarity_matrix_mir_to_motive"])
        np.save(npy_inv_path_ts, fit["similarity_matrix_motive_to_mir"])
        np.save(npy_inv_path_latest, fit["similarity_matrix_motive_to_mir"])
        write_text_report(txt_report_path, calibration_result)

        print("\n[SAVED] Calibration fit saved (pre-validation) to disk.")

        # ---- Optional real-time validation agent ----
        run_agent = input("\nRun the real-time validation agent now? (y/n) [y]: ").strip().lower()
        if run_agent in ('', 'y'):
            dur_input = input(f"Validation duration in seconds [default {VALIDATION_DEFAULT_DURATION_SEC:.0f}]: ").strip()
            try:
                duration_sec = float(dur_input) if dur_input else VALIDATION_DEFAULT_DURATION_SEC
            except ValueError:
                duration_sec = VALIDATION_DEFAULT_DURATION_SEC

            validation_log = run_validation_agent(motive, mir_api, target_rb_name, fit, duration_sec)
            calibration_result["validation"] = validation_log

            # Re-save with validation results included.
            safe_pickle_dump(calibration_result, pkl_path)
            safe_pickle_dump(calibration_result, pkl_path_latest)
            write_text_report(txt_report_path, calibration_result)

        print("\n=====================================================")
        print("[SUCCESS] Calibration complete and saved:")
        print(f"   {pkl_path}")
        print(f"   {pkl_path_latest}")
        print(f"   {npy_path_ts}")
        print(f"   {npy_path_latest}  (MiR -> Motive, use this in the fusion pipeline)")
        print(f"   {npy_inv_path_latest}  (Motive -> MiR, bonus/optional)")
        print(f"   {txt_report_path}")
        print("=====================================================")

        # Clean up the autosave file since we finished successfully.
        try:
            if os.path.exists(autosave_path):
                os.remove(autosave_path)
        except Exception:
            pass

    except Exception as e:
        print(f"\n[CRITICAL] Unexpected error: {e}")
        traceback.print_exc()
        print(f"\n[RECOVERY] Your points collected so far are autosaved at:")
        print(f"   {autosave_path}")
        print("You can inspect/recover them manually with pickle.load() if needed.")

    finally:
        motive.shutdown()


if __name__ == '__main__':
    main()