import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (8/10): SESSION INTERLEAVING & LOOP TRACE <<<')

formatter_path = os.path.join(AGENTS_DIR, 'qwen_dataset_formatter.py')
if os.path.exists(formatter_path):
    with open(formatter_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        lines = content.split('\n')
        # Print lines around 145 to 175 to see the session loop structure
        print('  [*] Inspecting Session Loop & JSONL writing logic in qwen_dataset_formatter.py:')
        for i in range(140, min(180, len(lines))):
            print(f'      Line {i+1}: {lines[i]}')

print('\n>>> PROBE 8/10 COMPLETE. READY FOR PROBE 9/10. <<<')
