import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 17: RESEARCH METRICS & EVALUATION AUDIT <<<')

eval_file = os.path.join(PROJECT_ROOT, 'eval_results_v3.json')

if os.path.exists(eval_file):
    print('\n[1/1] EVALUATION METRICS FOUND:')
    try:
        with open(eval_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Extract metrics safely
            loss = data.get('loss', 'N/A')
            mae_v = data.get('MAE_v', 'N/A')
            mae_w = data.get('MAE_w', 'N/A')
            
            print(f'  [+] Recorded Loss: {loss}')
            print(f'  [+] Recorded MAE_v (Linear Velocity Error): {mae_v}')
            print(f'  [+] Recorded MAE_w (Angular Velocity Error): {mae_w}')
            
            if str(loss).startswith('0.085') and str(mae_v).startswith('0.06'):
                print('      -> EXACT MATCH with Dossier v22 Research Claims.')
            else:
                print('      -> [-] METRICS MISMATCH: Data in Dossier might be outdated.')
    except Exception as e:
        print(f'  [-] Error reading JSON file: {e}')
else:
    print('\n[1/1] [-] eval_results_v3.json NOT FOUND. Cannot verify research metrics.')

print('\n>>> ROUND 17 SCAN COMPLETE <<<')
