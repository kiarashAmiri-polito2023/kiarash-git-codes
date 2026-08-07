import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 400-DIM TEST 3/5: 20-WAY KINEMATIC & SEMANTIC DATA EXTRACTION <<<')

# 1. DATASET KINEMATIC & PROMPT ANALYSIS (10 Ways of Extraction)
print('\n[1/3] DEEP DATASET KINEMATIC ANALYSIS (train.jsonl):')
train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
v_speeds = []
w_speeds = []
behaviors = {}
prompt_snippets = set()

if os.path.exists(train_json_path):
    with open(train_json_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            try:
                data = json.loads(line)
                # Ext Way 1-2: Extract Kinematic Action limits
                action = data.get('ground_truth_action', [0.0, 0.0])
                v_speeds.append(action[0])
                w_speeds.append(action[1])
                
                # Ext Way 3: Behavior distribution
                b_class = data.get('behavior_class', 'UNKNOWN')
                behaviors[b_class] = behaviors.get(b_class, 0) + 1
                
                # Ext Way 4-5: Semantic Prompt extraction (How is it taught?)
                convs = data.get('conversations', [])
                if convs and len(convs) > 0:
                    text_val = convs[0].get('value', '')
                    # Extract everything after '<image>\n'
                    clean_text = text_val.split('\n', 1)[-1][:80]
                    prompt_snippets.add(clean_text)
            except: pass
            
    print(f'  [+] Total Samples Analyzed: {len(lines)}')
    print(f'  [+] Kinematic Check - V_Linear: Min={min(v_speeds):.2f}, Max={max(v_speeds):.2f} (Target V_MAX=1.5)')
    print(f'  [+] Kinematic Check - W_Angular: Min={min(w_speeds):.2f}, Max={max(w_speeds):.2f} (Target W_MAX=1.0)')
    print(f'  [+] Behavior Classes: {behaviors}')
    print('  [+] Core AI Semantic Prompt Snippets (First 80 chars):')
    for snip in list(prompt_snippets)[:2]:
        print(f'      -> "{snip}..."')
else:
    print('  [-] train.jsonl NOT FOUND.')

# 2. RENDERING LOGIC EXTRACTION (5 Ways of Extraction)
print('\n[2/3] BEV RENDERER LOGIC EXTRACTION (bev_image_renderer.py):')
renderer_path = os.path.join(PROJECT_ROOT, 'agents', 'bev_image_renderer.py')
if os.path.exists(renderer_path):
    with open(renderer_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        # Search for color codes, drawing functions, array manipulation
        draw_funcs = re.findall(r'cv2\.(circle|rectangle|polylines|fillPoly)\(.*?\)', content)
        print(f'  [+] Found {len(draw_funcs)} geometric drawing calls (Visual Fusion Evidence)')
        if 'lidar' in content.lower(): print('  [+] Contains explicit LiDAR rendering logic.')
        if 'motive' in content.lower() or 'optitrack' in content.lower(): print('  [+] Contains explicit MoCap rendering logic.')
else:
    print('  [-] bev_image_renderer.py NOT FOUND.')

# 3. SEMANTIC NARRATOR EXTRACTION (5 Ways of Extraction)
print('\n[3/3] VIDEO NARRATOR LINGUISTIC RULES (video_narrator.py):')
narrator_path = os.path.join(PROJECT_ROOT, 'agents', 'video_narrator.py')
if os.path.exists(narrator_path):
    with open(narrator_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        # Find all hardcoded strings that look like instruction rules
        rules = re.findall(r'instruction\s*=\s*["\'](.*?)["\']', content)
        rules += re.findall(r'instruct\s*=\s*["\'](.*?)["\']', content)
        print(f'  [+] Found {len(rules)} Semantic Rules designed to teach the VLM:')
        for i, rule in enumerate(rules[:3]):
            print(f'      Rule {i+1}: "{rule}"')
else:
    print('  [-] video_narrator.py NOT FOUND.')

print('\n>>> TEST 3/5 COMPLETE. DATA EXTRACTED IN 20 DIMENSIONS. WAITING FOR RESULTS. <<<')
