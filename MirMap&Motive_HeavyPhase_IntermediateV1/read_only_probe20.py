import os
import sys
import ast

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIMENSIONAL DEEP PIPELINE & FLOWCHART AUDIT <<<')

def analyze_python_file(filepath, keywords):
    """Reads a python file and looks for specific logic markers without executing it."""
    if not os.path.exists(filepath):
        return 'MISSING'
    
    found_markers = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            for kw in keywords:
                if kw in content:
                    found_markers.append(kw)
        return found_markers if found_markers else 'NO_MARKERS_FOUND'
    except Exception as e:
        return f'ERROR: {e}'

# 1. THE PAST (Data Acquisition & Sensor Fusion)
print('\n[1/4] ANALYZING THE PAST (Foundation & Data Pipeline):')
agents_dir = os.path.join(PROJECT_ROOT, 'agents')
past_files = {
    'slam_to_bev.py': ['cv2.warpAffine', '1988', '1056', 'np.array'],
    'NatNetClient.py': ['socket', 'multicast', 'unpack'],
    'vla_dataset_builder.py': ['V_MAX', 'W_MAX', 'np.clip']
}
for fname, markers in past_files.items():
    res = analyze_python_file(os.path.join(agents_dir, fname), markers)
    print(f'  -> {fname}: Evidence found -> {res}')

# 2. THE PRESENT (Orchestration & Verification State)
print('\n[2/4] ANALYZING THE PRESENT (Orchestration & AI Logic):')
present_files = {
    'launch_session.py': ['subprocess.Popen', 'roslaunch', 'subscribe_and_run', 'run_ai_advisor'],
    'A18_deep_agent_verifier.py': ['gemini-2.5-flash', 'openrouter.ai', 'localhost:1234', 'requests.post', 'LMStudio']
}
for fname, markers in present_files.items():
    res = analyze_python_file(os.path.join(agents_dir, fname), markers)
    print(f'  -> {fname}: Evidence found -> {res}')

# 3. THE FUTURE (Dataset readiness & VLA Training)
print('\n[3/4] ANALYZING THE FUTURE (Training Readiness):')
dataset_dir = os.path.join(PROJECT_ROOT, 'dataset')
if os.path.exists(dataset_dir):
    for jfile in ['train.jsonl', 'val.jsonl']:
        jp = os.path.join(dataset_dir, jfile)
        if os.path.exists(jp):
            with open(jp, 'r', encoding='utf-8') as f:
                lines = sum(1 for line in f)
            print(f'  -> {jfile}: Contains {lines} data samples.')
        else:
            print(f'  -> {jfile}: MISSING')
else:
    print('  -> dataset directory: MISSING')

train_res = analyze_python_file(os.path.join(PROJECT_ROOT, 'train_qwen_vla.py'), ['PeftModel', 'LoraConfig', 'qwen3_vla_mir100_lora'])
print(f'  -> train_qwen_vla.py logic: {train_res}')

# 4. ARCHITECTURAL SANITY (Detecting what we are ACTUALLY controlling)
print('\n[4/4] CROSS-CHECKING ROBOT TARGETS:')
mir_count = 0
ur_count = 0
for root, _, files in os.walk(agents_dir):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read().lower()
                if 'mir100' in content or 'cmd_vel' in content: mir_count += 1
                if 'ur_rtde' in content or 'universal robot' in content: ur_count += 1
print(f'  -> MiR100/Mobile Base mentions across all agents: Found in {mir_count} files.')
print(f'  -> UR Arm/Manipulator mentions across all agents: Found in {ur_count} files.')

print('\n>>> 400-DIMENSIONAL AUDIT COMPLETE. WAITING FOR FLOWCHART CONSTRUCTION. <<<')
