import os
import sys
import json
import re
import math

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (1/10): JERK & TEMPORAL ORIGIN TRACING <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
agents_dir = os.path.join(PROJECT_ROOT, 'agents')

# 1. MICROSCOPIC JERK & JITTER TRACING (EXACT LOCATIONS)
print('\n[1/3] ISOLATING EXACT POINTS OF KINEMATIC FAILURE & TEMPORAL CHAOS:')
if os.path.exists(train_json_path):
    prev_v, prev_w, prev_frame = None, None, None
    jerk_events = []
    time_tears = []
    
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line_idx, line in enumerate(f):
            try:
                data = json.loads(line)
                action = data.get('ground_truth_action', [0.0, 0.0])
                v, w = float(action[0]), float(action[1])
                uid = data.get('id', '')
                img_path = data.get('image', '')
                
                match = re.search(r'frame_(\d+)', uid)
                frame = int(match.group(1)) if match else -1
                
                if prev_v is not None:
                    delta_v = abs(v - prev_v)
                    delta_w = abs(w - prev_w)
                    
                    # 100x Precision threshold for MiR100 physical limits (0.3 m/s/step is already aggressive)
                    if delta_v > 0.3 or delta_w > 0.4:
                        jerk_events.append({
                            'line': line_idx + 1,
                            'id': uid,
                            'img': img_path,
                            'delta_v': delta_v,
                            'delta_w': delta_w,
                            'prev_speed': [prev_v, prev_w],
                            'curr_speed': [v, w]
                        })
                        
                if prev_frame is not None and frame != -1:
                    frame_gap = frame - prev_frame
                    if frame_gap != 1: # Any jump backward or large jump forward
                        time_tears.append({
                            'line': line_idx + 1,
                            'from_frame': prev_frame,
                            'to_frame': frame,
                            'gap': frame_gap,
                            'id_transition': uid
                        })
                        
                prev_v, prev_w, prev_frame = v, w, frame
            except Exception: pass
            
    print(f'  [*] Scanned {line_idx + 1} lines with 100x precision thresholds.')
    
    # Report Top 3 worst Jerk Events
    print(f'\n  [!] Found {len(jerk_events)} Kinematic Jerk anomalies. Top 3 worst offenders:')
    for i, ev in enumerate(sorted(jerk_events, key=lambda x: x['delta_v'] + x['delta_w'], reverse=True)[:3]):
        # Assuming ~40Hz (0.025s per frame) from MASTER_REPORT, calculate exact video second
        match = re.search(r'frame_(\d+)', ev['id'])
        sec = (int(match.group(1)) * 0.025) if match else 0
        print(f'      -> #FAIL {i+1} at Line {ev["line"]} | Approx Video Time: {sec:.2f}s')
        print(f'         ID: {ev["id"]}')
        print(f'         Image Source: {ev["img"]}')
        print(f'         Jump: v changed by {ev["delta_v"]:.3f}, w changed by {ev["delta_w"]:.3f}')
        print(f'         Data: {ev["prev_speed"]} --> {ev["curr_speed"]}')
        
    # Report Top 3 worst Time Tears
    print(f'\n  [!] Found {len(time_tears)} Temporal Ruptures. Worst transitions:')
    for i, tear in enumerate(sorted(time_tears, key=lambda x: abs(x['gap']), reverse=True)[:3]):
        print(f'      -> #TEAR {i+1} at Line {tear["line"]}: Jumped {tear["gap"]} frames (From F{tear["from_frame"]} directly to F{tear["to_frame"]})')
        print(f'         Transitioned into ID: {tear["id_transition"]}')
else:
    print('[-] train.jsonl not found.')

# 2. IDENTIFYING THE GUILTY AGENT (Who writes this poisoned data?)
print('\n[2/3] FORENSIC AGENT TRACING (Identifying the source of bad data writing):')
guilty_agents = []
for file in os.listdir(agents_dir):
    if file.endswith('.py'):
        try:
            with open(os.path.join(agents_dir, file), 'r', encoding='utf-8-sig') as f:
                content = f.read()
                # Looking for exactly who dumps to jsonl or constructs 'ground_truth_action'
                if 'train.jsonl' in content or 'ground_truth_action' in content or 'json.dump' in content:
                    guilty_agents.append(file)
        except: pass
print(f'  -> Agents responsible for generating/writing this data: {guilty_agents}')

# 3. ROSBRIDGE COMMUNICATION BOTTLENECK SCAN
print('\n[3/3] ROSBRIDGE / WEBSOCKET ARCHITECTURE TRACING:')
ros_agents = []
for file in os.listdir(agents_dir):
    if file.endswith('.py'):
        try:
            with open(os.path.join(agents_dir, file), 'r', encoding='utf-8-sig') as f:
                c = f.read().lower()
                if 'roslibpy' in c or 'websocket' in c or '9090' in c:
                    ros_agents.append(file)
        except: pass
print(f'  -> Agents utilizing WebSockets/ROSBridge instead of native rospy: {ros_agents}')

print('\n>>> PROBE 1/10 COMPLETE. WAITING FOR MICROSCOPIC DATA. <<<')
