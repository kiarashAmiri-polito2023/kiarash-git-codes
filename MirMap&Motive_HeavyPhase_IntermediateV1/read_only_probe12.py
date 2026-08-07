import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 12: SECURITY BLIND-CHECK & ORCHESTRATION AUDIT <<<')

# 1. Blind Security Check (Checks existence and size ONLY, NEVER prints contents)
print('\n[1/2] BLIND SECURITY CHECK (API Keys):')
secrets_dir = os.path.join(PROJECT_ROOT, '.secrets')
if os.path.exists(secrets_dir):
    for key_file in ['openrouter.key', 'gemini.key']:
        kp = os.path.join(secrets_dir, key_file)
        if os.path.exists(kp):
            size = os.path.getsize(kp)
            print(f'  [+] {key_file}: SECURELY FOUND (Size: {size} bytes)')
            if key_file == 'openrouter.key' and size == 73:
                print('      -> Size strictly matches Dossier v22')
            elif key_file == 'gemini.key' and size == 53:
                print('      -> Size strictly matches Dossier v22')
        else:
            print(f'  [-] {key_file}: MISSING!')
else:
    print('  [-] .secrets directory NOT FOUND!')

# 2. Orchestration Pipeline Architecture
print('\n[2/2] ORCHESTRATION PIPELINE (launch_session.py structure):')
launch_path = os.path.join(PROJECT_ROOT, 'agents', 'launch_session.py')
if os.path.exists(launch_path):
    with open(launch_path, 'r', encoding='utf-8-sig') as f:
        content = f.readlines()
        funcs = [line.strip() for line in content if line.strip().startswith('def ')]
        print(f'  [+] Discovered {len(funcs)} total functions in launch_session.py')
        print('  [+] Main execution functions:')
        for fn in funcs:
            if any(kw in fn.lower() for kw in ['run', 'main', 'start', 'init', 'launch']):
                print(f'      -> {fn}')
else:
    print('  [-] launch_session.py NOT FOUND!')

print('\n>>> ROUND 12 SCAN COMPLETE <<<')
