import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (2/10): DATA SHUFFLE & SMOOTHING TRACING <<<')

target_agents = ['vla_dataset_builder.py', 'qwen_dataset_formatter.py', 'session_worthiness_analyzer.py']

# 1. HUNTING THE TEMPORAL TEAR (Unsorted File Iteration)
print('\n[1/2] HUNTING TEMPORAL CHAOS (Scanning for unsorted os.listdir/glob):')
temporal_flaw_found = False
for agent in target_agents:
    agent_path = os.path.join(AGENTS_DIR, agent)
    if os.path.exists(agent_path):
        with open(agent_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Search for directory listing without sorting
                if ('os.listdir' in line or 'glob.glob' in line) and 'sorted' not in line:
                    print(f'  [!] FATAL TEMPORAL FLAW in {agent} at Line {i+1}:')
                    print(f'      -> Code: {line.strip()}')
                    print(f'      -> Diagnosis: Files are read in arbitrary OS hash order, causing the 274 frame jumps!')
                    temporal_flaw_found = True
                
                # Check if intentional shuffle is applied before training
                if 'random.shuffle' in line:
                    print(f'  [!] INTENTIONAL SHUFFLE found in {agent} at Line {i+1}:')
                    print(f'      -> Code: {line.strip()}')
                    print(f'      -> Diagnosis: Shuffling destroys temporal sequence needed for continuous VLA tracking.')
                    temporal_flaw_found = True

if not temporal_flaw_found:
    print('  [*] No glaring unsorted listdir found. The shuffle might happen inside JSON encoding/dumping.')

# 2. HUNTING THE KINEMATIC JERK (Absence of Low-Pass/Smoothing Filters)
print('\n[2/2] HUNTING KINEMATIC JERK (Checking Action Assignment Logic):')
for agent in target_agents:
    agent_path = os.path.join(AGENTS_DIR, agent)
    if os.path.exists(agent_path):
        with open(agent_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            
            if 'ground_truth_action' in content:
                print(f'\n  [*] Analyzing Action Assignment in {agent}:')
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'ground_truth_action' in line:
                        print(f'      -> Line {i+1}: {line.strip()}')
                
                # Check for smoothing algorithms
                if 'smooth' not in content.lower() and 'filter' not in content.lower() and 'ema' not in content.lower():
                    print(f'  [-] CRITICAL: No mathematical smoothing (EMA, Low-pass) found in {agent}.')
                    print(f'      -> Diagnosis: Raw joystick/teleop data is directly injected, causing infinite Jerk (92 anomalies).')

print('\n>>> PROBE 2/10 COMPLETE. WAITING FOR EXACT LINE NUMBERS TO TARGET IN SURGERY. <<<')
