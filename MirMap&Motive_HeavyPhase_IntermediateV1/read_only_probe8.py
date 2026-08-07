import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 8: GLOBAL KINEMATIC SAFETY SCAN <<<')

agents_dir = os.path.join(PROJECT_ROOT, 'agents')
keywords = ['linear.x', 'angular.z', 'cmd_vel', 'v_max', 'w_max', 'velocity']

if os.path.exists(agents_dir):
    py_files = [f for f in os.listdir(agents_dir) if f.endswith('.py')]
    found_any = False
    
    for pf in py_files:
        pf_path = os.path.join(agents_dir, pf)
        try:
            with open(pf_path, 'r', encoding='utf-8-sig') as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in keywords) and ('def ' in line or '=' in line or 'pub' in line):
                        print(f'  [+] {pf} (Line {i+1}): {line.strip()}')
                        found_any = True
        except Exception as e:
            pass
            
    if not found_any:
        print('  [-] No explicit ROS velocity commands found in the top level definitions.')
else:
    print('  [-] Agents directory not found.')

print('\n>>> ROUND 8 SCAN COMPLETE <<<')
