import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (7/10): DATASET FORMATTER SORTING TRACE <<<')

formatter_path = os.path.join(AGENTS_DIR, 'qwen_dataset_formatter.py')
if os.path.exists(formatter_path):
    with open(formatter_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'os.listdir' in line or 'glob' in line or 'sorted' in line:
                print(f'  [+] Found Directory Listing/Sorting in qwen_dataset_formatter.py at Line {i+1}:')
                print(f'      -> {line.strip()}')

print('\n>>> PROBE 7/10 COMPLETE. READY FOR PROBE 8/10. <<<')
