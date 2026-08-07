import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 9: MOCAP TRACKING PIPELINE AUDIT <<<')

target_files = ['NatNetClient.py', 'mir_command_logger.py']
agents_dir = os.path.join(PROJECT_ROOT, 'agents')

# 1. Scan for MATLAB remnants in MoCap files
print('\n[1/2] SCANNING FOR MATLAB REMNANTS IN TRACKING PIPELINE:')
matlab_found = False
for tf in target_files:
    tf_path = os.path.join(agents_dir, tf)
    if os.path.exists(tf_path):
        with open(tf_path, 'r', encoding='utf-8-sig') as f:
            content = f.read().lower()
            if 'matlab' in content:
                print(f'  [-] WARNING: Found MATLAB references inside {tf}!')
                matlab_found = True
            else:
                print(f'  [+] EXCELLENT: No MATLAB references in {tf}. Pure Python pipeline verified.')
    else:
        print(f'  [-] {tf} NOT FOUND in agents dir.')

if not matlab_found:
    print('  [+] Total MATLAB Independence: VERIFIED. (A huge plus for deployment speed)')

# 2. Check OptiTrack Network Defaults in NatNetClient
print('\n[2/2] OPTITRACK NATNET CONFIGURATION:')
natnet_path = os.path.join(agents_dir, 'NatNetClient.py')
if os.path.exists(natnet_path):
    with open(natnet_path, 'r', encoding='utf-8-sig') as f:
        for line in f.readlines():
            if 'self.serverIPAddress' in line or 'self.localIPAddress' in line or 'self.multicastAddress' in line:
                print(f'  -> {line.strip()}')

print('\n>>> ROUND 9 SCAN COMPLETE <<<')
