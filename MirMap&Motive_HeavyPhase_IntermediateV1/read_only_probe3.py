import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
file_path = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents\A18_deep_agent_verifier.py'

print('\n>>> BEGIN ROUND 3: EXACT LINE EXTRACTION <<<')
if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        print('--- A18 PROMPT AREA (Lines 110 to 140) ---')
        # چاپ خطوط همراه با شماره خط دقیق
        for i, line in enumerate(lines[110:140], start=111):
            print(f'{i:03d}: {line.rstrip()}')
        print('------------------------------------------')
else:
    print('[-] A18 file not found!')
print('>>> ROUND 3 COMPLETE <<<\n')
