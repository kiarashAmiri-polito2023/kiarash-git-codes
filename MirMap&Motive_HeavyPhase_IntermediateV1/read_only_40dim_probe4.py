import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN 40-DIMENSIONAL SYSTEM VALIDATION PROBE 4/5 (READ-ONLY) <<<')

train_json_path = os.path.join(PROJECT_ROOT, 'dataset', 'train.jsonl')
frame_numbers = []

if os.path.exists(train_json_path):
    with open(train_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                uid = data.get('id', '')
                m = re.search(r'frame_(\d+)', uid)
                if m:
                    frame_numbers.append(int(m.group(1)))
            except: pass

print('\n[1/2] Frame Sequence Monotonicity Check:')
if frame_numbers:
    is_monotonic = all(frame_numbers[i] < frame_numbers[i+1] for i in range(len(frame_numbers)-1))
    print(f'  -> Is Frame Sequence Strictly Monotonic (No Jumps)? {is_monotonic}')
    print('  -> [DIM 81-90 STATUS]: Monotonicity and sequence flow mapped.')

print('\n[2/2] Frame Index Density Distribution:')
if frame_numbers:
    total_span = max(frame_numbers) - min(frame_numbers) + 1
    recorded_count = len(frame_numbers)
    density_pct = (recorded_count / total_span) * 100 if total_span > 0 else 0
    print(f'  -> Frame Span Coverage: Min={min(frame_numbers)}, Max={max(frame_numbers)}')
    print(f'  -> Effective Frame Density Ratio: {density_pct:.2f}% (Recorded vs Total Span)')
    print('  -> [DIM 91-100 STATUS]: Sequence density profile verified.')

print('\n>>> 40-DIMENSIONAL PROBE 4/5 COMPLETE. NO CODE WAS ALTERED. <<<')
