import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 7: TRAINING MAPPER & CORE SAFETY PROBE <<<')

# 1. Check how train_qwen_vla.py handles the dataset keys
train_script = os.path.join(PROJECT_ROOT, 'train_qwen_vla.py')
if os.path.exists(train_script):
    print('\n[1/2] DATASET MAPPING IN train_qwen_vla.py:')
    with open(train_script, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        mapping_found = False
        for i, line in enumerate(lines):
            if 'conversations' in line or 'messages' in line or 'map' in line or 'dataset' in line.lower():
                # Print contextual lines around dataset mapping
                if 'conversations' in line or 'messages' in line:
                    print(f'  Line {i+1}: {line.strip()}')
                    mapping_found = True
        if not mapping_found:
            print('  [-] No explicit key mapping found. Training script might fail with Qwen3 default loader.')
else:
    print('\n[1/2] [-] train_qwen_vla.py NOT FOUND')

# 2. Find real physical safety clamps in aligner/engine
print('\n[2/2] HUNTING FOR PHYSICAL SAFETY CLAMPS:')
target_files = ['agents\\cross_modal_aligner.py', 'agents\\knowledge_engine.py']
for target in target_files:
    path = os.path.join(PROJECT_ROOT, target)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            for i, line in enumerate(f.readlines()):
                line_up = line.upper()
                if any(k in line_up for k in ['CLAMP', 'MAX_V', 'MAX_W', 'VELOCITY_LIMIT']):
                    print(f'  [+] Found in {target} (Line {i+1}): {line.strip()}')
    else:
        print(f'  [-] {target} NOT FOUND')

print('\n>>> ROUND 7 PROBE COMPLETE <<<')
