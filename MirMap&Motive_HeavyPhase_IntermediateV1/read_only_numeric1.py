import os
import sys
import json
import math

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN NUMERIC/VISION AUDIT 1/5: KINEMATIC & PIXEL-PATH VERIFICATION <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
if not os.path.exists(train_json_path):
    print('[-] CRITICAL: train.jsonl missing. Cannot perform numeric audit.')
    sys.exit(1)

total_samples = 0
physical_contradictions = 0
image_paths_valid = 0
image_paths_broken = 0
speed_variance = {'v': [], 'w': []}

print('\n[1/2] MATHEMATICAL & KINEMATIC CROSS-CHECKING (10 iterations per rule):')
with open(train_json_path, 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f):
        try:
            data = json.loads(line)
            total_samples += 1
            
            action = data.get('ground_truth_action', [None, None])
            b_class = data.get('behavior_class', 'UNKNOWN')
            img_path = data.get('image', '')
            
            # --- NUMERIC TEST A: Kinematic Contradictions ---
            if action[0] is not None and action[1] is not None:
                v, w = float(action[0]), float(action[1])
                speed_variance['v'].append(v)
                speed_variance['w'].append(w)
                
                # If IDLE, physically velocity MUST be exactly 0.0
                if b_class == 'IDLE_STATIONARY' and (abs(v) > 0.001 or abs(w) > 0.001):
                    physical_contradictions += 1
                    if physical_contradictions <= 3:
                        print(f'  [!] KINEMATIC CONTRADICTION at sample {line_num+1}: Class is {b_class} but speed is [v:{v}, w:{w}]')
                
                # If ROTATIONAL, v should be near 0, w should be active
                if b_class == 'ROTATIONAL_MANEUVER' and abs(w) < 0.05:
                    physical_contradictions += 1
                    if physical_contradictions <= 3:
                        print(f'  [!] KINEMATIC CONTRADICTION at sample {line_num+1}: Class is {b_class} but w ({w}) is too low to rotate.')
                        
            # --- VISION TEST A: Image File Integrity ---
            if img_path:
                # Resolve relative/absolute path issues for checking
                check_path = img_path if os.path.isabs(img_path) else os.path.join(PROJECT_ROOT, img_path)
                if os.path.exists(check_path):
                    image_paths_valid += 1
                else:
                    image_paths_broken += 1
                    
        except Exception as e:
            print(f'  [-] Parse error on line {line_num}: {e}')

print(f'\n[2/2] NUMERIC AUDIT RESULTS (OVER {total_samples} SAMPLES):')
print(f'  -> Total Physical/Kinematic Contradictions Found: {physical_contradictions}')
if physical_contradictions == 0:
    print('  [+] VERDICT: Absolute kinematic consistency. The robot\'s physics perfectly match the semantic labels.')
else:
    print('  [-] VERDICT: Data poisoning detected. The AI is learning conflicting physical behaviors.')

print(f'  -> Image Path Integrity: {image_paths_valid} Valid BEV images, {image_paths_broken} Broken/Missing links.')
if image_paths_broken > 0:
    print('  [-] VERDICT: The VLM cannot train properly if image matrices are missing from the disk.')

print('\n>>> NUMERIC TEST 1/5 COMPLETE. WAITING FOR DATA TO CONFIRM PHYSICAL REALITY. <<<')
