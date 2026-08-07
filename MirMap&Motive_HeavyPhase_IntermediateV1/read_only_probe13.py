import os
import sys
import hashlib

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 13: BACKUP INTEGRITY & FALLBACK LOGIC AUDIT <<<')

# 1. Verify A18 Backup Integrity (The Safety Net)
print('\n[1/2] A18 BACKUP INTEGRITY CHECK (Target MD5 starts with 67e80f1e):')
backup_dir = os.path.join(PROJECT_ROOT, 'backups', 'A18_deep_agent_verifier')
if os.path.exists(backup_dir):
    files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
    print(f'  [+] Found {len(files)} files in A18 backup directory.')
    target_found = False
    for f in files:
        if 'pre_r35_10_targeted_patch' in f:
            target_found = True
            f_path = os.path.join(backup_dir, f)
            with open(f_path, 'rb') as file:
                md5 = hashlib.md5(file.read()).hexdigest()
            print(f'  [+] Target Backup Found: {f}')
            print(f'  [+] MD5 Hash: {md5}')
            if md5.startswith('67e80f1e'):
                print('      -> EXACT MATCH with Dossier v22 (Rollback is 100% safe).')
            else:
                print('      -> [-] MD5 MISMATCH!')
    if not target_found:
        print('  [-] Target backup pre_r35_10_targeted_patch NOT FOUND.')
else:
    print('  [-] Backup directory NOT FOUND.')

# 2. Extract Fallback Logic from live A18
print('\n[2/2] A18 OPENROUTER FALLBACK LOGIC INSPECTION:')
a18_path = os.path.join(PROJECT_ROOT, 'agents', 'A18_deep_agent_verifier.py')
if os.path.exists(a18_path):
    with open(a18_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if 'def call_openrouter_fallback' in line or 'def call_fallback' in line:
                print(f'  [+] Found fallback definition at Line {i+1}: {line.strip()}')
                for j in range(1, 4):
                    if i+j < len(lines):
                        print(f'      {lines[i+j].rstrip()}')
else:
    print('  [-] A18_deep_agent_verifier.py NOT FOUND.')

print('\n>>> ROUND 13 SCAN COMPLETE <<<')
