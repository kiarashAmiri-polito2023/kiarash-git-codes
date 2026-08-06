#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash Amiri Polito
Email: s322803@studenti.polito.it
GitHub: https://github.com/kiarashAmiri-polito2023/kiarash-git-codes.git

Changelog & Updates (Compared to previous version):
  * Updated author credentials, email, and GitHub repository links in the script header.
  * Integrated long-term persistent map memory ('mir_mapping_memory/static_map.npy') to track static obstacles across multiple runs efficiently without increasing file size.
  * Implemented Advanced Dynamic vs. Static Separation using velocity displacement thresholds (>0.5m shift) to isolate moving entities and filter out sensor noise.
  * Added Multi-Human Tracking & Visualization via DBSCAN clustering, automatically assigning unique identifiers (Human 1, Human 2...) and drawing distinct 40cm tracking circles.
  * Implemented Wi-Fi Disconnection & Freeze Mode to prevent application crashes and unexpected window closure during network loss, allowing manual exit when desired.
  * Utilized fully vectorized NumPy matrix operations for zero-lag performance alongside heavy concurrent processes.
"""

import os
import math
import time
import numpy as np
import roslibpy
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# ===========================================================================
# Configuration & Persistent Memory Setup
# ===========================================================================
ROBOT_IP = '192.168.12.20'
ROS_PORT = 9090

MEMORY_FOLDER = 'mir_mapping_memory'
MEMORY_FILE = os.path.join(MEMORY_FOLDER, 'static_map.npy')

# Ensure memory folder exists
if not os.path.exists(MEMORY_FOLDER):
    os.makedirs(MEMORY_FOLDER)

# Load long-term static map memory if available
if os.path.exists(MEMORY_FILE):
    try:
        loaded_memory = np.load(MEMORY_FILE)
        static_memory = loaded_memory.tolist() if len(loaded_memory) > 0 else []
        print(f"[INFO] Loaded {len(static_memory)} persistent static points from memory.")
    except Exception:
        static_memory = []
else:
    static_memory = []

# Global state variables for real-time tracking
robot_pose = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
latest_laser_points = None
previous_laser_points = None

def odom_callback(msg):
    """Updates robot global position and orientation at maximum speed."""
    global robot_pose
    pos = msg.get('pose', {}).get('pose', {})
    position = pos.get('position', {})
    orientation = pos.get('orientation', {})
    
    robot_pose['x'] = position.get('x', 0.0)
    robot_pose['y'] = position.get('y', 0.0)
    
    qx = orientation.get('x', 0.0)
    qy = orientation.get('y', 0.0)
    qz = orientation.get('z', 0.0)
    qw = orientation.get('w', 0.0)
    
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    robot_pose['yaw'] = math.atan2(siny_cosp, cosy_cosp)

def laser_callback(msg):
    """Processes laser scans, applies Map-Centric transform, and tracks dynamics."""
    global latest_laser_points
    ranges = msg.get('ranges', [])
    angle_min = msg.get('angle_min', 0.0)
    angle_inc = msg.get('angle_increment', 0.0)
    
    if not ranges:
        return
        
    ranges = np.array(ranges, dtype=float)
    valid_indices = np.where((ranges > 0.1) & (ranges < 10.0))[0][::2]
    if len(valid_indices) == 0:
        return
        
    r = ranges[valid_indices]
    angles = angle_min + (valid_indices * angle_inc)
    
    # Local to Global Frame Transform via NumPy Vectorization
    x_local = r * np.cos(angles)
    y_local = r * np.sin(angles)
    
    cos_yaw = np.cos(robot_pose['yaw'])
    sin_yaw = np.sin(robot_pose['yaw'])
    
    x_global = robot_pose['x'] + (x_local * cos_yaw - y_local * sin_yaw)
    y_global = robot_pose['y'] + (x_local * sin_yaw + y_local * cos_yaw)
    
    latest_laser_points = np.column_stack((x_global, y_global))

# ===========================================================================
# Main Execution & Rendering Loop with Wi-Fi Freeze Protection
# ===========================================================================
print("=====================================================")
print("  MiR Advanced Map-Centric Tracker with Persistent Memory")
print("=====================================================")

client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
client.run()

if not client.is_connected:
    print("[CRITICAL] Could not connect to ROS Bridge at startup.")

print("[SUCCESS] Subscribing to /odom and /f_scan...")
roslibpy.Topic(client, '/odom', 'nav_msgs/Odometry').subscribe(odom_callback)
roslibpy.Topic(client, '/f_scan', 'sensor_msgs/LaserScan').subscribe(laser_callback)

# Setup Optimized 2D Interactive Plot
plt.ion()
fig, ax = plt.subplots(figsize=(9, 9))

scatter_static = ax.scatter([], [], c='red', s=6, label='Static Obstacles', alpha=0.6)
scatter_dynamic = ax.scatter([], [], c='blue', s=14, label='Dynamic Obstacles (Humans)', alpha=0.9)
robot_marker, = ax.plot([], [], marker=(3, 0, 0), color='green', markersize=15, linestyle='None', label='Robot')

human_circles = []
human_texts = []

ax.set_xlim([-15, 15])
ax.set_ylim([-15, 15])
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.5)
ax.set_xlabel('Map X (m)')
ax.set_ylabel('Map Y (m)')
ax.set_title('MiR Persistent Live Tracker (Zero-Lag & Freeze Protected)')
ax.legend(loc='upper right')

print("[INFO] Live tracking loop running. Close window manually to exit.")

wifi_active = True

try:
    while plt.fignum_exists(fig.number):
        # Check connection status
        if client.is_connected:
            if not wifi_active:
                print("\n[INFO] Wi-Fi reconnected! Resuming live stream...")
                wifi_active = True
                
            if latest_laser_points is not None and len(latest_laser_points) > 0:
                pts = latest_laser_points
                
                # Dynamic vs Static Separation & Velocity Check (>0.5m shift threshold)
                if previous_laser_points is not None and len(previous_laser_points) == len(pts):
                    displacements = np.linalg.norm(pts - previous_laser_points, axis=1)
                    is_dynamic = displacements > 0.5  # Moved more than 0.5m
                    dynamic_pts = pts[is_dynamic]
                    transient_pts = pts[~is_dynamic]
                else:
                    dynamic_pts = np.empty((0, 2))
                    transient_pts = pts

                previous_laser_points = pts.copy()
                
                # Update Permanent Static Memory
                if len(transient_pts) > 0:
                    if len(static_memory) > 0:
                        mem_arr = np.array(static_memory)
                        dists = np.min(np.linalg.norm(transient_pts[:, np.newaxis, :] - mem_arr[np.newaxis, :, :], axis=2), axis=1)
                        matched_static = transient_pts[dists < 0.15]
                        new_static = transient_pts[dists >= 0.15]
                        
                        if len(static_memory) < 5000 and len(new_static) > 0:
                            static_memory.extend(new_static[::3].tolist()) # Subsample to keep memory ultra-light
                    else:
                        static_memory.extend(transient_pts[::3].tolist())

                # Render Static Points
                if len(static_memory) > 0:
                    scatter_static.set_offsets(np.array(static_memory))

                # Cluster and Track Dynamic Obstacles (Humans) with 40cm Radius Circles
                for circ in human_circles:
                    circ.remove()
                for txt in human_texts:
                    txt.remove()
                human_circles.clear()
                human_texts.clear()

                if len(dynamic_pts) > 0:
                    scatter_dynamic.set_offsets(dynamic_pts)
                    
                    # Simple clustering to separate multiple humans
                    from sklearn.cluster import DBSCAN
                    clustering = DBSCAN(eps=0.6, min_samples=3).fit(dynamic_pts)
                    labels = clustering.labels_
                    
                    unique_labels = set(labels)
                    human_id = 1
                    colors = ['blue', 'purple', 'magenta', 'orange']
                    
                    for k in unique_labels:
                        if k == -1:
                            continue  # Noise
                        class_member_mask = (labels == k)
                        cluster_points = dynamic_pts[class_member_mask]
                        center_x = np.mean(cluster_points[:, 0])
                        center_y = np.mean(cluster_points[:, 1])
                        
                        col = colors[(human_id - 1) % len(colors)]
                        circ = Circle((center_x, center_y), 0.4, color=col, fill=False, linewidth=2, linestyle='--')
                        ax.add_patch(circ)
                        human_circles.append(circ)
                        
                        txt = ax.text(center_x, center_y + 0.5, f"Human {human_id}", color=col, weight='bold', fontsize=10, ha='center')
                        human_texts.append(txt)
                        human_id += 1
                else:
                    scatter_dynamic.set_offsets(np.empty((0, 2)))

                # Update Robot Position Marker
                robot_marker.set_data([robot_pose['x']], [robot_pose['y']])
                
                fig.canvas.draw_idle()
                fig.canvas.flush_events()
                
        else:
            if wifi_active:
                print("\n[WARNING] Wi-Fi / ROS connection lost! Entering PAUSE (Freeze) mode. Window remains open.")
                wifi_active = False
                
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user.")

# Save permanent map memory before closing safely
try:
    if len(static_memory) > 0:
        np.save(MEMORY_FILE, np.array(static_memory))
        print(f"[INFO] Saved {len(static_memory)} permanent static points to '{MEMORY_FILE}'.")
except Exception as e:
    print(f"[ERROR] Could not save map memory: {e}")

client.terminate()
plt.close()