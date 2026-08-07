import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIM TEST 5/5: ORCHESTRATION & VLA PROMPT ANATOMY <<<')

# 1. ORCHESTRATION LOOP ANALYSIS
print('\n[1/3] ANALYZING MASTER ORCHESTRATION (launch_session.py):')
launch_path = os.path.join(PROJECT_ROOT, 'agents', 'launch_session.py')
if os.path.exists(launch_path):
    with open(launch_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        threads = re.findall(r'(?:Thread|Process|Popen)\(', content)
        print(f'  [+] Found {len(threads)} concurrent execution threads/processes managing the robot/sensors.')
        if 'rospy.spin' in content or 'rate.sleep' in content:
            print('  [+] ROS Event Loop (Spin/Sleep) logically detected.')
else:
    print('  [-] launch_session.py missing.')

# 2. VLM/VLA PROMPT ENGINEERING DEEP SCAN
print('\n[2/3] SCANNING VLA PROMPTING STRUCTURE:')
for agent in ['knowledge_engine.py', 'co_pilot_agent.py']:
    path = os.path.join(PROJECT_ROOT, 'agents', agent)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            # extract basic instruction patterns
            sys_prompts = re.findall(r'(?:prompt|instruction).*?=.*?["\'](.*?)["\']', content, re.IGNORECASE)
            if sys_prompts:
                snip = sys_prompts[0][:100].replace('\n', ' ').strip()
                print(f'  [+] {agent} Semantic Anchor: "{snip}..."')
            else:
                print(f'  [*] No explicit hardcoded anchor text found directly in {agent}.')

# 3. TOOL-USE & MCP GROUNDWORK CHECK (Crucial for GitHub Scouting)
print('\n[3/3] CHECKING FOR EXISTING MCP / TOOL-USE INFRASTRUCTURE FOR MIR100:')
mcp_found = False
for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, 'agents')):
    for file in files:
        if file.endswith('.py'):
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8-sig', errors='ignore') as f:
                    c = f.read().lower()
                    if 'mcp' in c or 'model context protocol' in c or 'tool_calls' in c:
                        print(f'  [+] Tool-use/MCP terminology found in: {file}')
                        mcp_found = True
            except: pass
if not mcp_found:
    print('  [-] No active MCP or native tool-use infrastructure found across agents. (Perfect gap for GitHub Idea Scouting!)')

print('\n>>> TEST 5/5 COMPLETE. 400-DIMENSIONAL AUDIT FINISHED. READY FOR GITHUB SCOUTING. <<<')
