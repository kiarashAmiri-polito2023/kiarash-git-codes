#!/usr/init/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash Amiri Polito
Email: s322803@studenti.polito.it
GitHub: https://github.com/kiarashAmiri-polito2023/kiarash-git-codes.git

Description:
  MiR Live SLAM Viewer with Lightweight Cumulative Persistent Memory.
  Saves all obstacles and robot path into a single updating PKL file inside the 'map' folder.
"""

import math
import time
import sys
import os
import pickle
import numpy as np
import roslibpy
import matplotlib.pyplot as plt

# ===========================================================================
# Configuration & Memory Setup
# ===========================================================================
ROBOT_IP = '192.168.12.20'
ROS_PORT = 9090

# تنظیمات ذخیره‌سازی در پوشه map
SAVE_DIR = "map"
SAVE_FILE = os.path.join(SAVE_DIR, "robot_map_data.pkl")

# ساخت پوشه در صورت عدم وجود
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# بارگذاری دیتای قبلی برای آپدیت تجمعی (Cumulative Update)
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, 'rb') as f:
            map_db = pickle.load(f)
        # اطمینان از اینکه ساختار داده‌ها کامل است
        if not isinstance(map_db, dict):
            map_db = {"obstacles": set(), "path": []}
        if "obstacles" not in map_db:
            map_db["obstacles"] = set()
        if "path" not in map_db:
            map_db["path"] = []
        print(f"[INFO] Loaded existing data: {len(map_db['obstacles'])} obstacles and {len(map_db['path'])} path points found.")
    except Exception as e:
        print(f"[WARNING] Could not load old pickle file, creating new database. Error: {e}")
        map_db = {"obstacles": set(), "path": []}
else:
    map_db = {"obstacles": set(), "path": []}

# متغیرهای سراسری ربات
robot_pose = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
latest_f_scan = np.empty((0, 2))
latest_b_scan = np.empty((0, 2))
pose_received = False

def amcl_pose_callback(msg):
    global robot_pose, pose_received
    position = msg.get('pose', {}).get('pose', {}).get('position', {})
    orientation = msg.get('pose', {}).get('pose', {}).get('orientation', {})
    
    robot_pose['x'] = position.get('x', 0.0)
    robot_pose['y'] = position.get('y', 0.0)
    
    qx = orientation.get('x', 0.0)
    qy = orientation.get('y', 0.0)
    qz = orientation.get('z', 0.0)
    qw = orientation.get('w', 1.0)
    
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    robot_pose['yaw'] = math.atan2(siny_cosp, cosy_cosp)
    pose_received = True
    
    # ذخیره مسیر ربات با فیلتر فاصله برای جلوگیری از حجیم شدن فایل
    current_pt = (round(robot_pose['x'], 2), round(robot_pose['y'], 2))
    if len(map_db['path']) == 0 or math.dist(current_pt, map_db['path'][-1]) > 0.5:
        map_db['path'].append(current_pt)

def process_live_laser(msg, offset_x, offset_y, offset_yaw):
    if not pose_received:
        return np.empty((0, 2))
        
    ranges = msg.get('ranges', [])
    angle_min = msg.get('angle_min', 0.0)
    angle_inc = msg.get('angle_increment', 0.0)
    
    if not ranges:
        return np.empty((0, 2))
        
    ranges = np.array(ranges, dtype=float)
    valid_indices = np.where((ranges > 0.05) & (ranges < 15.0))[0]
    
    if len(valid_indices) == 0:
        return np.empty((0, 2))
        
    r = ranges[valid_indices]
    angles = angle_min + (valid_indices * angle_inc)
    
    x_l = r * np.cos(angles)
    y_l = r * np.sin(angles)
    cos_s, sin_s = np.cos(offset_yaw), np.sin(offset_yaw)
    x_base = (x_l * cos_s - y_l * sin_s) + offset_x
    y_base = (x_l * sin_s + y_l * cos_s) + offset_y
    
    cos_r, sin_r = np.cos(robot_pose['yaw']), np.sin(robot_pose['yaw'])
    x_global = robot_pose['x'] + (x_base * cos_r - y_base * sin_r)
    y_global = robot_pose['y'] + (x_base * sin_r + y_base * cos_r)
    
    # ذخیره و رند کردن موانع در حافظه دائمی (به صورت Set برای حذف تکرارها)
    for gx, gy in zip(x_global, y_global):
        map_db['obstacles'].add((round(gx, 1), round(gy, 1)))
        
    return np.column_stack((x_global, y_global))

def f_scan_callback(msg):
    global latest_f_scan
    latest_f_scan = process_live_laser(msg, offset_x=0.429, offset_y=0.236, offset_yaw=math.pi/4)

def b_scan_callback(msg):
    global latest_b_scan
    latest_b_scan = process_live_laser(msg, offset_x=-0.429, offset_y=-0.236, offset_yaw=-3*math.pi/4)

# ===========================================================================
# Execution & Visualization
# ===========================================================================
client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
client.run()

if client.is_connected:
    print("[SUCCESS] Connected to robot. Initializing subscriptions...")
    roslibpy.Topic(client, '/amcl_pose', 'geometry_msgs/PoseWithCovarianceStamped').subscribe(amcl_pose_callback)
    roslibpy.Topic(client, '/f_scan', 'sensor_msgs/LaserScan').subscribe(f_scan_callback)
    roslibpy.Topic(client, '/b_scan', 'sensor_msgs/LaserScan').subscribe(b_scan_callback)
else:
    print("[CRITICAL] Could not connect to ROS Bridge.")
    sys.exit()

plt.ion()
fig, ax = plt.subplots(figsize=(10, 10))
ax.set_xlim([-10, 10])
ax.set_ylim([-10, 10])
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.5)

scatter = ax.scatter([], [], c='red', s=6, label='Live Obstacles')
robot_marker, = ax.plot([], [], marker=(3, 0, 0), color='dodgerblue', markersize=20, linestyle='None', label='Robot')
ax.legend(loc='upper right')

save_counter = 0

try:
    while plt.fignum_exists(fig.number):
        if pose_received:
            all_points = np.vstack((latest_f_scan, latest_b_scan))
            if len(all_points) > 0:
                scatter.set_offsets(all_points)
            else:
                scatter.set_offsets(np.empty((0, 2)))
            
            robot_marker.set_data([robot_pose['x']], [robot_pose['y']])
            
            # آپدیت و ذخیره فایل پیکل هر 100 فریم یکبار برای حفظ سرعت اجرا
            save_counter += 1
            if save_counter >= 100:
                with open(SAVE_FILE, 'wb') as f:
                    pickle.dump(map_db, f)
                print(f"[INFO] Data updated in {SAVE_FILE} | Total Stored Obstacles: {len(map_db['obstacles'])}")
                save_counter = 0
            
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            
        time.sleep(0.05)
        
except KeyboardInterrupt:
    # ذخیره نهایی و ایمن اطلاعات هنگام بستن برنامه
    with open(SAVE_FILE, 'wb') as f:
        pickle.dump(map_db, f)
    print(f"\n[INFO] Final save completed successfully. Total Obstacles: {len(map_db['obstacles'])}. Exiting.")

client.terminate()
plt.close()