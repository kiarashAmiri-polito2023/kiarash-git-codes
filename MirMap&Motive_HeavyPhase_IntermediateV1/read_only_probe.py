import os
import sys
import socket
import json
import hashlib

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 2: PYTHON DEEP PROBE <<<')

# 1. A18 PROMPT CHECK
a18_path = os.path.join(PROJECT_ROOT, 'agents', 'A18_deep_agent_verifier.py')
if os.path.exists(a18_path):
    with open(a18_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    if 'Multi-Modal Safety Envelope' in content:
        print('  [+] A18 PROMPT: Enriched (Good - Fixed)')
    elif 'You are an AI safety referee' in content:
        print('  [-] A18 PROMPT: BUG-AV Confirmed (Still old 4% version)')
    else:
        print('  [?] A18 PROMPT: Unknown state')
else:
    print('  [-] A18 file MISSING')

# 2. DATASET SIZE
train_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
if os.path.exists(train_path):
    with open(train_path, 'r', encoding='utf-8') as f:
        print(f'  [+] DATASET: {len(f.readlines())} lines in train.jsonl')
else:
    print('  [-] DATASET: train.jsonl MISSING')

# 3. MIR100 PORT CHECK
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(('192.168.12.20', 9090))
    s.close()
    print('  [+] MiR100 (192.168.12.20:9090): REACHABLE')
except:
    print('  [-] MiR100 (192.168.12.20:9090): UNREACHABLE (BUG-AZ)')

print('>>> ROUND 2 COMPLETE <<<\n')
