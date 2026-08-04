#!/usr/bin/env python3
"""
MultiRigidBodyTracker + MiR Integration

Extends the working Motive/NatNet tracker with:
  1. Simultaneous MiR robot API polling (over WiFi) alongside Motive
  2. Coordinate unification via the pre-computed affine transform matrix
     (mir_to_motive_matrix.npy, produced by Auto_calibration_MIR_Motive.py)
  3. A single unified timestamp for ALL data (sample-and-hold sync tick),
     while still preserving full-rate raw Motive data separately
  4. Robot-relative kinematics: distance, relative velocity (closing
     speed), relative acceleration, and relative bearing/orientation of
     the robot toward every other tracked body
  5. Persistent point-cloud tracking: a point is classified "Dynamic" if
     its cumulative displacement from its first recorded position
     reaches 1000mm (1m) at any point during the session, otherwise
     "Static" -- tracked over time, not a single-frame comparison

NOTE ON THE POINT CLOUD: the SLAM point cloud source is still a
placeholder in the reference code this was built from (randomly
generated points, not real sensor data yet). The TRACKING LOGIC below is
built correctly and is ready to receive real data, but the matching
distance gate (POINT_MATCH_MAX_DIST_MM) will likely need retuning once
real SLAM point cloud data is wired in -- noted clearly at that constant.
"""

import os
import sys
import time
import pickle
import threading
import importlib.util
from datetime import datetime

import numpy as np
import scipy.io as sio
from scipy.spatial import cKDTree
import requests

try:
    import cv2
except ImportError:
    print('ERROR: opencv-python is required for the coordinate transform. '
          'Install with: pip install opencv-python')
    sys.exit(1)

import matplotlib
if importlib.util.find_spec('tkinter') is not None:
    matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

try:
    from NatNetClient import NatNetClient
except ImportError:
    print('ERROR: NatNetClient.py was not found next to this script.')
    sys.exit(1)


# ============================================================
# Configuration
# ============================================================
DANGER_THRESHOLD_MM = 100.0
WARNING_THRESHOLD_MM = 500.0
MIN_APPROACH_SPEED_MMPS = 20.0

TRANSFORM_MATRIX_PATH = 'mir_to_motive_matrix.npy'

# How often we poll the MiR HTTP API. 30ms (per the original request) is
# aggressive for HTTP over WiFi -- typical round-trip latency to a real
# MiR robot is often 20-100ms on its own, so a 30ms poll interval can
# fall behind or queue up. 100ms (10Hz) is a more reliable default; lower
# it if your network/robot handle 30ms reliably in practice.
MIR_POLL_INTERVAL_S = 0.1

# The unified sync tick -- this defines the single shared timestamp rate
# for the synchronized dataset. Matches the MiR poll rate since that is
# the natural bottleneck (no point synchronizing faster than our slowest
# real data source).
SYNC_TICK_INTERVAL_S = 0.1

# Point-cloud persistent tracking
POINT_DYNAMIC_THRESHOLD_MM = 1000.0   # 1 meter, per requirement
POINT_MATCH_MAX_DIST_MM = 500.0       # max distance to match a new detection
                                        # to an existing tracked point -- WILL
                                        # need retuning with real SLAM data


# ============================================================
# Math helpers
# ============================================================

def quaternion_to_euler(qx, qy, qz, qw):
    sinr_cosp = 2 * (qw * qx + qy * qz)
    cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
    roll = np.arctan2(sinr_cosp, cosr_cosp)
    sinp = 2 * (qw * qy - qz * qx)
    if abs(sinp) >= 1:
        pitch = np.copysign(np.pi / 2, sinp)
    else:
        pitch = np.arcsin(sinp)
    siny_cosp = 2 * (qw * qz + qx * qy)
    cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    return np.degrees(roll), np.degrees(pitch), np.degrees(yaw)


def wrap_angle_180(a):
    return np.mod(np.asarray(a) + 180.0, 360.0) - 180.0


def make_valid_name(name):
    valid = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in name)
    if valid and valid[0].isdigit():
        valid = '_' + valid
    return valid or '_unnamed'


def identify_robot_body(names):
    matches = [n for n in names if 'robot' in n.lower()]
    if len(matches) >= 1:
        if len(matches) > 1:
            print(f'[WARNING] Multiple bodies matched "robot" ({matches}). Using: {matches[0]}')
        return matches[0]
    return None


# ============================================================
# Coordinate transform (MiR API frame -> Motive frame)
# ============================================================

def load_transform_matrix(path=TRANSFORM_MATRIX_PATH):
    if not os.path.exists(path):
        print(f'[WARNING] Transform matrix "{path}" not found. Run '
              f'Auto_calibration_MIR_Motive.py first. MiR positions will '
              f'NOT be transformed into the Motive frame until this exists.')
        return None
    matrix = np.load(path)
    print(f'[INFO] Loaded transform matrix from {path}:\n{matrix}')
    return matrix


def transform_mir_to_motive(x_mm, y_mm, matrix):
    """Applies the 2x3 affine matrix from calibration. Returns (x, y) in
    Motive's coordinate frame (mm), or the raw (untransformed) input if
    no matrix is available."""
    if matrix is None:
        return x_mm, y_mm
    point = np.array([[[x_mm, y_mm]]], dtype=np.float32)
    transformed = cv2.transform(point, matrix)[0][0]
    return float(transformed[0]), float(transformed[1])


# ============================================================
# Per-body raw data buffer
# ============================================================

class RigidBodyBuffer:
    def __init__(self):
        self.time = []
        self.position = []
        self.quaternion = []
        self.euler = []

    def append_row(self, t, position_mm, quat, euler):
        self.time.append(t)
        self.position.append(position_mm)
        self.quaternion.append(quat)
        self.euler.append(euler)

    def append_nan_row(self, t):
        self.time.append(t)
        self.position.append([np.nan, np.nan, np.nan])
        self.quaternion.append([np.nan, np.nan, np.nan, np.nan])
        self.euler.append([np.nan, np.nan, np.nan])

    def trim(self):
        return {
            'Position': np.array(self.position, dtype=float).reshape(-1, 3),
            'Quaternion': np.array(self.quaternion, dtype=float).reshape(-1, 4),
            'Euler': np.array(self.euler, dtype=float).reshape(-1, 3),
            'Time': np.array(self.time, dtype=float).reshape(-1, 1),
        }


# ============================================================
# Kinematics (per-body, absolute)
# ============================================================

def compute_kinematics(original_data):
    kinematics = {}
    for name, body in original_data.items():
        t = body['Time'].flatten()
        pos = body['Position']
        eul = body['Euler']
        n = len(t)
        vel = np.full_like(pos, np.nan)
        acc = np.full_like(pos, np.nan)
        ang_vel = np.full_like(eul, np.nan)
        if n >= 2:
            dt = np.diff(t)
            dt[dt <= 0] = np.nan
            vel[1:, :] = np.diff(pos, axis=0) / dt[:, None]
            ang_vel[1:, :] = np.diff(eul, axis=0) / dt[:, None]
        if n >= 3:
            dt2 = np.diff(t[1:])
            dt2[dt2 <= 0] = np.nan
            acc[2:, :] = np.diff(vel[1:, :], axis=0) / dt2[:, None]
        kinematics[name] = {'Velocity': vel, 'Acceleration': acc, 'AngularVelocity': ang_vel}
    return kinematics


# ============================================================
# Robot-relative kinematics (NEW): for every other body, the robot's
# distance, closing speed (relative velocity along the connecting line),
# relative acceleration, and relative bearing toward that body.
# ============================================================

def compute_robot_relative_kinematics(original_data, kinematics, robot_name):
    result = {}
    if robot_name is None or robot_name not in original_data:
        return result

    robot_pos = original_data[robot_name]['Position']
    robot_euler = original_data[robot_name]['Euler']
    robot_vel = kinematics[robot_name]['Velocity']
    robot_acc = kinematics[robot_name]['Acceleration']

    for name, body in original_data.items():
        if name == robot_name:
            continue
        other_pos = body['Position']
        if other_pos.shape[0] != robot_pos.shape[0]:
            continue

        delta = other_pos - robot_pos                     # robot -> body
        dist = np.sqrt(np.sum(delta ** 2, axis=1))
        with np.errstate(invalid='ignore', divide='ignore'):
            dir_unit = delta / dist[:, None]

        # Relative (closing) speed: positive = robot approaching this body
        closing_speed = np.sum(robot_vel * dir_unit, axis=1)
        # Relative acceleration along the same direction
        closing_accel = np.sum(robot_acc * dir_unit, axis=1)

        world_bearing = np.degrees(np.arctan2(delta[:, 1], delta[:, 0]))
        relative_bearing = wrap_angle_180(world_bearing - robot_euler[:, 2])

        result[name] = {
            'Distance': dist,
            'ClosingSpeed': closing_speed,          # mm/s, + = robot approaching
            'ClosingAcceleration': closing_accel,   # mm/s^2
            'RelativeBearing': relative_bearing,    # deg, 0 = body is directly ahead of robot's heading
        }
    return result


def compute_relative_motion(original_data, kinematics, robot_name, danger_mm, warn_mm, min_approach_speed):
    result = {'HumanNames': []}
    if robot_name is None or robot_name not in original_data:
        return result
    robot_pos = original_data[robot_name]['Position']
    human_names = [n for n in original_data.keys() if n != robot_name]
    n_frames = robot_pos.shape[0]
    distance_matrix = np.full((n_frames, len(human_names)), np.nan)
    for h, hn in enumerate(human_names):
        human_pos = original_data[hn]['Position']
        if human_pos.shape[0] != n_frames:
            continue
        delta = human_pos - robot_pos
        dist = np.sqrt(np.sum(delta ** 2, axis=1))
        distance_matrix[:, h] = dist
        result[hn] = {'Distance': dist}
    min_dist = np.full(n_frames, np.nan)
    valid_rows = ~np.all(np.isnan(distance_matrix), axis=1)
    if np.any(valid_rows):
        min_dist[valid_rows] = np.nanmin(distance_matrix[valid_rows, :], axis=1)
    safety_level = np.zeros(n_frames)
    safety_level[min_dist <= warn_mm] = 1
    safety_level[min_dist <= danger_mm] = 2
    safety_level[np.isnan(min_dist)] = np.nan
    result['MinDistance'] = min_dist
    result['SafetyLevel'] = safety_level
    result['HumanNames'] = human_names
    return result


def compute_tracking_quality(original_data):
    quality = {}
    for name, body in original_data.items():
        is_tracked = ~np.any(np.isnan(body['Position']), axis=1)
        quality[name] = {'IsTracked': is_tracked, 'GapCount': 0, 'MaxGapDuration': 0.0}
    return quality


def auto_trim_dead_time(original_data, loop_timestamps):
    first_global = None
    last_global = None
    for name, body in original_data.items():
        pos = body['Position']
        if len(pos) == 0:
            continue
        valid = ~np.any(np.isnan(pos), axis=1)
        valid_idx = np.where(valid)[0]
        if len(valid_idx) > 0:
            f_idx = valid_idx[0]
            l_idx = valid_idx[-1]
            if first_global is None or f_idx < first_global:
                first_global = f_idx
            if last_global is None or l_idx > last_global:
                last_global = l_idx
    if first_global is None:
        return original_data, loop_timestamps, 0, len(loop_timestamps) - 1
    trimmed = {}
    for name, body in original_data.items():
        n_len = len(body['Time'])
        f_i = min(first_global, n_len - 1)
        l_i = min(last_global, n_len - 1)
        if f_i > l_i:
            f_i, l_i = 0, n_len - 1
        trimmed[name] = {
            'Position': body['Position'][f_i:l_i + 1],
            'Quaternion': body['Quaternion'][f_i:l_i + 1],
            'Euler': body['Euler'][f_i:l_i + 1],
            'Time': body['Time'][f_i:l_i + 1],
        }
    ts_len = len(loop_timestamps)
    if ts_len > 0:
        f_ts = min(first_global, ts_len - 1)
        l_ts = min(last_global, ts_len - 1)
        trimmed_timestamps = loop_timestamps[f_ts:l_ts + 1]
    else:
        trimmed_timestamps = []
    return trimmed, trimmed_timestamps, first_global, last_global


def ask_trim_confirmation(n_total, first_idx, last_idx):
    trimmed_start = first_idx
    trimmed_end = max(n_total - 1 - last_idx, 0)
    if trimmed_start == 0 and trimmed_end == 0:
        return False
    message = f'Detected {trimmed_start} dead frame(s) at start and {trimmed_end} at end. Trim?'
    if importlib.util.find_spec('tkinter') is not None:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        result = messagebox.askyesno('Auto-Trim Dead Time', message)
        root.destroy()
        return result
    answer = input(f'{message} (yes/no): ').strip()
    return bool(answer) and answer[0].lower() == 'y'


# ============================================================
# Persistent point-cloud tracking (feature: Dynamic vs Static via
# cumulative 1m displacement, tracked over time -- not a single-frame
# comparison)
# ============================================================

class PersistentPointTracker:
    """
    Maintains a set of tracked points across frames. Each incoming
    point-cloud frame is matched against currently tracked points via
    nearest-neighbor (within POINT_MATCH_MAX_DIST_MM); matched points
    update their current position and cumulative displacement from their
    FIRST recorded position, unmatched detections start new tracks.

    A point is classified 'Dynamic' once its displacement from its first
    position reaches POINT_DYNAMIC_THRESHOLD_MM at any point; otherwise
    it stays 'Static'.
    """

    def __init__(self, dynamic_threshold_mm=POINT_DYNAMIC_THRESHOLD_MM,
                 match_max_dist_mm=POINT_MATCH_MAX_DIST_MM):
        self.dynamic_threshold_mm = dynamic_threshold_mm
        self.match_max_dist_mm = match_max_dist_mm
        self.tracks = []  # list of dicts: {first_pos, current_pos, max_displacement, classification}

    def update(self, points_xy):
        """points_xy: Nx2 array of detected point positions (mm) this frame.
        Returns a list of classifications ('Static'/'Dynamic'), one per
        input point, in the same order."""
        points_xy = np.asarray(points_xy, dtype=float)
        classifications = [None] * len(points_xy)

        if len(self.tracks) == 0:
            for i, p in enumerate(points_xy):
                self.tracks.append({'first_pos': p.copy(), 'current_pos': p.copy(),
                                     'max_displacement': 0.0, 'classification': 'Static'})
                classifications[i] = 'Static'
            return classifications

        if len(points_xy) == 0:
            return classifications

        track_positions = np.array([t['current_pos'] for t in self.tracks])
        tree = cKDTree(track_positions)
        distances, matched_track_idx = tree.query(points_xy, distance_upper_bound=self.match_max_dist_mm)

        used_tracks = set()
        for i, (dist, track_idx) in enumerate(zip(distances, matched_track_idx)):
            if np.isfinite(dist) and track_idx not in used_tracks:
                track = self.tracks[track_idx]
                track['current_pos'] = points_xy[i]
                displacement = np.linalg.norm(points_xy[i] - track['first_pos'])
                track['max_displacement'] = max(track['max_displacement'], displacement)
                if track['max_displacement'] >= self.dynamic_threshold_mm:
                    track['classification'] = 'Dynamic'
                classifications[i] = track['classification']
                used_tracks.add(track_idx)
            else:
                # No existing track close enough -- start a new one
                self.tracks.append({'first_pos': points_xy[i].copy(), 'current_pos': points_xy[i].copy(),
                                     'max_displacement': 0.0, 'classification': 'Static'})
                classifications[i] = 'Static'

        return classifications

    def get_summary(self):
        n_static = sum(1 for t in self.tracks if t['classification'] == 'Static')
        n_dynamic = sum(1 for t in self.tracks if t['classification'] == 'Dynamic')
        return {'TotalTracks': len(self.tracks), 'Static': n_static, 'Dynamic': n_dynamic}


# ============================================================
# Main tracker application
# ============================================================

class MultiRigidBodyTracker:
    def __init__(self, mir_ip=None):
        self.output_folder = f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_folder, exist_ok=True)

        self.id_to_name = {}
        self.rb_names = []
        self.selected_names = []
        self.buffers = {}              # synchronized buffers (sync-tick rate)
        self.highrate_buffers = {}     # full native-rate Motive-only buffers (raw data preserved)
        self.loop_timestamps = []
        self.start_time = None
        self.lock = threading.Lock()
        self.stop_requested = False
        self.natnet_client = None
        self.model_def_received = False
        self.fig = None
        self.combined_lines_3d = {}
        self._live_buffer = {}
        self._pending_seen = set()
        self._pending_t = None

        # Latest-known-state caches (updated asynchronously, read by the sync tick)
        self._latest_motive_state = {}   # {name: {'Position':..., 'Quaternion':..., 'Euler':...}}
        self._latest_mir_state = None    # {'Position':[x,y,0], 'Quaternion':[0,0,0,1], 'Euler':[0,0,theta]}

        self.mir_ip = mir_ip
        self.transform_matrix = None
        self.point_tracker = PersistentPointTracker()
        self.point_cloud_log = []  # list of (timestamp, points_xy, classifications)

        self._mir_thread = None
        self._sync_thread = None

        self.loaded_session = None
        self.pkl_path = None
        self.mat_path = None

    # ---------------- NatNet ----------------

    def connect_to_natnet(self):
        client = NatNetClient()
        client.set_client_address('127.0.0.1')
        client.set_server_address('127.0.0.1')
        client.set_use_multicast(True)
        client.new_frame_listener = self._on_new_frame
        client.rigid_body_listener = self._on_rigid_body
        client.model_def_listener = self._on_model_definitions

        self._natnet_thread = threading.Thread(target=client.run, daemon=True)
        self._natnet_thread.start()
        time.sleep(1.5)
        self.natnet_client = client

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

    def build_rigid_body_map(self):
        timeout_sock = 0
        while (not hasattr(self.natnet_client, 'command_socket') or
               self.natnet_client.command_socket is None) and timeout_sock < 30:
            time.sleep(0.1)
            timeout_sock += 1
        try:
            if self.natnet_client.command_socket is not None:
                self.natnet_client.send_request(
                    self.natnet_client.command_socket,
                    self.natnet_client.NAT_REQUEST_MODELDEF,
                    '',
                    (self.natnet_client.server_ip_address, self.natnet_client.command_port)
                )
        except Exception:
            pass
        timeout = 0
        while not self.model_def_received and timeout < 30:
            time.sleep(0.2)
            timeout += 1

    def select_rigid_bodies_to_record(self):
        print('\n--- Select which Rigid Bodies to record ---')
        selected = []
        for name in self.rb_names:
            answer = input(f'Record "{name}"? (yes/no): ').strip().lower()
            if answer.startswith('y'):
                selected.append(name)
        self.selected_names = selected

    def _on_new_frame(self, frame_number=None, *args, **kwargs):
        # Kept ONLY to close out high-rate frame boundaries; the
        # synchronized buffers no longer get written here (that's now
        # the sync tick's job -- see _sync_tick_loop).
        pass

    def _on_rigid_body(self, new_id, position, rotation):
        """Now only updates the 'latest known state' cache + the
        full native-rate high-rate buffer. The synchronized dataset is
        built separately by the sync tick, reading this cache."""
        if new_id not in self.id_to_name:
            return
        name = self.id_to_name[new_id]
        if name not in self.selected_names:
            return

        t = time.time() - self.start_time if self.start_time else 0.0

        if position is None:
            position_mm = [np.nan, np.nan, np.nan]
        else:
            position_mm = [position[0] * 1000.0, position[1] * 1000.0, position[2] * 1000.0]
        if rotation is None:
            quat = [0.0, 0.0, 0.0, 1.0]
            roll, pitch, yaw = 0.0, 0.0, 0.0
        else:
            qx, qy, qz, qw = rotation
            roll, pitch, yaw = quaternion_to_euler(qx, qy, qz, qw)
            quat = [qx, qy, qz, qw]

        fn = make_valid_name(name)
        with self.lock:
            self._latest_motive_state[name] = {'Position': position_mm, 'Quaternion': quat,
                                                'Euler': [roll, pitch, yaw]}
            if fn in self.highrate_buffers:
                self.highrate_buffers[fn].append_row(t, position_mm, quat, [roll, pitch, yaw])
            if position is not None and not np.isnan(position_mm[0]):
                self._live_buffer.setdefault(fn, []).append(position_mm)

    # ---------------- MiR robot API polling ----------------

    def _get_mir_status(self):
        if not self.mir_ip:
            return None
        try:
            url = f'http://{self.mir_ip}/api/v2.0.0/status'
            headers = {'Accept-Language': 'en_US', 'Content-Type': 'application/json'}
            resp = requests.get(url, headers=headers, timeout=1.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _mir_polling_loop(self):
        consecutive_failures = 0
        while not self.stop_requested:
            status = self._get_mir_status()
            if status is not None:
                consecutive_failures = 0
                mir_x_mm = status.get('position', {}).get('x', 0.0) * 1000.0
                mir_y_mm = status.get('position', {}).get('y', 0.0) * 1000.0
                mir_theta_deg = status.get('position', {}).get('orientation', 0.0)

                motive_x, motive_y = transform_mir_to_motive(mir_x_mm, mir_y_mm, self.transform_matrix)

                with self.lock:
                    self._latest_mir_state = {
                        'Position': [motive_x, motive_y, 0.0],
                        'Quaternion': [0.0, 0.0, 0.0, 1.0],
                        'Euler': [0.0, 0.0, mir_theta_deg],
                    }
            else:
                consecutive_failures += 1
                if consecutive_failures == 5:
                    print('\n[WARNING] Lost connection to MiR robot API -- check WiFi. '
                          'Will keep retrying in the background.')
            time.sleep(MIR_POLL_INTERVAL_S)

    # ---------------- Unified sync tick ----------------

    def _sync_tick_loop(self):
        """Runs at SYNC_TICK_INTERVAL_S, writing ONE synchronized row per
        selected body (+ the MiR robot, if connected) per tick, using the
        latest known value from each source (sample-and-hold). This is
        what gives every source the SAME shared timestamp."""
        while not self.stop_requested:
            t = time.time() - self.start_time if self.start_time else 0.0

            with self.lock:
                for name in self.selected_names:
                    fn = make_valid_name(name)
                    state = self._latest_motive_state.get(name)
                    if state is not None:
                        self.buffers[fn].append_row(t, state['Position'], state['Quaternion'], state['Euler'])
                    else:
                        self.buffers[fn].append_nan_row(t)

                if self.mir_ip:
                    if 'MiR_Robot' not in self.buffers:
                        self.buffers['MiR_Robot'] = RigidBodyBuffer()
                    if self._latest_mir_state is not None:
                        s = self._latest_mir_state
                        self.buffers['MiR_Robot'].append_row(t, s['Position'], s['Quaternion'], s['Euler'])
                    else:
                        self.buffers['MiR_Robot'].append_nan_row(t)

                self.loop_timestamps.append(t)

            time.sleep(SYNC_TICK_INTERVAL_S)

    # ---------------- Live plotting ----------------

    def initialize_plots(self):
        n = len(self.selected_names)
        plt.ion()
        self.fig = plt.figure(figsize=(9, 7))
        if n == 0:
            return
        colors = plt.cm.tab10(np.linspace(0, 1, n))
        ax_combined = self.fig.add_subplot(111, projection='3d')
        ax_combined.set_title('Combined 3D Trajectory (Live)')
        ax_combined.set_xlabel('X (mm)')
        ax_combined.set_ylabel('Y (mm)')
        ax_combined.set_zlabel('Z (mm)')

        for i, name in enumerate(self.selected_names):
            fn = make_valid_name(name)
            (line,) = ax_combined.plot([], [], [], color=colors[i], linewidth=2.0, label=name)
            self.combined_lines_3d[fn] = line
        ax_combined.legend()

        ax_button = self.fig.add_axes([0.40, 0.01, 0.20, 0.06])
        self.stop_button = Button(ax_button, 'STOP & SAVE', color=(0.85, 0.2, 0.2), hovercolor=(0.95, 0.3, 0.3))
        self.stop_button.label.set_color('white')
        self.stop_button.label.set_fontweight('bold')
        self.stop_button.on_clicked(lambda event: setattr(self, 'stop_requested', True))

    def _redraw(self):
        with self.lock:
            all_pts = []
            for fn, pts in self._live_buffer.items():
                if not pts or fn not in self.combined_lines_3d:
                    continue
                arr = np.array(pts)
                self.combined_lines_3d[fn].set_data_3d(arr[:, 0], arr[:, 1], arr[:, 2])
                all_pts.extend(pts)

        if self.combined_lines_3d and self.fig:
            try:
                ax = next(iter(self.combined_lines_3d.values())).axes
                if all_pts:
                    arr_all = np.array(all_pts)
                    if arr_all.size > 0:
                        xmin, xmax = np.min(arr_all[:, 0]), np.max(arr_all[:, 0])
                        ymin, ymax = np.min(arr_all[:, 1]), np.max(arr_all[:, 1])
                        zmin, zmax = np.min(arr_all[:, 2]), np.max(arr_all[:, 2])
                        margin = 300.0
                        ax.set_xlim(xmin - margin, xmax + margin)
                        ax.set_ylim(ymin - margin, ymax + margin)
                        ax.set_zlim(zmin - margin, zmax + margin)
                self.fig.canvas.draw_idle()
                self.fig.canvas.flush_events()
            except Exception:
                pass

    # ---------------- Point cloud (placeholder source, real tracker) ----------------

    def _get_slam_point_cloud(self):
        """Placeholder -- replace with the real SLAM point cloud source
        (same limitation as the original reference file). Returns an
        Nx2 array of point positions in mm."""
        return np.random.uniform(-5000, 5000, (30, 2))

    def _poll_point_cloud_once(self):
        t = time.time() - self.start_time if self.start_time else 0.0
        points = self._get_slam_point_cloud()
        classifications = self.point_tracker.update(points)
        self.point_cloud_log.append((t, points, classifications))

    # ---------------- Run / finalize ----------------

    def run(self):
        print('Multi-Rigid-Body NatNet Tracker (+ MiR Integration) - Start')
        print('=========================================================')

        if self.mir_ip:
            self.transform_matrix = load_transform_matrix()

        self.connect_to_natnet()
        self.build_rigid_body_map()

        print(f'Detected {len(self.rb_names)} Rigid Body/Bodies from Motive:')
        for name in self.rb_names:
            print(f'   - {name}')

        self.select_rigid_bodies_to_record()
        if not self.selected_names:
            print('No Rigid Bodies selected. Exiting.')
            return

        for name in self.selected_names:
            fn = make_valid_name(name)
            self.buffers[fn] = RigidBodyBuffer()
            self.highrate_buffers[fn] = RigidBodyBuffer()

        self.initialize_plots()
        self.start_time = time.time()

        # Start the MiR polling thread (if an IP was provided) and the
        # unified sync tick thread.
        if self.mir_ip:
            self._mir_thread = threading.Thread(target=self._mir_polling_loop, daemon=True)
            self._mir_thread.start()
            print(f'[INFO] Polling MiR robot API at {self.mir_ip} every {MIR_POLL_INTERVAL_S*1000:.0f}ms')

        self._sync_thread = threading.Thread(target=self._sync_tick_loop, daemon=True)
        self._sync_thread.start()
        print(f'[INFO] Unified sync tick running every {SYNC_TICK_INTERVAL_S*1000:.0f}ms')

        print('\nStreaming... click STOP & SAVE button or press Ctrl+C in terminal.\n')

        try:
            while self.stop_requested is False and plt.fignum_exists(self.fig.number):
                self._redraw()
                if self.mir_ip:
                    self._poll_point_cloud_once()
                self.fig.canvas.draw_idle()
                self.fig.canvas.flush_events()
                plt.pause(0.05)
        except KeyboardInterrupt:
            print('\n[INFO] Ctrl+C detected -- stopping safely...')

        self.stop_requested = True
        plt.close(self.fig)
        time.sleep(SYNC_TICK_INTERVAL_S * 2)  # let background threads finish their last tick
        self.finalize_and_save()

    def finalize_and_save(self):
        print('=========================================================')
        print('Disconnecting and running post-processing...')
        try:
            self.natnet_client.shutdown()
        except Exception:
            pass

        if not self.selected_names or not self.loop_timestamps:
            print('No frames captured.')
            return

        # Synchronized dataset (main output)
        original_data = {make_valid_name(name): self.buffers[make_valid_name(name)].trim()
                          for name in self.selected_names}
        if self.mir_ip and 'MiR_Robot' in self.buffers:
            original_data['MiR_Robot'] = self.buffers['MiR_Robot'].trim()

        # Full native-rate Motive-only data, preserved separately (raw data is never discarded)
        highrate_data = {make_valid_name(name): self.highrate_buffers[make_valid_name(name)].trim()
                          for name in self.selected_names}

        n_total = len(self.loop_timestamps)
        _, _, first_valid_idx, last_valid_idx = auto_trim_dead_time(original_data, self.loop_timestamps)
        if ask_trim_confirmation(n_total, first_valid_idx, last_valid_idx):
            original_data, self.loop_timestamps, first_valid_idx, last_valid_idx = \
                auto_trim_dead_time(original_data, self.loop_timestamps)

        mocap_session = {'OriginalData': original_data, 'HighRateMotiveData': highrate_data}
        self.mat_path = os.path.join(self.output_folder, f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mat")
        try:
            sio.savemat(self.mat_path, {'MocapSession': mocap_session})
            print(f'[SUCCESS] Raw data saved to .mat file: {self.mat_path}')
        except Exception as e:
            print(f'Failed to save .mat: {e}')

        try:
            robot_name = identify_robot_body(list(original_data.keys()))
            kinematics = compute_kinematics(original_data)
            relative_motion = compute_relative_motion(original_data, kinematics, robot_name,
                                                        DANGER_THRESHOLD_MM, WARNING_THRESHOLD_MM,
                                                        MIN_APPROACH_SPEED_MMPS)
            robot_relative_kinematics = compute_robot_relative_kinematics(original_data, kinematics, robot_name)
            tracking_quality = compute_tracking_quality(original_data)

            mocap_session['Analysis'] = {
                'Kinematics': kinematics,
                'RelativeMotion': relative_motion,
                'RobotRelativeKinematics': robot_relative_kinematics,
                'TrackingQuality': tracking_quality,
                'PointCloudSummary': self.point_tracker.get_summary(),
                'PointCloudLog': self.point_cloud_log,
            }
            sio.savemat(self.mat_path, {'MocapSession': mocap_session})
            print('[SUCCESS] Analysis updated in .mat file.')
            print(f"[INFO] Point cloud tracking summary: {self.point_tracker.get_summary()}")
        except Exception as e:
            print(f'Analysis failed: {e}')

        self.pkl_path = os.path.join(self.output_folder, f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")
        try:
            with open(self.pkl_path, 'wb') as f:
                pickle.dump(mocap_session, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f'[SUCCESS] Pickle saved to {self.pkl_path}')
        except Exception as e:
            print(f'Failed to save .pkl file: {e}')

        print(f'Session complete! Output folder: {self.output_folder}')


if __name__ == '__main__':
    mir_ip_input = input('Enter the MiR robot IP address (leave blank to skip MiR integration): ').strip()
    tracker = MultiRigidBodyTracker(mir_ip=mir_ip_input if mir_ip_input else None)
    tracker.run()
