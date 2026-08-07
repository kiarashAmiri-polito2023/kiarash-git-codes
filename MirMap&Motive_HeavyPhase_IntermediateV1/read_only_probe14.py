import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 14: FALLBACK TRACING & REPORTING AUDIT <<<')

# 1. Trace the exact location of OpenRouter requests in A18
print('\n[1/2] TRACING OPENROUTER FALLBACK LOGIC IN A18:')
a18_path = os.path.join(PROJECT_ROOT, 'agents', 'A18_deep_agent_verifier.py')
if os.path.exists(a18_path):
    with open(a18_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        fallback_lines = []
        for i, line in enumerate(lines):
            if 'openrouter.ai' in line or 'requests.post' in line:
                fallback_lines.append(f'  Line {i+1}: {line.strip()}')
        
        if fallback_lines:
            print('  [+] Found OpenRouter API calls embedded at:')
            for fl in fallback_lines[:3]:  # Print only first 3 to keep it brief
                print(fl)
            print('  [+] Logic is inline (not a separate function).')
        else:
            print('  [-] No OpenRouter logic found via keyword search.')
else:
    print('  [-] A18_deep_agent_verifier.py NOT FOUND.')

# 2. Check the integrity of the generation report script
print('\n[2/2] REPORT GENERATION SCRIPT AUDIT:')
gen_path = os.path.join(PROJECT_ROOT, 'generate_publication_report_v5.py')
if os.path.exists(gen_path):
    with open(gen_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        if 'MASTER_REPORT.md' in content and 'A18' in content:
            print('  [+] generate_publication_report_v5.py is structurally ready to parse A18.')
        else:
            print('  [-] WARNING: Report script might not be linking A18 data correctly.')
else:
    print('  [-] generate_publication_report_v5.py NOT FOUND.')

print('\n>>> ROUND 14 SCAN COMPLETE <<<')
