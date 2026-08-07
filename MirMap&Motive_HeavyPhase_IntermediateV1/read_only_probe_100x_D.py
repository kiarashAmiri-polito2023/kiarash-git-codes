import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (4/10): VARIABLE PIPELINE & NETWORK BUFFER TRACING <<<')

# 1. TRACING THE SOURCE OF 'user_prompt' (To fix Semantic Entropy)
print('\n[1/2] TRACING "user_prompt" PIPELINE (Semantic Traceability):')
formatter_path = os.path.join(AGENTS_DIR, 'qwen_dataset_formatter.py')
if os.path.exists(formatter_path):
    with open(formatter_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        lines = content.split('\n')
        prompt_assignments = []
        for i, line in enumerate(lines):
            if 'user_prompt' in line and '=' in line and '==' not in line:
                prompt_assignments.append(f'Line {i+1}: {line.strip()}')
        
        if prompt_assignments:
            print('  [*] Found origins of the semantic prompt in qwen_dataset_formatter.py:')
            for pa in prompt_assignments: print(f'      -> {pa}')
        else:
            print('  [-] "user_prompt" is passed as an argument. Scanning for its caller...')
            # Simple global regex to find caller
            caller_found = False
            for agent in os.listdir(AGENTS_DIR):
                if agent.endswith('.py') and agent != 'qwen_dataset_formatter.py':
                    with open(os.path.join(AGENTS_DIR, agent), 'r', encoding='utf-8-sig') as af:
                        if 'qwen_dataset_formatter' in af.read() and 'prompt' in af.read().lower():
                            print(f'      -> Likely caller found in: {agent} (Requires parameter trace)')
                            caller_found = True
            if not caller_found: print('      -> Caller dynamically binds prompt from JSON or external file.')

# 2. CHECKING ROSBRIDGE BUFFER & THROTTLE LIMITS (Kinematic Jerk / Latency Source)
print('\n[2/2] TRACING ROSLIBPY BUFFER CONSTRAINTS (Network Bottleneck Check):')
ros_agents = ['launch_session.py', 'mir_command_logger.py']
buffer_flaw = True

for agent in ros_agents:
    path = os.path.join(AGENTS_DIR, agent)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if 'roslibpy.Topic' in line:
                    # Look for explicit queue_size or throttle_rate definitions
                    print(f'  [*] Inspecting ROSBridge Topic at {agent} Line {i+1}:')
                    print(f'      -> {line.strip()}')
                    
                    # Read the next 3 lines in case of multiline arguments
                    full_args = line.strip()
                    for j in range(1, 4):
                        if i+j < len(lines): full_args += ' ' + lines[i+j].strip()
                        
                    if 'queue_size' in full_args or 'queue_length' in full_args or 'throttle_rate' in full_args:
                        print('      -> [OK] Buffer control / Throttle detected! Network choke is mitigated.')
                        buffer_flaw = False
                    else:
                        print('      -> [!] CRITICAL: No queue_size or throttle_rate defined! Websocket buffers will overflow at 100Hz.')

if buffer_flaw:
    print('\n  [!] DIAGNOSIS (Rule 39 Specs):')
    print('      -> Error Name: ROSBridge_Buffer_Overflow')
    print('      -> Location: mir_command_logger.py & launch_session.py (roslibpy.Topic initialization)')
    print('      -> Mechanism: MoCap sends data at 100Hz, WebSocket without queue_size=1 or throttle_rate chokes, causing message batched delivery (Latency -> Jerk).')

print('\n>>> PROBE 4/10 COMPLETE. WAITING FOR RESULTS. <<<')
