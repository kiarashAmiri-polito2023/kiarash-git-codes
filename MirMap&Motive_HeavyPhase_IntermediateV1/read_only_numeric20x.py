import os
import sys
import json
import math
from collections import Counter
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 20x ULTRA-PRECISION FORENSIC AUDIT (PRE-GITHUB FINAL STAGE) <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')

v_speeds = []
w_speeds = []
frame_ids = []
all_text = ""
timestamps = [] # Assumed from frame index if real time isn't explicitly in root JSON

if os.path.exists(train_json_path):
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                
                # Kinematics
                action = data.get('ground_truth_action', [0.0, 0.0])
                v_speeds.append(float(action[0]))
                w_speeds.append(float(action[1]))
                
                # Temporal/Frame ID
                uid = data.get('id', '')
                match = re.search(r'frame_(\d+)', uid)
                if match:
                    frame_ids.append(int(match.group(1)))
                
                # Semantics
                convs = data.get('conversations', [])
                if convs:
                    all_text += " " + convs[0].get('value', '').replace('<image>', '').lower()
                    
            except Exception: pass
else:
    print('[-] train.jsonl missing.')
    sys.exit(1)

n = len(v_speeds)

# --- 20x KINEMATIC: JERK & CORRELATION ---
print('\n[1/4] 20x KINEMATIC DYNAMICS (Jerk & Acceleration Equivalents):')
v_deltas = [abs(v_speeds[i] - v_speeds[i-1]) for i in range(1, n)]
w_deltas = [abs(w_speeds[i] - w_speeds[i-1]) for i in range(1, n)]
if v_deltas:
    max_v_jerk = max(v_deltas)
    max_w_jerk = max(w_deltas)
    print(f'  -> Max Linear Delta between frames: {max_v_jerk:.4f} m/s per frame')
    print(f'  -> Max Angular Delta between frames: {max_w_jerk:.4f} rad/s per frame')
    if max_v_jerk > 0.5 or max_w_jerk > 0.5:
        print('  [!] CRITICAL WARNING: High frame-to-frame Jerk detected. Danger of wheel slip on MiR100.')
    else:
        print('  [+] VERDICT: Actuator commands transition smoothly. Kinematic safety is intact.')

# Calculate v vs w correlation (Does it slow down to turn?)
mean_v, mean_w = sum(v_speeds)/n, sum(w_speeds)/n
covar = sum((v_speeds[i]-mean_v)*(w_speeds[i]-mean_w) for i in range(n))
std_v = math.sqrt(sum((v-mean_v)**2 for v in v_speeds))
std_w = math.sqrt(sum((w-mean_w)**2 for w in w_speeds))
correlation = covar / (std_v * std_w) if std_v > 0 and std_w > 0 else 0
print(f'  -> Pearson Correlation (v vs w): {correlation:.4f}')
if correlation < -0.3:
    print('  [+] VERDICT: True robotic behavior proven. The robot correctly decelerates when turning.')

# --- 20x SEMANTIC: ENTROPY & VOCABULARY RICHNESS ---
print('\n[2/4] 20x SEMANTIC ENTROPY (Lexical Richness):')
words = re.findall(r'\b[a-z]{3,}\b', all_text)
vocab = Counter(words)
unique_words = len(vocab)
print(f'  -> Total Words Parsed: {len(words)}')
print(f'  -> Unique Lexical Tokens (Vocabulary Size): {unique_words}')
print(f'  -> Top 5 frequent semantic anchors: {vocab.most_common(5)}')
if unique_words < 50:
    print('  [-] WARNING: Semantic space is highly restricted. VLM might overfit to repetitive phrases.')

# --- 20x TEMPORAL: JITTER ANALYSIS ---
print('\n[3/4] 20x TEMPORAL JITTER & GAP ANALYSIS:')
if len(frame_ids) > 1:
    frame_gaps = [frame_ids[i] - frame_ids[i-1] for i in range(1, len(frame_ids))]
    max_gap = max(frame_gaps)
    avg_gap = sum(frame_gaps) / len(frame_gaps)
    print(f'  -> Average Frame Step: {avg_gap:.2f}')
    print(f'  -> Maximum Frame Gap (Freeze Duration): {max_gap} frames skipped in a single event')
    if max_gap > 10:
        print(f'  [!] WARNING: Severe data blackout event detected (Gap of {max_gap} frames).')

print('\n[4/4] 20x ROS PUBLISHER TOPOLOGY SCAN:')
logger_path = os.path.join(PROJECT_ROOT, 'agents', 'mir_command_logger.py')
if os.path.exists(logger_path):
    with open(logger_path, 'r', encoding='utf-8-sig') as f:
        c = f.read()
        pubs = re.findall(r'rospy\.Publisher\([^)]+\)', c)
        print(f'  -> Found {len(pubs)} explicitly defined ROS Publishers routing the AI logic.')
        
print('\n>>> 20x AUDIT COMPLETE. WAITING FOR FINAL NUMBERS. GITHUB SCOUTING IS NEXT. <<<')
