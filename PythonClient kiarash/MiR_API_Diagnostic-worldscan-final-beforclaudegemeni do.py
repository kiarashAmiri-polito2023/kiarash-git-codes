#!/usr/bin/env python3
"""
MiR_API_Diagnostic_SmartMap.py
Intelligently reads /status values, identifies the active map (or falls back to a stored map),
and aggressively extracts the SLAM point cloud from the specific map GUID.
"""

import sys
import requests
import hashlib
import base64
import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# ===========================================================================
# Configuration
# ===========================================================================
ROBOT_IP = "192.168.12.20"
MIR_USERNAME = "adminpolito"
MIR_PASSWORD = "Polito2021!"

BASE_URLS = [
    f'http://{ROBOT_IP}/api/v2.0.0',
    f'http://{ROBOT_IP}:8080/api/v2.0.0',
    f'http://{ROBOT_IP}:8080',
]

POINT_HEIGHT_MIN_M = 0.20
POINT_HEIGHT_MAX_M = 0.30

def get_auth_headers():
    hashed_pw = hashlib.sha256(MIR_PASSWORD.encode('utf-8')).hexdigest()
    combined = f"{MIR_USERNAME}:{hashed_pw}"
    encoded = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept-Language": "en_US"
    }

def extract_all_points(data, found_arrays):
    """Recursively searches the ENTIRE JSON for any list of coordinates."""
    if isinstance(data, dict):
        for k, v in data.items():
            extract_all_points(v, found_arrays)
    elif isinstance(data, list) and len(data) > 0:
        first = data[0]
        # [x, y] lists
        if isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(first[0], (int, float)):
            try:
                arr = np.array(data, dtype=float)
                if len(arr) > 10:
                    found_arrays.append(arr[:, :2])
            except: pass
        # [{'x': 1, 'y': 2}] dicts
        elif isinstance(first, dict) and 'x' in first and 'y' in first:
            try:
                arr = np.array([[p['x'], p['y']] for p in data], dtype=float)
                if len(arr) > 10:
                    found_arrays.append(arr)
            except: pass
        else:
            for item in data:
                extract_all_points(item, found_arrays)

def plot_points(points_xy, title):
    fig = plt.figure(figsize=(12, 5))
    
    ax1 = fig.add_subplot(121)
    ax1.scatter(points_xy[:, 0], points_xy[:, 1], s=8, c='tab:blue')
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_title(f'{title} -- 2D')
    ax1.set_aspect('equal')
    ax1.grid(True)

    ax2 = fig.add_subplot(122, projection='3d')
    n = len(points_xy)
    heights = np.random.uniform(POINT_HEIGHT_MIN_M, POINT_HEIGHT_MAX_M, n)
    for i in range(n):
        ax2.plot([points_xy[i, 0], points_xy[i, 0]],
                  [points_xy[i, 1], points_xy[i, 1]],
                  [0, heights[i]], color='tab:orange', linewidth=1.5)
    ax2.scatter(points_xy[:, 0], points_xy[:, 1], heights, s=6, c='tab:red')
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_zlabel('Height (m)')
    ax2.set_title(f'{title} -- 3D')
    
    plt.tight_layout()
    plt.show()

def main():
    print('=====================================================')
    print('  MiR API Diagnostic / Smart Map Extractor')
    print('=====================================================\n')

    headers = get_auth_headers()
    working_base_url = None
    
    # 1. Find correct Port/Base URL
    for base in BASE_URLS:
        try:
            r = requests.get(base + '/status', headers=headers, timeout=2.0)
            if r.status_code == 200:
                working_base_url = base
                break
        except: pass

    if not working_base_url:
        print('[CRITICAL] Cannot connect to MiR.')
        return

    # 2. Extract REAL values from /status
    print(f"[1] Fetching live /status from {working_base_url}...")
    r_status = requests.get(working_base_url + '/status', headers=headers).json()
    active_map_id = r_status.get('map_id')
    
    print(f"  -> Robot State:   {r_status.get('state_text')}")
    print(f"  -> Battery:       {r_status.get('battery_percentage')}%")
    print(f"  -> Position:      {r_status.get('position')}")
    print(f"  -> Active Map ID: {active_map_id}")

    # 3. Check Database & Handle '-1' issue
    print("\n[2] Fetching /maps database...")
    r_maps = requests.get(working_base_url + '/maps', headers=headers).json()
    print(f"  -> Found {len(r_maps)} maps stored in the robot.")
    
    target_guid = None
    if str(active_map_id) != '-1' and active_map_id is not None:
        target_guid = str(active_map_id)
        print(f"  -> Proceeding with ACTIVE map GUID: {target_guid}")
    elif len(r_maps) > 0:
        target_guid = r_maps[0].get('guid')
        print("  -> Robot has NO active map (map_id = -1).")
        print(f"  -> Auto-fallback to the first available map: '{r_maps[0].get('name')}' ({target_guid})")
        
    # 4. Fetch the specific Map data and extract points
    if target_guid:
        print(f"\n[3] Fetching full SLAM data for map GUID: {target_guid}...")
        r_target = requests.get(working_base_url + f'/maps/{target_guid}', headers=headers).json()
        
        # Save raw JSON for inspection
        with open('mir_target_map_raw.json', 'w') as f:
            json.dump(r_target, f, indent=2)
        print("  -> Saved raw map data to 'mir_target_map_raw.json'")
        
        # Aggressively extract coordinates
        found_arrays = []
        extract_all_points(r_target, found_arrays)
        
        if found_arrays:
            largest_array = max(found_arrays, key=len)
            print(f"\n[SUCCESS] Extracted {len(largest_array)} points from map! Plotting...")
            plot_points(largest_array, f'Map GUID: {target_guid}')
        else:
            print("\n[INFO] No point clouds found inside this specific map either. Please inspect 'mir_target_map_raw.json'.")

if __name__ == '__main__':
    main()