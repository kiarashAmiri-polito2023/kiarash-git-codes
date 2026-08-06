#!/usr/bin/env python3
"""
MiR_API_Diagnostic_Standalone.py
Aggressive Extraction Version.
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
# Hardcoded Configuration
# ===========================================================================
ROBOT_IP = "192.168.12.20"
MIR_USERNAME = "adminpolito"
MIR_PASSWORD = "Polito2021!"

CANDIDATE_ENDPOINTS = ['/status', '/world_model', '/maps']
CANDIDATE_BASE_URLS = [
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

def test_endpoint(base_url, endpoint, headers):
    url = base_url.rstrip('/') + endpoint
    try:
        resp = requests.get(url, headers=headers, timeout=5.0)
        result = {'endpoint': endpoint, 'status_code': resp.status_code, 'error': None, 'data': None}
        if resp.status_code == 200:
            try:
                result['data'] = resp.json()
            except Exception:
                result['data'] = f'(non-JSON response, {len(resp.content)} bytes)'
        return result
    except Exception as e:
        return {'endpoint': endpoint, 'status_code': None, 'error': str(e), 'data': None}

def summarize_json(data, max_len=200):
    if isinstance(data, dict):
        return f'dict with keys: {list(data.keys())}'
    if isinstance(data, list):
        return f'list, len={len(data)}'
    return str(data)[:max_len]

def extract_all_points(data, found_arrays):
    """Recursively searches the ENTIRE JSON for any list of coordinates."""
    if isinstance(data, dict):
        for k, v in data.items():
            extract_all_points(v, found_arrays)
    elif isinstance(data, list) and len(data) > 0:
        first = data[0]
        # Check if it's a raw list of [x, y]
        if isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(first[0], (int, float)):
            try:
                arr = np.array(data, dtype=float)
                if len(arr) > 10:  # Ignore tiny arrays (like robot footprint)
                    found_arrays.append(arr[:, :2])
            except: pass
        # Check if it's a list of dicts like [{'x': 1, 'y': 2}]
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
    ax2.set_title(f'{title} -- Extruded 3D view')
    
    plt.tight_layout()
    plt.show()

def main():
    print('=====================================================')
    print('  MiR API Diagnostic / Aggressive Extractor Tool')
    print('=====================================================\n')

    headers = get_auth_headers()
    working_base_url = None
    
    for base_url in CANDIDATE_BASE_URLS:
        r = test_endpoint(base_url, '/status', headers)
        if r['status_code'] == 200:
            working_base_url = base_url
            break

    if not working_base_url:
        print('\n[CRITICAL] Cannot connect.')
        return

    print(f'\nTesting endpoints against: {working_base_url}\n')
    results = []
    for endpoint in CANDIDATE_ENDPOINTS:
        r = test_endpoint(working_base_url, endpoint, headers)
        results.append(r)
        if r['error']:
            print(f"  {endpoint:30s} -> ERROR: {r['error']}")
        elif r['status_code'] == 200:
            print(f"  {endpoint:30s} -> 200 OK   | {summarize_json(r['data'])}")
        else:
            print(f"  {endpoint:30s} -> HTTP {r['status_code']}")

    print('\n=====================================================')
    print('Saving raw /world_model JSON to file and searching for points...')
    
    found_any = False
    for r in results:
        if r['status_code'] == 200 and r['data'] is not None and r['endpoint'] == '/world_model':
            # Save raw JSON for manual inspection
            try:
                with open('mir_world_model_raw.json', 'w') as f:
                    json.dump(r['data'], f, indent=2)
                print("  -> Saved raw data to 'mir_world_model_raw.json'.")
            except: pass

            # Aggressive extraction
            found_arrays = []
            extract_all_points(r['data'], found_arrays)
            
            if found_arrays:
                found_any = True
                # Select the largest array (most likely to be the full point cloud)
                largest_array = max(found_arrays, key=len)
                print(f"[FOUND] Extracted {len(largest_array)} points from {r['endpoint']} -- plotting...")
                plot_points(largest_array, r['endpoint'])

    if not found_any:
        print('\n[INFO] No point clouds found. Please open "mir_world_model_raw.json" in your editor to see the structure.')

if __name__ == '__main__':
    main()