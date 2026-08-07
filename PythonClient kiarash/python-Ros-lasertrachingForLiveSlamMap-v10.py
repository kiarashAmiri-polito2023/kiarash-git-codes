#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash Amiri Polito
Email: s322803@studenti.polito.it
GitHub: https://github.com/kiarashAmiri-polito2023/kiarash-git-codes.git

Description:
  Ultimate MiR SLAM Map & State Viewer with Comprehensive Lightweight Persistence.
  Saves global map grid, obstacles, robot live position, orientation (yaw), speed, 
  and historical path into a single updating PKL file inside the 'map' folder for Qwen-VL.
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
        if not isinstance(map_db, dict):
            map_db = {"obstacles": set(), "path": [], "map_metadata": {}, "map_grid": None, "latest_robot_state": {}}
        if "obstacles" not in map_db: map_db["obstacles"] = set()
        if "path" not in map_db: map_db["path"] = []
        if "map_metadata" not in map_db: map_db["map_metadata"] = {}
        if "map_grid" not in map_db: map_db["map_grid"] = None
        if "latest_robot_state" not in map_db: map_db["latest_robot_state"] = {}
        
        print(f"[INFO] Loaded existing DB: {len(map_db['obstacles'])} obstacles, {len(map_db['path'])} path points found.")
    except Exception as e:
        print(f"[WARNING] Could not load old pickle file, creating new database. Error: {e}")
        map_db = {"obstacles": set(), "path": [], "map_metadata": {}, "map_grid": None, "latest_robot_state": {}}
else:
    map_db = {"obstacles": set(), "path": [], "map_metadata": {}, "map_grid": None, "latest_robot_state": {}}

# متغیرهای سراسری برای ذخیره داده‌ها[cite: 2]
map_data_2d = None
map_extent = None
robot_pose = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
latest_f_scan = np.empty((0, 2))
latest_b_scan = np.empty((0, 2))
pose_received = False
last_pose_time = time.time()

def map_callback(msg):
    """
    دریافت، دیکد کردن و پردازش نقشه خام SLAM به یک تصویر دوبعدی و ذخیره متادیتای آن[cite: 2].
    """
    global map_data_2d, map_extent, map_db
    info = msg.get('info', {})
    data = msg.get('data', [])
    
    if data and info:
        width = info.get('width', 0)
        height = info.get('height', 0)
        resolution = info.get('resolution', 0.05)
        origin_x = info.get('origin', {}).get('position', {}).get('x', 0.0)
        origin_y = info.get('origin', {}).get('position', {}).get('y', 0.0)
        
        # ذخیره متادیتا و گرید نقشه برای تحلیل مدل هوش مصنوعی
        map_db["map_metadata"] = {
            "width": width,
            "height": height,
            "resolution": resolution,
            "origin_x": origin_x,
            "origin_y": origin_y
        }
        
        # تبدیل آرایه یک‌بعدی به دوبعدی[cite: 2]
        arr = np.array(data, dtype=float).reshape((height, width))
        arr = np.where(arr == -1, np.nan, arr)
        map_data_2d = arr
        map_db["map_grid"] = arr # ذخیره نهایی نقشه در دیتابیس
        
        # محاسبه ابعاد واقعی نقشه برای قفل کردن بوم[cite: 2]
        map_extent = [
            origin_x, 
            origin_x + (width * resolution),
            origin_y, 
            origin_y + (height * resolution)
        ]

def robot_pose_callback(msg):
    """دریافت مختصات قطعی ربات، محاسبه سرعت و ثبت جهت‌گیری (Orientation & Yaw)[cite: 2]."""
    global robot_pose, pose_received, last_pose_time, map_db
    position = msg.get('position', {})
    orientation = msg.get('orientation', {})
    
    current_x = position.get('x', 0.0)
    current_y = position.get('y', 0.0)
    
    qx = orientation.get('x', 0.0)
    qy = orientation.get('y', 0.0)
    qz = orientation.get('z', 0.0)
    qw = orientation.get('w', 1.0)
    
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    current_yaw = math.atan2(siny_cosp, cosy_cosp)
    
    robot_pose['x'] = current_x
    robot_pose['y'] = current_y
    robot_pose['yaw'] = current_yaw
    pose_received = True
    
    # محاسبه سرعت لحظه‌ای (متر بر ثانیه) و فواصل زمانی
    current_time = time.time()
    dt = current_time - last_pose_time
    speed = 0.0
    if len(map_db['path']) > 0 and dt > 0:
        last_pt = map_db['path'][-1]
        dist = math.dist((current_x, current_y), (last_pt['x'], last_pt['y']))
        speed = dist / dt
    last_pose_time = current_time
    
    # ساخت بسته وضعیت کامل ربات برای Qwen-VL
    robot_state = {
        'x': round(current_x, 2),
        'y': round(current_y, 2),
        'yaw': round(current_yaw, 2),
        'orientation_quat': {'x': qx, 'y': qy, 'z': qz, 'w': qw},
        'speed': round(speed, 2),
        'timestamp': current_time
    }
    
    map_db['latest_robot_state'] = robot_state
    
    # ثبت مسیر حرکتی با فیلتر فاصله برای سبک ماندن فایل
    if len(map_db['path']) == 0 or math.dist((current_x, current_y), (map_db['path'][-1]['x'], map_db['path'][-1]['y'])) > 0.4:
        map_db['path'].append(robot_state)

def process_live_laser(msg, offset_x, offset_y, offset_yaw):
    """تبدیل نقاط خام لیزر به مختصات جهانی و ذخیره به عنوان موانع[cite: 2]."""
    global map_db
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
    
    # مختصات محلی و اعمال زاویه نصب سنسور[cite: 2]
    x_l = r * np.cos(angles)
    y_l = r * np.sin(angles)
    cos_s, sin_s = np.cos(offset_yaw), np.sin(offset_yaw)
    x_base = (x_l * cos_s - y_l * sin_s) + offset_x
    y_base = (x_l * sin_s + y_l * cos_s) + offset_y
    
    # انتقال به مختصات جهانی[cite: 2]
    cos_r, sin_r = np.cos(robot_pose['yaw']), np.sin(robot_pose['yaw'])
    x_global = robot_pose['x'] + (x_base * cos_r - y_base * sin_r)
    y_global = robot_pose['y'] + (x_base * sin_r + y_base * cos_r)
    
    # ذخیره و رند کردن موانع در حافظه دائمی (به صورت Set برای حذف تکرارها و سبک ماندن فایل)
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
print("=====================================================")
print("  MiR Ultimate SLAM Viewer with Full AI State Logger[cite: 2]")
print("=====================================================")

client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
client.run()

if not client.is_connected:
    print("[CRITICAL] Failed to connect to ROS Bridge.")
    sys.exit()

print("[SUCCESS] Connected! Requesting SLAM Map from robot[cite: 2]...")

# ابتدا فقط به نقشه وصل می‌شویم تا دانلود کامل شود[cite: 2]
map_listener = roslibpy.Topic(client, '/map', 'nav_msgs/OccupancyGrid')
map_listener.subscribe(map_callback)

print("    [..] Downloading large map data", end="")
timeout = 150
while map_data_2d is None and timeout > 0:
    time.sleep(0.1)
    timeout -= 1
    if timeout % 10 == 0:
        print(".", end="")
        sys.stdout.flush()
print("")

if map_data_2d is None:
    print("[ERROR] Map download timed out. Check network or robot mapping status[cite: 2].")
    client.terminate()
    sys.exit()
    
print("[SUCCESS] Map successfully downloaded and decoded[cite: 2]!")
map_listener.unsubscribe()

# حالا به سنسورهای زنده متصل می‌شویم[cite: 2]
roslibpy.Topic(client, '/robot_pose', 'geometry_msgs/Pose').subscribe(robot_pose_callback)
roslibpy.Topic(client, '/f_scan', 'sensor_msgs/LaserScan').subscribe(f_scan_callback)
roslibpy.Topic(client, '/b_scan', 'sensor_msgs/LaserScan').subscribe(b_scan_callback)

plt.ion()
fig, ax = plt.subplots(figsize=(10, 10))

# 1. رسم نقشه ثابت در پس‌زمینه[cite: 2]
ax.imshow(map_data_2d, cmap='gray_r', origin='lower', extent=map_extent)

# 2. قفل کردن کادر دوربین روی ابعاد واقعی نقشه[cite: 2]
ax.set_xlim([map_extent[0], map_extent[1]])
ax.set_ylim([map_extent[2], map_extent[3]])
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.3)

scatter_obstacles = ax.scatter([], [], c='red', s=6, label='Live Scanners')
robot_marker, = ax.plot([], [], marker=(3, 0, 0), color='dodgerblue', markersize=20, linestyle='None', label='MiR Robot')

ax.set_xlabel('Global X (m)')
ax.set_ylabel('Global Y (m)')
ax.set_title('MiR Global SLAM: Fixed Map & Moving Robot')
ax.legend(loc='upper right')

save_counter = 0

try:
    while plt.fignum_exists(fig.number):
        if pose_received:
            # همگام‌سازی لیزرها[cite: 2]
            all_laser_points = np.vstack((latest_f_scan, latest_b_scan))
            if len(all_laser_points) > 0:
                scatter_obstacles.set_offsets(all_laser_points)
            else:
                scatter_obstacles.set_offsets(np.empty((0, 2)))
                
            # آپدیت موقعیت ربات در نقشه ثابت[cite: 2]
            robot_marker.set_data([robot_pose['x']], [robot_pose['y']])
            t = plt.matplotlib.markers.MarkerStyle(marker=(3, 0, 0))
            t._transform = t.get_transform().rotate(robot_pose['yaw'] - math.pi/2)
            robot_marker.set_marker(t)
            
            # ذخیره کردن و آپدیت فایل پیکل هر 100 فریم یکبار برای حفظ سرعت اجرای برنامه
            save_counter += 1
            if save_counter >= 100:
                with open(SAVE_FILE, 'wb') as f:
                    pickle.dump(map_db, f)
                print(f"[INFO] PKL Updated in {SAVE_FILE} | Obstacles: {len(map_db['obstacles'])} | Speed: {map_db['latest_robot_state'].get('speed', 0)} m/s")
                save_counter = 0
            
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            
        time.sleep(0.05)
        
except KeyboardInterrupt:
    # ذخیره نهایی و ایمن هنگام بستن برنامه[cite: 2]
    with open(SAVE_FILE, 'wb') as f:
        pickle.dump(map_db, f)
    print(f"\n[INFO] Final save completed successfully. Total Obstacles: {len(map_db['obstacles'])}. Exiting.")

client.terminate()
plt.close()