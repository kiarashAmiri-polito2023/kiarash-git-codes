import os
import sys
import json
import math

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN NUMERIC/VISION AUDIT 2/5: KINEMATIC BIAS & VARIANCE ANALYSIS <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
v_speeds = []
w_speeds = []

try:
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            action = data.get('ground_truth_action', [0.0, 0.0])
            v_speeds.append(float(action[0]))
            w_speeds.append(float(action[1]))
except Exception as e:
    print(f'[-] Error reading dataset: {e}')
    sys.exit(1)

# --- MATHEMATICAL DISTRIBUTION ANALYSIS ---
n = len(v_speeds)
if n == 0:
    print('[-] No valid kinematic data found.')
    sys.exit(1)

# Mean
mean_v = sum(v_speeds) / n
mean_w = sum(w_speeds) / n

# Variance & Standard Deviation
var_v = sum((v - mean_v) ** 2 for v in v_speeds) / n
var_w = sum((w - mean_w) ** 2 for w in w_speeds) / n
std_v = math.sqrt(var_v)
std_w = math.sqrt(var_w)

# Directional Bias (Left vs Right turns)
left_turns = sum(1 for w in w_speeds if w > 0.05)
right_turns = sum(1 for w in w_speeds if w < -0.05)
straight = sum(1 for w in w_speeds if abs(w) <= 0.05)

print('\n[1/2] KINEMATIC DISTRIBUTION & BALANCE:')
print(f'  -> Total Samples: {n}')
print(f'  -> Linear Velocity (v): Mean = {mean_v:.4f} m/s | StdDev = {std_v:.4f}')
print(f'  -> Angular Velocity (w): Mean = {mean_w:.4f} rad/s | StdDev = {std_w:.4f}')

print('\n[2/2] DIRECTIONAL BIAS ANALYSIS (Obstacle Avoidance Balance):')
print(f'  -> Left Turns (w > 0): {left_turns} samples')
print(f'  -> Right Turns (w < 0): {right_turns} samples')
print(f'  -> Straight/Idle (w ~ 0): {straight} samples')

if left_turns == 0 or right_turns == 0:
    print('  [-] CRITICAL BIAS: The robot is missing turning data for one direction. AI will fail in real navigation.')
elif max(left_turns, right_turns) / min(left_turns, right_turns) > 2.0:
    print('  [!] WARNING: Severe directional bias detected. The AI will favor turning to one specific side.')
else:
    print('  [+] VERDICT: Directional turning data is relatively balanced. AI can learn bidirectional obstacle avoidance.')

print('\n>>> NUMERIC TEST 2/5 COMPLETE. WAITING FOR STATISTICAL RESULTS. <<<')
