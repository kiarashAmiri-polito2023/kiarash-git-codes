#!/usr/bin/env python3
import os
import sys
import time
import pickle
import threading
import code
from datetime import datetime

import numpy as np
import scipy.io as sio
import importlib.util

import matplotlib
if importlib.util.find_spec('tkinter') is not None:
    matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

try:
    from NatNetClient import NatNetClient
except ImportError:
    print("ERROR: NatNetClient.py was not found next to this script.")
    sys.exit(1)

DANGER_THRESHOLD_MM = 100.0
WARNING_THRESHOLD_MM = 500.0
MIN_APPROACH_SPEED_MMPS = 20.0

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
    valid = "".join(ch if (ch.isalnum() or ch == '_') else '_' for ch in name)
    if valid and valid[0].isdigit():
        valid = "_" + valid
    return valid or "_unnamed"

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

def identify_robot_body(names):
    matches = [n for n in names if 'robot' in n.lower()]
    if len(matches) >= 1:
        return matches[0]
    return None

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
    return False

class MultiRigidBodyTracker:
    def __init__(self):
        self.output_folder = f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_folder, exist_ok=True)
        self.id_to_name = {}
        self.rb_names = []
        self.selected_names = []
        self.buffers = {}
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
        
        self.loaded_session = None
        self.pkl_path = None
        self.mat_path = None

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
        while (not hasattr(self.natnet_client, 'command_socket') or self.natnet_client.command_socket is None) and timeout_sock < 30:
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

        if not self.rb_names:
            self.rb_names = ["kia hat 002", "kiarash_leftwrist", "kiarash_RightWrist"]
            for idx, name in enumerate(self.rb_names, start=1):
                self.id_to_name[idx] = name

    def select_rigid_bodies_to_record(self):
        print('\n--- Select which Rigid Bodies to record ---')
        selected = []
        for name in self.rb_names:
            answer = input(f'Record "{name}"? (yes/no): ').strip().lower()
            if answer.startswith('y'):
                selected.append(name)
        self.selected_names = selected

    def _on_new_frame(self, frame_number=None, *args, **kwargs):
        t = time.time() - self.start_time if self.start_time else 0.0
        with self.lock:
            if self._pending_t is not None:
                for name in self.selected_names:
                    fn = make_valid_name(name)
                    if name not in self._pending_seen:
                        self.buffers[fn].append_nan_row(self._pending_t)
                self.loop_timestamps.append(self._pending_t)
            self._pending_seen = set()
            self._pending_t = t

    def _on_rigid_body(self, new_id, position, rotation):
        if new_id not in self.id_to_name:
            return
        name = self.id_to_name[new_id]
        if name not in self.selected_names:
            return

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
            self._pending_seen.add(name)
            self.buffers[fn].append_row(self._pending_t, position_mm, quat, [roll, pitch, yaw])
            if position is not None and not np.isnan(position_mm[0]):
                self._live_buffer.setdefault(fn, []).append(position_mm)

    def initialize_plots(self):
        self._live_buffer = {make_valid_name(n): [] for n in self.selected_names}
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

    def run(self):
        print('Multi-Rigid-Body NatNet Tracker - Start')
        print('=========================================================')

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
            self.buffers[make_valid_name(name)] = RigidBodyBuffer()

        self.initialize_plots()
        self.start_time = time.time()

        print('\nStreaming... click STOP & SAVE button or press Ctrl+C in terminal.\n')

        try:
            while self.stop_requested is False and plt.fignum_exists(self.fig.number):
                self._redraw()
                self.fig.canvas.draw_idle()
                self.fig.canvas.flush_events()
                plt.pause(0.05)
        except KeyboardInterrupt:
            print('\n[INFO] Ctrl+C detected -- stopping safely...')

        plt.close(self.fig)
        self.finalize_and_save()

    def finalize_and_save(self):
        print('=========================================================')
        print('Disconnecting and running post-processing...')
        try:
            self.natnet_client.shutdown()
        except Exception:
            pass

        with self.lock:
            if self._pending_t is not None:
                for name in self.selected_names:
                    fn = make_valid_name(name)
                    if name not in self._pending_seen:
                        self.buffers[fn].append_nan_row(self._pending_t)
                self.loop_timestamps.append(self._pending_t)

        if not self.selected_names or not self.loop_timestamps:
            print('No frames captured.')
            return

        original_data = {make_valid_name(name): self.buffers[make_valid_name(name)].trim() for name in self.selected_names}

        n_total = len(self.loop_timestamps)
        _, _, first_valid_idx, last_valid_idx = auto_trim_dead_time(original_data, self.loop_timestamps)
        if ask_trim_confirmation(n_total, first_valid_idx, last_valid_idx):
            original_data, self.loop_timestamps, first_valid_idx, last_valid_idx = auto_trim_dead_time(original_data, self.loop_timestamps)

        mocap_session = {'OriginalData': original_data}
        self.mat_path = os.path.join(self.output_folder, f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mat")
        try:
            sio.savemat(self.mat_path, {'MocapSession': mocap_session})
            print(f'[SUCCESS] Raw data saved to .mat file: {self.mat_path}')
        except Exception as e:
            print(f'Failed to save .mat: {e}')

        try:
            robot_name = identify_robot_body(list(original_data.keys()))
            kinematics = compute_kinematics(original_data)
            relative_motion = compute_relative_motion(original_data, kinematics, robot_name, DANGER_THRESHOLD_MM, WARNING_THRESHOLD_MM, MIN_APPROACH_SPEED_MMPS)
            tracking_quality = compute_tracking_quality(original_data)

            mocap_session['Analysis'] = {
                'Kinematics': kinematics,
                'RelativeMotion': relative_motion,
                'TrackingQuality': tracking_quality,
            }
            sio.savemat(self.mat_path, {'MocapSession': mocap_session})
            print('[SUCCESS] Analysis updated in .mat file.')
        except Exception as e:
            print(f'Analysis failed: {e}')

        self.pkl_path = os.path.join(self.output_folder, f"MocapSession_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")
        try:
            with open(self.pkl_path, 'wb') as f:
                pickle.dump(mocap_session, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f'[SUCCESS] Pickle saved to {self.pkl_path}')
            
            # بارگذاری خودکار فایل در متغیر session
            with open(self.pkl_path, 'rb') as f:
                session = pickle.load(f)
            
            self.loaded_session = session
            print(f'[SUCCESS] Data successfully imported into Python variable `session`!')
            print(f'Keys available: {list(session.keys())}')
            print('---------------------------------------------------------')
            print('Entering interactive mode. You can inspect `session` now.')
            print('Type exit() when you are done.')
            print('---------------------------------------------------------')
            
            # باز نگه داشتن ترمینال و ورود به مفسر پایتون برای مشاهده داده‌ها
            code.interact(local=locals())
            
        except Exception as e:
            print(f'Failed to save/load .pkl file: {e}')

        print(f'Session complete! Output folder: {self.output_folder}')

if __name__ == '__main__':
    tracker = MultiRigidBodyTracker()
    tracker.run()
    ojpoj
    pjppo
    lp;po
    