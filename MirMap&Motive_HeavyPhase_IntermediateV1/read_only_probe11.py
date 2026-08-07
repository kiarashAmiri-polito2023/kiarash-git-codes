import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 11: GLOBAL VIDEO SEARCH & MODEL WEIGHTS AUDIT <<<')

# 1. Global Search for Missing Video Files
print('\n[1/2] HUNTING FOR MISSING VIDEO FILES (8 AVI files claimed in Dossier):')
video_count = 0
for root, dirs, files in os.walk(PROJECT_ROOT):
    vids = [f for f in files if f.lower().endswith(('.avi', '.mp4'))]
    if vids:
        rel_path = os.path.relpath(root, PROJECT_ROOT)
        print(f'  [+] Found {len(vids)} videos in: {rel_path} (e.g., {vids[0]})')
        video_count += len(vids)

if video_count == 0:
    print('  [-] 0 videos found in the entire project root. The AVI files are MISSING or moved.')
else:
    print(f'  [+] Total videos found across project: {video_count}')

# 2. Audit Qwen3-VL LoRA Weights
print('\n[2/2] AUDITING QWEN3-VL LORA WEIGHTS DIRECTORIES:')
models_dir = os.path.join(PROJECT_ROOT, 'models')
if os.path.exists(models_dir):
    for lora_folder in ['qwen3_vla_mir100_lora', 'qwen3_vla_mir100_lora_v2']:
        target = os.path.join(models_dir, lora_folder)
        if os.path.exists(target):
            safetensors = [f for f in os.listdir(target) if f.endswith('.safetensors') or f.endswith('.bin')]
            if safetensors:
                print(f'  [+] {lora_folder}: FOUND (Contains {len(safetensors)} weight files)')
            else:
                print(f'  [-] {lora_folder}: EXISTS but NO WEIGHT FILES (.safetensors/.bin) FOUND!')
        else:
            print(f'  [-] {lora_folder}: FOLDER MISSING!')
else:
    print('  [-] models directory NOT FOUND.')

print('\n>>> ROUND 11 SCAN COMPLETE <<<')
