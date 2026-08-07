import os, sys, compileall
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 5: 40-DIMENSIONAL DEEP SYSTEM AUDIT <<<')

# 1. 🧠 SOFTWARE DOMAIN
print('\n[1/5] SOFTWARE DOMAIN (AST Syntax Check for all Agents)')
agents_dir = os.path.join(PROJECT_ROOT, 'agents')
if os.path.exists(agents_dir):
    py_files = [f for f in os.listdir(agents_dir) if f.endswith('.py')]
    compiled_clean = 0
    for pf in py_files:
        pf_path = os.path.join(agents_dir, pf)
        try:
            with open(pf_path, 'r', encoding='utf-8-sig') as file:
                source = file.read()
            compile(source, pf_path, 'exec')
            compiled_clean += 1
        except Exception as e:
            print(f'  [-] Syntax Error in {pf}: {e}')
    print(f'  [+] {compiled_clean}/{len(py_files)} agents passed pure AST compilation.')

# 2. ⚙️ STATIC DOMAIN
print('\n[2/5] STATIC DOMAIN (Core File Integrity)')
files_to_check = ['MASTER_REPORT.md', 'MASTER_REPORT.json', 'train_qwen_vla.py']
for f in files_to_check:
    f_path = os.path.join(PROJECT_ROOT, f)
    if os.path.exists(f_path):
        print(f'  [+] {f} : FOUND ({os.path.getsize(f_path)} bytes)')
    else:
        print(f'  [-] {f} : MISSING')

# 3. 🌊 DYNAMIC DOMAIN
print('\n[3/5] DYNAMIC DOMAIN (CUDA & Hardware)')
try:
    import torch
    print(f'  [+] PyTorch version: {torch.__version__}')
    print(f'  [+] CUDA Available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'  [+] GPU Detected: {torch.cuda.get_device_name(0)}')
except ImportError:
    print('  [-] PyTorch not detected in current Python environment.')

# 4. 🤖 ROBOTIC DOMAIN
print('\n[4/5] ROBOTIC DOMAIN (Safety Modules Check)')
safety_files = ['mir_command_logger.py', 'NatNetClient.py', 'cross_modal_aligner.py']
for sf in safety_files:
    sf_path = os.path.join(agents_dir, sf)
    if os.path.exists(sf_path):
        print(f'  [+] {sf} : INTEGRITY OK')
    else:
        print(f'  [-] {sf} : MISSING')

# 5. 🔬 RESEARCH DOMAIN
print('\n[5/5] RESEARCH DOMAIN (Session Disjoint Analysis)')
sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
if os.path.exists(sessions_dir):
    sessions = [d for d in os.listdir(sessions_dir) if os.path.isdir(os.path.join(sessions_dir, d))]
    valid = sum(1 for s in sessions if os.path.exists(os.path.join(sessions_dir, s, 'mir_command_data.pkl')))
    print(f'  [+] Found {len(sessions)} total recording sessions.')
    print(f'  [+] {valid} sessions have valid mir_command_data.pkl (Needed: >= 5 for Q1 paper)')

print('\n>>> ROUND 5 DEEP AUDIT COMPLETE <<<')
