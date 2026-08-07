import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN NUMERIC/VISION AUDIT 3/5: PIXEL MATRIX & BEV RESOLUTION <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
sample_img_path = None

# Extract the very first valid image path from dataset
try:
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data.get('image'):
                sample_img_path = data.get('image')
                if not os.path.isabs(sample_img_path):
                    sample_img_path = os.path.join(PROJECT_ROOT, sample_img_path)
                break
except Exception as e:
    print(f'[-] Error parsing JSON: {e}')

if sample_img_path and os.path.exists(sample_img_path):
    print(f'  [+] Target BEV Image: {os.path.basename(sample_img_path)}')
    try:
        from PIL import Image
        import numpy as np
        
        # Load image into RAM directly as a raw Matrix
        img = Image.open(sample_img_path)
        img_arr = np.array(img)
        
        print(f'\n[1/2] MATRIX DIMENSION & TENSOR SHAPE:')
        print(f'  -> Array Shape: {img_arr.shape} (Height x Width x Channels)')
        print(f'  -> Data Type: {img_arr.dtype}')
        
        if len(img_arr.shape) == 3 and img_arr.shape[2] >= 3:
            print('\n[2/2] PIXEL DENSITY & OBSTACLE SIGNATURES (Channel Analysis):')
            r, g, b = img_arr[:,:,0], img_arr[:,:,1], img_arr[:,:,2]
            
            print(f'  -> Red Channel (Mean Activation): {r.mean():.2f} (Min:{r.min()}, Max:{r.max()})')
            print(f'  -> Green Channel (Mean Activation): {g.mean():.2f} (Min:{g.min()}, Max:{g.max()})')
            print(f'  -> Blue Channel (Mean Activation): {b.mean():.2f} (Min:{b.min()}, Max:{b.max()})')
            
            # Check unique color clusters (determines if LiDAR and MoCap use distinct visual markers)
            unique_colors = len(np.unique(img_arr.reshape(-1, img_arr.shape[2]), axis=0))
            print(f'  -> Unique Color Signatures: {unique_colors} (Complexity of the spatial map)')
            
            if unique_colors < 10:
                print('  [!] WARNING: Very low color variance. BEV might be too simplistic (e.g., purely binary black/white).')
            else:
                print('  [+] VERDICT: Rich visual matrix confirmed. VLM has multi-channel spatial data to distinguish sensor sources.')
        else:
            print('  [-] Matrix is NOT standard RGB. VLM needs explicit prompt instructions to decode this shape.')
            
    except ImportError:
        print('  [-] CRITICAL: Python PIL/numpy packages failed to load in this terminal session.')
else:
    print('  [-] Could not locate the actual image file on disk to extract matrix data.')

print('\n>>> NUMERIC TEST 3/5 COMPLETE. WAITING FOR TENSOR RESULTS. <<<')
