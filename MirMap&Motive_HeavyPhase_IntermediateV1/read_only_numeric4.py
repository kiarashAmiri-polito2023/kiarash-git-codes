import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN NUMERIC/VISION AUDIT 4/5: TEMPORAL SYNC & FRAME CONTINUITY <<<')

# 1. DATASET FRAME CONTINUITY CHECK (Are we dropping frames?)
print('\n[1/2] DATASET FRAME CONTINUITY ANALYSIS:')
train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
frame_numbers = []

try:
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # Extracted ID example: session_2026-08-27_17-54-20_frame_00281
            uid = data.get('id', '')
            match = re.search(r'frame_(\d+)', uid)
            if match:
                frame_numbers.append(int(match.group(1)))
except Exception as e:
    print(f'  [-] Error reading dataset: {e}')

if frame_numbers:
    frame_numbers.sort()
    total_frames = len(frame_numbers)
    min_f, max_f = frame_numbers[0], frame_numbers[-1]
    
    # Calculate drops
    expected_frames = (max_f - min_f) + 1
    dropped_frames = expected_frames - total_frames
    drop_rate = (dropped_frames / expected_frames) * 100 if expected_frames > 0 else 0
    
    print(f'  -> Processed {total_frames} frame IDs.')
    print(f'  -> Min Frame: {min_f}, Max Frame: {max_f}')
    print(f'  -> Dropped/Missing Frames: {dropped_frames} ({drop_rate:.2f}%)')
    
    if drop_rate > 15.0:
        print('  [-] WARNING: High frame drop rate. Temporal continuity is severely broken. VLM might struggle with temporal awareness.')
    else:
        print('  [+] VERDICT: Acceptable frame continuity. The visual flow for the robot is stable over time.')
else:
    print('  [-] No frame numbers could be extracted from dataset IDs.')

# 2. SOURCE CODE TEMPORAL SYNC (LiDAR vs Motive Time-slip prevention)
print('\n[2/2] SOURCE CODE SCAN FOR SENSOR SYNCHRONIZATION:')
agents_to_check = ['slam_to_bev.py', 'cross_modal_aligner.py', 'bev_image_renderer.py']
agents_dir = os.path.join(PROJECT_ROOT, 'agents')
sync_logic_found = False

for agent in agents_to_check:
    path = os.path.join(agents_dir, agent)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            c = f.read()
            # Searching for standard ROS or Python timestamp synchronization methods
            if any(kw in c for kw in ['message_filters', 'ApproximateTimeSynchronizer', 'time_sync', 'timestamp', 'rospy.Time.now']):
                print(f'  [+] Temporal Sync Logic detected in: {agent}')
                sync_logic_found = True
                
                # Extract exact line
                lines = c.split('\n')
                for i, l in enumerate(lines):
                    if any(kw in l for kw in ['message_filters', 'TimeSynchronizer', 'timestamp', 'sync']):
                        print(f'      -> Line {i+1}: {l.strip()}')

if not sync_logic_found:
    print('  [-] WARNING: No hardcoded ROS temporal synchronization found in checked agents. Sync might be handled externally or assumed perfect.')

print('\n>>> NUMERIC TEST 4/5 COMPLETE. WAITING FOR TEMPORAL ALIGNMENT RESULTS. <<<')
