#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: motive_connector.py  (v2 — rewritten against the ACTUAL NatNetClient SDK)

The ONLY module in the project that touches NatNetClient directly.
Every other script must import and use MotiveConnector.

Confirmed project convention (calibration v4, PASS):
  - Motive Up Axis = Z
  - Ground plane   = Motive (X, Y)
  - Vertical       = Motive Z
  - All positions returned in MILLIMETERS.

Changelog vs v1:
  - Uses client.run() which returns True/False (not Thread(target=run)).
  - Captures per-frame metadata (frame_number, timestamp, is_recording)
    via new_frame_listener for future video sync.
  - Captures camera descriptions (name, position, orientation) from the
    SDK's __unpack_camera_description, for the future video annotation
    module (OptiTrack cameras in Object Mode -> AVI).
  - Adds start_recording() / stop_recording() using NAT_REQUEST with
    text commands, confirmed compatible with this SDK's send_request().
  - Thread safety via self._lock on all shared state.
"""

import sys
import time
import math
import threading

import numpy as np

try:
    from NatNetClient import NatNetClient
except ImportError:
    print("[ERROR] NatNetClient.py not found next to this module.")
    sys.exit(1)


GROUND_AXES = ("x", "y")
VERTICAL_AXIS = "z"
DEFAULT_STALE_TIMEOUT_SEC = 1.0


def quaternion_to_euler_deg(qx, qy, qz, qw):
    """Quaternion -> (roll, pitch, yaw) in degrees."""
    sinr_cosp = 2 * (qw * qx + qy * qz)
    cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2 * (qw * qy - qz * qx)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)

    siny_cosp = 2 * (qw * qz + qx * qy)
    cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


class MotiveConnector:
    """
    Thread-safe shared connector to Motive via NatNet.

    Usage:
        motive = MotiveConnector()
        if not motive.connect():
            print("Connection failed")
            sys.exit(1)
        motive.request_model_definitions()

        # ... use get_full_state(), is_fresh(), etc. ...

        motive.shutdown()
    """

    def __init__(self, stale_timeout_sec=DEFAULT_STALE_TIMEOUT_SEC):
        self._lock = threading.Lock()

        self._client = None
        self.id_to_name = {}
        self.rb_names = []

        # name -> full state dict
        self._states = {}

        # Per-frame metadata from new_frame_listener
        self._latest_frame = {
            "frame_number": None,
            "timestamp": None,
            "is_recording": False,
            "received_at": None,
        }

        # Camera descriptions from model definitions
        self.camera_descriptions = []

        self.model_def_received = False
        self.stale_timeout_sec = stale_timeout_sec

    # -----------------------------------------------------------------
    # NatNet Callbacks (called from NatNet's background threads)
    # -----------------------------------------------------------------
    def _on_rigid_body(self, new_id, position, rotation):
        with self._lock:
            name = self.id_to_name.get(new_id)
        if name is None:
            return

        now = time.time()

        if position is None or np.isnan(position[0]):
            with self._lock:
                self._states[name] = {
                    "x_mm": None, "y_mm": None, "z_mm": None,
                    "qx": None, "qy": None, "qz": None, "qw": None,
                    "roll_deg": None, "pitch_deg": None, "yaw_deg": None,
                    "updated_at": now,
                    "tracked": False,
                }
            return

        x_mm = position[0] * 1000.0
        y_mm = position[1] * 1000.0
        z_mm = position[2] * 1000.0

        if rotation is None:
            qx = qy = qz = 0.0
            qw = 1.0
        else:
            qx, qy, qz, qw = rotation

        roll_deg, pitch_deg, yaw_deg = quaternion_to_euler_deg(qx, qy, qz, qw)

        with self._lock:
            self._states[name] = {
                "x_mm": x_mm, "y_mm": y_mm, "z_mm": z_mm,
                "qx": qx, "qy": qy, "qz": qz, "qw": qw,
                "roll_deg": roll_deg, "pitch_deg": pitch_deg, "yaw_deg": yaw_deg,
                "updated_at": now,
                "tracked": True,
            }

    def _on_model_definitions(self, data_descs):
        id_to_name = {}
        rb_names = []

        for rb in data_descs.rigid_body_list:
            raw_name = getattr(rb, 'sz_name', getattr(rb, 'rb_name', None))
            rb_id = getattr(rb, 'id_num', getattr(rb, 'rigid_body_id', None))
            if rb_id is None or raw_name is None:
                continue
            name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name
            id_to_name[rb_id] = name
            if name not in rb_names:
                rb_names.append(name)

        # Camera descriptions (for future video annotation module)
        cameras = []
        if hasattr(data_descs, 'camera_list'):
            for cam in data_descs.camera_list:
                cam_name = getattr(cam, 'name', None) or getattr(cam, 'sz_name', None)
                if isinstance(cam_name, bytes):
                    cam_name = cam_name.decode('utf-8', errors='ignore')
                cameras.append({
                    "name": cam_name,
                    "position": getattr(cam, 'position', None),
                    "orientation": getattr(cam, 'orientation', None),
                })

        with self._lock:
            self.id_to_name = id_to_name
            self.rb_names = rb_names
            self.camera_descriptions = cameras
            self.model_def_received = True

    def _on_new_frame(self, data_dict):
        with self._lock:
            self._latest_frame = {
                "frame_number": data_dict.get("frame_number"),
                "timestamp": data_dict.get("timestamp"),
                "is_recording": data_dict.get("is_recording", False),
                "received_at": time.time(),
            }

    # -----------------------------------------------------------------
    # Connection lifecycle
    # -----------------------------------------------------------------
    def connect(self, client_address='127.0.0.1', server_address='127.0.0.1',
                use_multicast=True):
        """
        Connects to NatNet. Returns True on success, False on failure.
        Uses the SDK's own run() method which creates its own threads.
        """
        client = NatNetClient()
        client.set_client_address(client_address)
        client.set_server_address(server_address)
        client.set_use_multicast(use_multicast)

        client.rigid_body_listener = self._on_rigid_body
        client.model_def_listener = self._on_model_definitions
        client.new_frame_listener = self._on_new_frame

        # client.run() creates command_thread + data_thread internally,
        # sends NAT_CONNECT, returns True/False.
        success = client.run()
        if not success:
            print("[MotiveConnector] ERROR: NatNetClient.run() returned False. "
                  "Check that Motive is streaming on the expected address/port.")
            return False

        time.sleep(1.0)  # allow handshake + server info to arrive
        self._client = client
        print("[MotiveConnector] Connected to NatNet.")
        return True

    def request_model_definitions(self, timeout_sec=6.0, poll_interval=0.2):
        """
        Sends NAT_REQUEST_MODELDEF to Motive and waits until the response
        arrives (populating rigid body names + camera descriptions).
        Returns True if definitions were received, False on timeout.
        """
        if self._client is None:
            raise RuntimeError("connect() must be called first.")

        # Wait for command_socket to be ready
        timeout_sock = 0
        while (self._client.command_socket is None) and timeout_sock < 30:
            time.sleep(0.1)
            timeout_sock += 1

        if self._client.command_socket is None:
            print("[MotiveConnector] WARNING: command_socket never became ready.")
            return False

        try:
            self._client.send_request(
                self._client.command_socket,
                self._client.NAT_REQUEST_MODELDEF,
                "",
                (self._client.server_ip_address, self._client.command_port)
            )
        except Exception as e:
            print(f"[MotiveConnector] WARNING: send_request failed: {e}")

        waited = 0.0
        while not self.model_def_received and waited < timeout_sec:
            time.sleep(poll_interval)
            waited += poll_interval

        if not self.model_def_received:
            print("[MotiveConnector] WARNING: model definitions not received "
                  f"within {timeout_sec}s. Is Motive streaming?")
        else:
            print(f"[MotiveConnector] Model definitions received. "
                  f"Rigid bodies: {self.rb_names}")
            if self.camera_descriptions:
                print(f"[MotiveConnector] Cameras detected: "
                      f"{[c['name'] for c in self.camera_descriptions]}")

        return self.model_def_received

    def shutdown(self):
        if self._client is not None:
            try:
                self._client.shutdown()
            except Exception:
                pass
        print("[MotiveConnector] Shutdown complete.")

    # -----------------------------------------------------------------
    # Recording control (remote trigger Motive via text commands)
    # -----------------------------------------------------------------
    def start_recording(self, take_name=None):
        """
        Remotely triggers Motive to START recording (all cameras in
        Reference/Object mode will begin capturing AVI/MJPEG).
        Returns True if the command was sent successfully, False otherwise.

        IMPORTANT: this only SENDS the command; you should verify in
        Motive's UI or via get_latest_frame()['is_recording'] that
        recording actually started.
        """
        if self._client is None or self._client.command_socket is None:
            print("[MotiveConnector] Cannot start recording: not connected.")
            return False
        try:
            addr = (self._client.server_ip_address, self._client.command_port)
            if take_name:
                self._client.send_request(
                    self._client.command_socket,
                    self._client.NAT_REQUEST,
                    f"SetRecordTakeName,{take_name}",
                    addr
                )
                time.sleep(0.1)
            self._client.send_request(
                self._client.command_socket,
                self._client.NAT_REQUEST,
                "StartRecording",
                addr
            )
            print(f"[MotiveConnector] Sent 'StartRecording'"
                  f"{f' (take: {take_name})' if take_name else ''}. "
                  f"Verify via is_motive_recording().")
            return True
        except Exception as e:
            print(f"[MotiveConnector] start_recording failed: {e}")
            return False

    def stop_recording(self):
        """Remotely triggers Motive to STOP recording."""
        if self._client is None or self._client.command_socket is None:
            print("[MotiveConnector] Cannot stop recording: not connected.")
            return False
        try:
            self._client.send_request(
                self._client.command_socket,
                self._client.NAT_REQUEST,
                "StopRecording",
                (self._client.server_ip_address, self._client.command_port)
            )
            print("[MotiveConnector] Sent 'StopRecording'.")
            return True
        except Exception as e:
            print(f"[MotiveConnector] stop_recording failed: {e}")
            return False

    def is_motive_recording(self):
        """Returns True if the latest frame from Motive indicates that
        Motive itself is currently recording a Take."""
        with self._lock:
            return self._latest_frame.get("is_recording", False)

    # -----------------------------------------------------------------
    # Public read API (thread-safe)
    # -----------------------------------------------------------------
    def list_rigid_bodies(self):
        with self._lock:
            return list(self.rb_names)

    def is_tracked(self, name):
        with self._lock:
            state = self._states.get(name)
        return bool(state and state.get("tracked"))

    def is_fresh(self, name, max_age_sec=None):
        if max_age_sec is None:
            max_age_sec = self.stale_timeout_sec
        with self._lock:
            state = self._states.get(name)
        if state is None:
            return False
        return (time.time() - state["updated_at"]) <= max_age_sec

    def get_age_sec(self, name):
        with self._lock:
            state = self._states.get(name)
        if state is None:
            return None
        return time.time() - state["updated_at"]

    def get_position_mm(self, name):
        """Returns (x_mm, y_mm, z_mm) or None."""
        with self._lock:
            state = self._states.get(name)
        if state is None or not state.get("tracked"):
            return None
        return state["x_mm"], state["y_mm"], state["z_mm"]

    def get_ground_position_mm(self, name):
        """Returns (x_mm, y_mm) -- ground plane only."""
        pos = self.get_position_mm(name)
        return (pos[0], pos[1]) if pos else None

    def get_height_mm(self, name):
        """Returns Z (vertical) in mm, or None."""
        pos = self.get_position_mm(name)
        return pos[2] if pos else None

    def get_quaternion(self, name):
        with self._lock:
            state = self._states.get(name)
        if state is None or not state.get("tracked"):
            return None
        return state["qx"], state["qy"], state["qz"], state["qw"]

    def get_euler_deg(self, name):
        """Returns (roll_deg, pitch_deg, yaw_deg) or None."""
        with self._lock:
            state = self._states.get(name)
        if state is None or not state.get("tracked"):
            return None
        return state["roll_deg"], state["pitch_deg"], state["yaw_deg"]

    def get_full_state(self, name):
        """Returns a full copy of the latest state dict, or None."""
        with self._lock:
            state = self._states.get(name)
        if state is None:
            return None
        result = dict(state)
        result["age_sec"] = time.time() - state["updated_at"]
        result["name"] = name
        return result

    def get_all_full_states(self):
        with self._lock:
            names = list(self._states.keys())
        return {name: self.get_full_state(name) for name in names}

    def get_latest_frame(self):
        """Returns the latest per-frame metadata dict from Motive."""
        with self._lock:
            return dict(self._latest_frame)

    def auto_detect_robot_name(self, keywords=("mir", "robot")):
        for name in self.list_rigid_bodies():
            if any(k in name.lower() for k in keywords):
                return name
        return None

    def get_camera_descriptions(self):
        """Returns list of camera description dicts from Motive's
        internal calibration. Empty if SDK didn't expose them."""
        with self._lock:
            return list(self.camera_descriptions)


# ===========================================================================
# Self-test
# ===========================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("  motive_connector.py v2 -- standalone self-test")
    print("=" * 60)

    conn = MotiveConnector()
    if not conn.connect():
        print("[FAIL] Could not connect to NatNet.")
        sys.exit(1)

    ok = conn.request_model_definitions()
    if not ok or not conn.list_rigid_bodies():
        print("[FAIL] No rigid bodies detected. Is Motive streaming?")
        conn.shutdown()
        sys.exit(1)

    print(f"\nRigid bodies: {conn.list_rigid_bodies()}")
    robot = conn.auto_detect_robot_name()
    print(f"Auto-detected robot: {robot}")

    cameras = conn.get_camera_descriptions()
    if cameras:
        print(f"\nCamera descriptions ({len(cameras)} cameras):")
        for c in cameras:
            print(f"  {c['name']} | pos={c['position']} | orient={c['orientation']}")
    else:
        print("\nNo camera descriptions available from this SDK version.")

    # Test recording commands
    print("\n--- Testing recording commands ---")
    conn.start_recording("test_take_from_python")
    time.sleep(2.0)
    frame = conn.get_latest_frame()
    print(f"  is_motive_recording = {frame.get('is_recording')}")
    conn.stop_recording()
    time.sleep(0.5)
    frame = conn.get_latest_frame()
    print(f"  is_motive_recording (after stop) = {frame.get('is_recording')}")

    print("\n--- Streaming live states for 5 seconds ---\n")
    try:
        t_end = time.time() + 5.0
        while time.time() < t_end:
            for name in conn.list_rigid_bodies():
                state = conn.get_full_state(name)
                if state and state["tracked"]:
                    print(f"  {name:25s} | x={state['x_mm']:8.1f} y={state['y_mm']:8.1f} "
                          f"z={state['z_mm']:8.1f} mm | yaw={state['yaw_deg']:6.1f} deg | "
                          f"fresh={conn.is_fresh(name)} | age={state['age_sec']:.3f}s")
                else:
                    print(f"  {name:25s} | NOT TRACKED")
            print("-" * 80)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    conn.shutdown()
    print("\n[DONE] Self-test complete.")