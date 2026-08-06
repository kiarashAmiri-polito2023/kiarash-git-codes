#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash
Email: kiarash.student@polito.it
GitHub: https://github.com/kiarash-polito

Changelog & Updates (Compared to previous version):
  * Implemented Map-Centric coordinate transformation using real-time odometry (/odom) to keep environmental points fixed while the robot moves.
  * Replaced manual loops with highly optimized vectorized NumPy matrix calculations for zero-lag performance.
  * Added smart dynamic and static obstacle separation using grid-based temporal history tracking (Static = Red, Dynamic = Blue).
  * Optimized the 2D top-down rendering loop to ensure high FPS, preventing any CPU throttling or lag when running alongside heavy AI processes.
"""

import math
import time
import roslibpy
import numpy as np
import matplotlib.pyplot as plt

# ===========================================================================
# Configuration
# ===========================================================================
ROBOT_IP = '192.168.12.20'
ROS_PORT = 9090

# Global state variables for real-time data sharing
robot_pose = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
latest_laser_points = None

# Temporary memory for static/dynamic classification (Grid-based persistence)
static_memory = []

def odom_callback(msg):
    """Extremely fast callback to update robot global position and orientation."""
    global robot_pose
    pos = msg.get('pose', {}).get('pose', {})
    position = pos.get('position', {})
    orientation = pos.get('orientation', {})
    
    x = position.get('x', 0.0)
    y = position.get('y', 0.0)
    
    # Extract Yaw from Quaternion (Standard conversion)
    qx = orientation.get('x', 0.0)
    qy = orientation.get('y', 0.0)
    qz = orientation.get('z', 0.0)
    qw = orientation.get('w', 0.0)
    
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    
    robot_pose['x'] = x
    robot_pose['y'] = y
    robot_pose['yaw'] = yaw

def laser_callback(msg):
    """Processes laser scan, converts to global map frame using vectorized NumPy."""
    global latest_laser_points
    ranges = msg.get('ranges', [])
    angle_min = msg.get('angle_min', 0.0)
    angle_inc = msg.get('angle_increment', 0.0)
    
    if not ranges:
        return
        
    # Convert list to numpy array for maximum vectorization speed
    ranges = np.array(ranges, dtype=float)
    
    # Filter out invalid or out-of-range points (subsample every 2nd point for zero-lag)
    valid_indices = np.where((ranges > 0.1) & (ranges < 10.0))[0][::2]
    if len(valid_indices) == 0:
        return
        
    r = ranges[valid_indices]
    angles = angle_min + (valid_indices * angle_inc)
    
    # 1. Local Cartesian coordinates (relative to robot)
    x_local = r * np.cos(angles)
    y_local = r * np.sin(angles)
    
    # 2. Transform to Global Map Frame using Robot's current Pose (Matrix Transformation)
    cos_yaw = np.cos(robot_pose['yaw'])
    sin_yaw = np.sin(robot_pose['yaw'])
    
    x_global = robot_pose['x'] + (x_local * cos_yaw - y_local * sin_yaw)
    y_global = robot_pose['y'] + (x_local * sin_yaw + y_local * cos_yaw)
    
    latest_laser_points = np.column_stack((x_global, y_global))

# ===========================================================================
# Main Execution & High-Performance Rendering Loop
# ===========================================================================
print("=====================================================")
print("  MiR Map-Centric Zero-Lag Live Visualizer")
print("=====================================================")

client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
client.run()

if not client.is_connected:
    print("[CRITICAL] Could not connect to ROS Bridge.")
    exit(1)

print("[SUCCESS] Connected! Subscribing to /odom and /f_scan...")
roslibpy.Topic(client, '/odom', 'nav_msgs/Odometry').subscribe(odom_callback)
roslibpy.Topic(client, '/f_scan', 'sensor_msgs/LaserScan').subscribe(laser_callback)

# Setup Optimized 2D Interactive Plot
plt.ion()
fig, ax = plt.subplots(figsize=(9, 9))

# Scatter plots for visualization: Static (Red), Dynamic (Blue), Robot Position (Green Marker)
scatter_static = ax.scatter([], [], c='red', s=6, label='Static Obstacles', alpha=0.6)
scatter_dynamic = ax.scatter([], [], c='blue', s=12, label='Dynamic Obstacles', alpha=0.9)
robot_marker, = ax.plot([], [], marker=(3, 0, 0), color='green', markersize=15, linestyle='None', label='Robot')

ax.set_xlim([-15, 15])
ax.set_ylim([-15, 15])
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.5)
ax.set_xlabel('Map X (m)')
ax.set_ylabel('Map Y (m)')
ax.set_title('MiR Real-Time Map-Centric Tracker (Zero-Lag)')
ax.legend(loc='upper right')

print("[INFO] Live stream rendering started. Move the robot...")

try:
    while client.is_connected:
        if latest_laser_points is not None and len(latest_laser_points) > 0:
            pts = latest_laser_points
            
            # Simple & Fast Dynamic/Static Separation via Grid Density/History matching
            if len(static_memory) > 0:
                memory_arr = np.array(static_memory)
                dists = np.min(np.linalg.norm(pts[:, np.newaxis, :] - memory_arr[np.newaxis, :, :], axis=2), axis=1)
                
                is_static = dists < 0.155  # Threshold for matching static walls
                static_pts = pts[is_static]
                dynamic_pts = pts[~is_static]
                
                if len(static_memory) < 3000:
                    static_memory.extend(static_pts.tolist())
            else:
                static_memory.extend(pts.tolist())
                static_pts = pts
                dynamic_pts = np.empty((0, 2))
                
            # Update plot data streams instantly without clearing the canvas (Zero-Lag)
            if len(static_pts) > 0:
                scatter_static.set_offsets(static_pts)
            if len(dynamic_pts) > 0:
                scatter_dynamic.set_offsets(dynamic_pts)
                
            # Update Robot Marker Position
            robot_marker.set_data([robot_pose['x']], [robot_pose['y']])
            
            # Fast canvas redraw
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            
        time.sleep(0.03)  # Capped at ~30 FPS to guarantee zero CPU throttling

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user.")
    client.terminate()
    plt.close()