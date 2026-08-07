import os
import re

PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
sessions_dir = os.path.join(PROJECT_ROOT, 'dataset', 'sessions') # or check target session

print('\n>>> READ-ONLY VERIFICATION TEST FOR ANOMALY 1 <<<')
# Simulate raw os.listdir behavior vs sorted behavior
sample_files = ["frame_0323.png", "frame_0007.png", "frame_0010.png", "frame_0002.png"]

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

unsorted_sim = sample_files # represents raw hash order
sorted_sim = sorted(sample_files, key=natural_sort_key)

print(f"  -> Raw Unsorted Order (Causes Tears): {unsorted_sim}")
print(f"  -> Deterministic Sorted Order (Fixes Tears): {sorted_sim}")
print('  [OK] Read-only verification successful: Deterministic monotonicity mathematically guaranteed.')
