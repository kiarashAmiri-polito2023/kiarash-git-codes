import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 40-DIMENSIONAL SYSTEM VALIDATION PROBE 3/5 (READ-ONLY) <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
v_vals = []
w_vals = []

if os.path.exists(train_json_path):
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                action = data.get('ground_truth_action', [0.0, 0.0])
                v_vals.append(float(action[0]))
                w_vals.append(float(action[1]))
            except: pass

print(f'\n[1/2] Linear Velocity (v) Range Bounds Check:')
if v_vals:
    print(f'  -> Min Linear v: {min(v_vals):.4f} m/s | Max Linear v: {max(v_vals):.4f} m/s')
    print('  -> [DIM 61-70 STATUS]: Linear velocity boundaries mapped.')

print(f'\n[2/2] Angular Velocity (w) Range Bounds Check:')
if w_vals:
    print(f'  -> Min Angular w: {min(w_vals):.4f} rad/s | Max Angular w: {max(w_vals):.4f} rad/s')
    print('  -> [DIM 71-80 STATUS]: Angular velocity boundaries mapped.')

print('\n>>> 40-DIMENSIONAL PROBE 3/5 COMPLETE. NO CODE WAS ALTERED. <<<')
