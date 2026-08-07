import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIM TEST 1/5: CROSS-MODAL OBSTACLE DETECTION AUDIT <<<')

target_agents = ['scene_object_detector.py', 'cross_modal_aligner.py', 'slam_to_bev.py', 'vla_dataset_builder.py']
agents_dir = os.path.join(PROJECT_ROOT, 'agents')

# 1. DEEP CODE LOGIC EXTRACTION (LiDAR vs Motive Interaction)
print('\n[1/3] EXTRACTING MUTUAL LEARNING LOGIC (LiDAR & Motive):')
for agent in target_agents:
    agent_path = os.path.join(agents_dir, agent)
    if os.path.exists(agent_path):
        print(f'\n  [*] Analyzing {agent}:')
        with open(agent_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Extract functions related to obstacle, lidar, motive, align
            funcs = [line.strip() for line in lines if line.strip().startswith('def ') and any(kw in line.lower() for kw in ['obstacle', 'lidar', 'scan', 'motive', 'optitrack', 'align', 'fuse'])]
            if funcs:
                print('      -> Core Functions Discovered:')
                for fn in funcs: print(f'         {fn}')
            
            # Look for explicit fusion/teaching mathematical logic
            fusion_keywords = ['np.bitwise_or', 'np.bitwise_and', 'overlap', 'IOU', 'distance', 'transform', 'error']
            found_logic = {}
            for i, line in enumerate(lines):
                if any(fk in line for fk in fusion_keywords) and ('lidar' in line.lower() or 'motive' in line.lower() or 'obstacle' in line.lower()):
                    found_logic[i+1] = line.strip()
            if found_logic:
                print('      -> Cross-Modal Math/Logic detected at lines:')
                for lnum, lcode in list(found_logic.items())[:3]:  # show top 3
                    print(f'         Line {lnum}: {lcode}')
    else:
        print(f'  [-] {agent} NOT FOUND.')

# 2. SEARCHING FOR SPEED/LATENCY METRICS IN REPORTS
print('\n[2/3] SCANNING REPORTS FOR DETECTION SPEED & LATENCY:')
report_files = [f for f in os.listdir(PROJECT_ROOT) if f.endswith('.md') or f.endswith('.txt') or f.endswith('.json')]
latency_evidence = False
for rep in report_files:
    try:
        with open(os.path.join(PROJECT_ROOT, rep), 'r', encoding='utf-8-sig') as f:
            content = f.read().lower()
            if 'ms' in content or 'latency' in content or 'fps' in content or 'hz' in content:
                print(f'  [+] Found timing/speed metrics in {rep}')
                latency_evidence = True
    except:
        pass
if not latency_evidence:
    print('  [-] No explicit execution speed (Latency/FPS) found in root reports.')

# 3. VERIFYING JSON DATASET STRUCTURE FOR OBSTACLES
print('\n[3/3] EXAMINING DATASET (train.jsonl) FOR OBSTACLE SUPERVISION TRACES:')
train_json = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
if os.path.exists(train_json):
    try:
        with open(train_json, 'r', encoding='utf-8') as f:
            first_line = f.readline().lower()
            if 'obstacle' in first_line or 'lidar' in first_line or 'motive' in first_line or 'bbox' in first_line:
                print('  [+] Dataset contains explicit obstacle/sensor trace keys!')
            else:
                print('  [-] Dataset appears to rely purely on BEV images, no explicit explicit obstacle coordinates in text.')
    except Exception as e:
        print(f'  [-] Error reading JSON: {e}')

print('\n>>> TEST 1/5 COMPLETE. WAITING FOR OUTPUT. <<<')
