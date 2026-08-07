import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIM TEST 2/5: MUTUAL SUPERVISION & LATENCY DEEP DIVE <<<')

# 1. DATASET DECODING (How do LiDAR and Motive teach each other?)
print('\n[1/3] DECODING MUTUAL SUPERVISION IN DATASET (train.jsonl):')
train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
if os.path.exists(train_json_path):
    try:
        with open(train_json_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            data = json.loads(first_line)
            print('  [+] Successfully extracted Sample 1 structure:')
            # Print keys to understand architecture
            for key, value in data.items():
                val_preview = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                print(f'      -> Key: {key:15} | Value Preview: {val_preview}')
    except Exception as e:
        print(f'  [-] Failed to parse JSON dataset: {e}')
else:
    print('  [-] train.jsonl not found.')

# 2. SPEED & LATENCY METRICS EXTRACTION
print('\n[2/3] EXTRACTING SPEED/LATENCY FROM MASTER_REPORT.md:')
report_path = os.path.join(PROJECT_ROOT, 'MASTER_REPORT.md')
if os.path.exists(report_path):
    try:
        with open(report_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            print('  [+] Latency/Speed benchmarks found in report:')
            metrics_found = 0
            for i, line in enumerate(lines):
                lower_line = line.lower()
                if any(x in lower_line for x in [' ms', 'hz', 'fps', 'latency', 'speed']):
                    print(f'      -> Line {i+1}: {line.strip()}')
                    metrics_found += 1
            if metrics_found == 0:
                print('      [-] No explicit timing numbers found in text despite initial match.')
    except Exception as e:
        print(f'  [-] Error reading report: {e}')
else:
    print('  [-] MASTER_REPORT.md not found.')

# 3. GLOBAL 41-AGENT INTERSECTION SCAN (Finding the hidden brain)
print('\n[3/3] GLOBAL AGENT SCAN FOR HIDDEN OBSTACLE FUSION LOGIC:')
agents_dir = os.path.join(PROJECT_ROOT, 'agents')
found_intersection = False

if os.path.exists(agents_dir):
    for filename in os.listdir(agents_dir):
        if filename.endswith('.py'):
            filepath = os.path.join(agents_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    content = f.read().lower()
                    # Check if this agent contains both 'obstacle' AND ('lidar' OR 'scan') AND 'motive'
                    if 'obstacle' in content and ('lidar' in content or 'scan' in content) and ('motive' in content or 'optitrack' in content):
                        print(f'  [+] Hidden Brain Candidate Found: {filename}')
                        found_intersection = True
                        
                        # Extract the specific lines
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if 'obstacle' in line and ('lidar' in line or 'motive' in line or 'align' in line):
                                print(f'      -> L{i+1}: {line.strip()}')
            except:
                pass

if not found_intersection:
    print('  [-] No single agent explicitly combines LiDAR, Motive, and Obstacle text in its logic. The fusion might be purely VLM-based or externalized.')

print('\n>>> TEST 2/5 COMPLETE. WAITING FOR RESULTS TO REVEAL REAL-TIME VS PRE-PROC. <<<')
