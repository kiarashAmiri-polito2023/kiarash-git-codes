#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mir_command_logger.py - Robot Command History Logger (v1.0)
Captures /cmd_vel, /odom, /joystick, /battery, REST API state.
Provides ACTION GROUND TRUTH for VLA training.
"""
import os, sys, time, threading, pickle, math, json, base64
from datetime import datetime, timezone

try:
    import roslibpy
    HAS_ROSLIBPY = True
except ImportError:
    HAS_ROSLIBPY = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def utc_now_epoch():
    return datetime.now(tz=timezone.utc).timestamp()

def safe_pickle_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


class MirCommandLogger:
    def __init__(self, session_path, robot_ip="192.168.12.20", ros_port=9090,
                 rest_port=8080, rest_auth=None, poll_rest_every_s=2.0):
        self.session_path = session_path
        self.robot_ip = robot_ip
        self.ros_port = ros_port
        self.rest_port = rest_port
        self.rest_auth = rest_auth
        self.poll_rest_every_s = poll_rest_every_s
        
        self.client = None
        self.rest_thread = None
        self.rest_running = False
        
        self.lock = threading.Lock()
        self.cmd_vel_log = []
        self.odom_log = []
        self.joystick_log = []
        self.battery_log = []
        self.rest_state_log = []
        self.safety_events = []
        
        self.start_time_utc = None
        self.stats = {
            "cmd_vel_count": 0, "odom_count": 0, "joystick_count": 0,
            "safety_stops_detected": 0, "manual_overrides_detected": 0,
            "rest_polls_success": 0, "rest_polls_failed": 0
        }
    
    def _cmd_vel_callback(self, msg):
        try:
            t = utc_now_epoch()
            lin = msg.get("linear", {})
            ang = msg.get("angular", {})
            entry = {
                "timestamp_utc": t,
                "linear_x_mps": float(lin.get("x", 0)),
                "linear_y_mps": float(lin.get("y", 0)),
                "angular_z_rps": float(ang.get("z", 0)),
                "speed_mps": math.hypot(float(lin.get("x", 0)), float(lin.get("y", 0)))
            }
            with self.lock:
                self.cmd_vel_log.append(entry)
                self.stats["cmd_vel_count"] += 1
                if len(self.cmd_vel_log) >= 2:
                    prev = self.cmd_vel_log[-2]
                    if prev["speed_mps"] > 0.1 and entry["speed_mps"] < 0.01:
                        self.safety_events.append({
                            "timestamp_utc": t, "type": "sudden_stop",
                            "prev_speed": prev["speed_mps"], "curr_speed": entry["speed_mps"]
                        })
                        self.stats["safety_stops_detected"] += 1
        except Exception:
            pass
    
    def _odom_callback(self, msg):
        try:
            t = utc_now_epoch()
            twist = msg.get("twist", {}).get("twist", {})
            lin = twist.get("linear", {})
            ang = twist.get("angular", {})
            pose = msg.get("pose", {}).get("pose", {})
            pos = pose.get("position", {})
            entry = {
                "timestamp_utc": t,
                "actual_linear_x_mps": float(lin.get("x", 0)),
                "actual_angular_z_rps": float(ang.get("z", 0)),
                "actual_speed_mps": math.hypot(float(lin.get("x", 0)), float(lin.get("y", 0))),
                "odom_x_m": float(pos.get("x", 0)),
                "odom_y_m": float(pos.get("y", 0))
            }
            with self.lock:
                self.odom_log.append(entry)
                self.stats["odom_count"] += 1
        except Exception:
            pass
    
    def _joystick_callback(self, msg):
        try:
            t = utc_now_epoch()
            with self.lock:
                self.joystick_log.append({"timestamp_utc": t, "raw": str(msg)[:200]})
                self.stats["joystick_count"] += 1
                self.stats["manual_overrides_detected"] += 1
                self.safety_events.append({"timestamp_utc": t, "type": "manual_override"})
        except Exception:
            pass
    
    def _battery_callback(self, msg):
        try:
            with self.lock:
                self.battery_log.append({
                    "timestamp_utc": utc_now_epoch(),
                    "percentage": float(msg.get("percentage", 0)),
                    "voltage": float(msg.get("voltage", 0))
                })
        except Exception:
            pass
    
    def _rest_poll_loop(self):
        if not HAS_REQUESTS:
            return
        base_url = f"http://{self.robot_ip}:{self.rest_port}/api/v2.0.0"
        headers = {}
        if self.rest_auth:
            if isinstance(self.rest_auth, dict):
                headers = self.rest_auth
            else:
                creds = f"{self.rest_auth[0]}:{self.rest_auth[1]}"
                headers["Authorization"] = "Basic " + base64.b64encode(creds.encode()).decode()
                headers["Accept-Language"] = "en_US"
        while self.rest_running:
            try:
                r = requests.get(f"{base_url}/status", headers=headers, timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    entry = {
                        "timestamp_utc": utc_now_epoch(),
                        "state_text": data.get("state_text"),
                        "mode_text": data.get("mode_text"),
                        "battery_percentage": data.get("battery_percentage"),
                        "mission_text": data.get("mission_text"),
                        "position_x": data.get("position", {}).get("x"),
                        "position_y": data.get("position", {}).get("y"),
                        "position_orientation": data.get("position", {}).get("orientation")
                    }
                    with self.lock:
                        self.rest_state_log.append(entry)
                        self.stats["rest_polls_success"] += 1
                else:
                    with self.lock:
                        self.stats["rest_polls_failed"] += 1
            except Exception:
                with self.lock:
                    self.stats["rest_polls_failed"] += 1
            time.sleep(self.poll_rest_every_s)
    
    def try_connect(self):
        if not HAS_ROSLIBPY:
            print("[MirCmdLogger] roslibpy not installed")
            return False
        try:
            print(f"[MirCmdLogger] Connecting to {self.robot_ip}:{self.ros_port}...")
            self.client = roslibpy.Ros(host=self.robot_ip, port=self.ros_port)
            self.client.run(timeout=10)
            if not self.client.is_connected:
                return False
            print("[MirCmdLogger] Connected. Subscribing...")
            for topic, msgtype, cb, name in [
                ("/cmd_vel", "geometry_msgs/Twist", self._cmd_vel_callback, "cmd_vel"),
                ("/odom", "nav_msgs/Odometry", self._odom_callback, "odom"),
                ("/joystick_vel", "geometry_msgs/TwistStamped", self._joystick_callback, "joystick"),
                ("/battery_state", "sensor_msgs/BatteryState", self._battery_callback, "battery")
            ]:
                try:
                    t = roslibpy.Topic(self.client, topic, msgtype)
                    t.subscribe(cb)
                    print(f"  [OK] {topic}")
                except Exception as e:
                    print(f"  [WARN] {topic} failed: {e}")
            self.start_time_utc = utc_now_iso()
            self.rest_running = True
            self.rest_thread = threading.Thread(target=self._rest_poll_loop, daemon=True)
            self.rest_thread.start()
            print("  [OK] REST poller started")
            return True
        except Exception as e:
            print(f"[MirCmdLogger] Error: {e}")
            return False
    
    def stop(self):
        self.rest_running = False
        if self.rest_thread:
            self.rest_thread.join(timeout=3)
        if self.client and self.client.is_connected:
            try:
                self.client.terminate()
            except Exception:
                pass
        print("[MirCmdLogger] Stopped.")
    
    def save_final(self):
        with self.lock:
            data = {
                "schema_version": "mir_command_log_v1",
                "start_time_utc": self.start_time_utc,
                "end_time_utc": utc_now_iso(),
                "robot_ip": self.robot_ip,
                "cmd_vel_log": list(self.cmd_vel_log),
                "odom_log": list(self.odom_log),
                "joystick_log": list(self.joystick_log),
                "battery_log": list(self.battery_log),
                "rest_state_log": list(self.rest_state_log),
                "safety_events": list(self.safety_events),
                "stats": dict(self.stats)
            }
        pkl = os.path.join(self.session_path, "mir_command_data.pkl")
        safe_pickle_dump(data, pkl)
        txt = os.path.join(self.session_path, "mir_command_data_summary.txt")
        with open(txt, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n MIR ROBOT COMMAND LOG\n" + "=" * 60 + "\n")
            f.write(f"Start: {data['start_time_utc']}\nEnd  : {data['end_time_utc']}\n\nSTATS:\n")
            for k, v in data["stats"].items():
                f.write(f"  {k}: {v}\n")
        print(f"[MirCmdLogger] Saved: {pkl}")
        return pkl


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("session_path")
    p.add_argument("--ip", default="192.168.12.20")
    p.add_argument("--duration", type=int, default=30)
    args = p.parse_args()
    logger = MirCommandLogger(args.session_path, robot_ip=args.ip)
    if not logger.try_connect():
        sys.exit(1)
    print(f"Logging for {args.duration}s...")
    time.sleep(args.duration)
    logger.stop()
    logger.save_final()
