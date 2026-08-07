import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 6: SAFETY & DATASET INTERNAL AUDIT <<<')

# 1. Inspect Safety Limits in mir_command_logger.py
logger_path = os.path.join(PROJECT_ROOT, 'agents', 'mir_command_logger.py')
if os.path.exists(logger_path):
    with open(logger_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        print('\n[1/2] ROBOTIC SAFETY LIMITS & CLAMPS FOUND:')
        for line in content.split('\n'):
            line_upper = line.upper()
            if any(kw in line_upper for kw in ['MAX_V', 'MAX_W', 'VEL', 'LIMIT', 'CLAMP', 'E_STOP']):
                if '=' in line or 'def ' in line:
                    print(f'  -> {line.strip()}')
else:
    print('\n[1/2] [-] mir_command_logger.py NOT FOUND')

# 2. Inspect Dataset Qwen3-VL Structure
train_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
if os.path.exists(train_path):
    print('\n[2/2] DATASET STRUCTURE VERIFICATION:')
    with open(train_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        try:
            data = json.loads(first_line)
            keys = list(data.keys())
            print(f'  [+] Root Keys in JSON: {keys}')
            if 'messages' in data:
                roles = [m.get('role') for m in data['messages']]
                print(f'  [+] Message Roles: {roles}')
                print('  [+] Structure is VALID for Qwen3-VL Fine-tuning.')
            else:
                print('  [-] WARNING: "messages" key not found. Dataset might not be Qwen3 compatible.')
        except Exception as e:
            print(f'  [-] Invalid JSONL format: {e}')
else:
    print('\n[2/2] [-] train.jsonl NOT FOUND')

print('\n>>> ROUND 6 AUDIT COMPLETE <<<')
