import os
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 16: PERCEPTION & SPATIAL MAP AUDIT <<<')

# 1. YOLOv8 Model Weights Check
print('\n[1/2] YOLOv8 OBJECT DETECTOR AUDIT:')
models_dir = os.path.join(PROJECT_ROOT, 'models')
yolo_path = os.path.join(models_dir, 'yolov8s.pt')
if os.path.exists(yolo_path):
    size_mb = os.path.getsize(yolo_path) / (1024**2)
    print(f'  [+] yolov8s.pt: FOUND (Size: {size_mb:.1f} MB)')
else:
    print('  [-] yolov8s.pt: MISSING! Object detection pipeline might fail.')

# 2. BEV Image Dimensionality Check (Target: SLAM map ratio / 1988x1056)
print('\n[2/2] BEV IMAGE DIMENSIONALITY CHECK:')
sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
image_found = False

if os.path.exists(sessions_dir):
    for root, dirs, files in os.walk(sessions_dir):
        images = [f for f in files if f.lower().endswith(('.png', '.jpg'))]
        if images:
            img_path = os.path.join(root, images[0])
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                print(f'  [+] Sample BEV Frame: {images[0]}')
                print(f'  [+] Dimensions: {width}x{height} pixels')
                if width == 1988 and height == 1056:
                    print('      -> EXACT MATCH with Dossier SLAM dimensions.')
                else:
                    print(f'      -> [!] NOTE: Dimensions differ from raw SLAM (1988x1056). Cropped/Resized by script?')
                image_found = True
                break  # Just need one sample
            except Exception as e:
                print(f'  [-] Error reading image: {e}')

if not image_found:
    print('  [-] No BEV images found to analyze dimensions.')

print('\n>>> ROUND 16 SCAN COMPLETE <<<')
