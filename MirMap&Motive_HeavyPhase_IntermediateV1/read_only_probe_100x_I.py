import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (9/10): COMMAND LOGGER & VELOCITY RECORDING TRACE <<<')

logger_path = os.path.join(AGENTS_DIR, 'mir_command_logger.py')
if os.path.exists(logger_path):
    with open(logger_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        lines = content.split('\n')
        print('  [*] Inspecting velocity recording & loop rate in mir_command_logger.py:')
        for i, line in enumerate(lines):
            if 'rate' in line.lower() or 'sleep' in line.lower() or 'linear' in line.lower() or 'angular' in line.lower():
                if len(line.strip()) > 5:
                    print(f'      Line {i+1}: {line.strip()[:100]}')

print('\n>>> PROBE 9/10 COMPLETE. READY FOR PROBE 10/10. <<<')
