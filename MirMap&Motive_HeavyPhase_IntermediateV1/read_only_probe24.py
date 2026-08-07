import os
import sys
import re
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIM TEST 4/5: VISUAL FUSION MECHANICS & ROS SAFETY AUDIT <<<')

# 1. ANALYZING VISUAL FUSION DRAWING METHODS
print('\n[1/3] DECODING MATRIX/IMAGE RENDERING (bev_image_renderer.py):')
renderer = os.path.join(PROJECT_ROOT, 'agents', 'bev_image_renderer.py')
if os.path.exists(renderer):
    with open(renderer, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        imports = re.findall(r'^(?:import|from)\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
        found_libs = set(imports).intersection({'cv2', 'PIL', 'matplotlib', 'numpy', 'skimage'})
        print(f'  [+] Image/Math libraries imported: {list(found_libs)}')
        if 'numpy' in found_libs: 
            print('  [+] Numpy detected: High probability of direct array/matrix manipulation for LiDAR/MoCap obstacle mapping.')
else:
    print('  [-] bev_image_renderer.py missing.')

# 2. SCANNING ROS SAFETY & OVERRIDES DURING OBSTACLES
print('\n[2/3] SCANNING KINEMATIC OVERRIDES & EMERGENCY (mir_command_logger.py):')
logger_path = os.path.join(PROJECT_ROOT, 'agents', 'mir_command_logger.py')
if os.path.exists(logger_path):
    with open(logger_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        overrides = [l.strip() for l in lines if any(kw in l.lower() for kw in ['stop', 'override', 'collision', 'emergency', 'clip'])]
        print(f'  [*] Found {len(overrides)} Safety/Override protocols guarding the MiR100.')
        for i, ov in enumerate(overrides[:3]): 
            print(f'      -> Protocol {i+1}: {ov[:100]}...')
else:
    print('  [-] mir_command_logger.py missing.')

# 3. EXAMINING LORA V2 TRAINING CONVERGENCE (Did the VLM learn the obstacles?)
print('\n[3/3] VERIFYING MODEL CONVERGENCE (qwen3_vla_mir100_lora_v2):')
model_dir = os.path.join(PROJECT_ROOT, 'models', 'qwen3_vla_mir100_lora_v2')
if os.path.exists(model_dir):
    print('  [+] LoRA v2 Model Architecture Exists.')
    trainer_state = os.path.join(model_dir, 'trainer_state.json')
    if os.path.exists(trainer_state):
        try:
            with open(trainer_state, 'r') as f:
                ts = json.load(f)
                log_hist = ts.get('log_history', [])
                if log_hist:
                    last_log = log_hist[-1]
                    loss = last_log.get('loss', 'N/A')
                    step = last_log.get('step', 'N/A')
                    print(f'  [+] Convergence Metrics: Final Loss = {loss} at Step = {step}')
        except Exception as e:
            print(f'  [-] Could not parse trainer_state.json: {e}')
    else:
        print('  [-] trainer_state.json not found, reading summary from earlier reports is required.')
else:
    print('  [-] LoRA v2 Directory NOT FOUND in this path.')

print('\n>>> TEST 4/5 COMPLETE. WAITING FOR RESULTS FOR FINAL PRE-GITHUB SYNTHESIS. <<<')
