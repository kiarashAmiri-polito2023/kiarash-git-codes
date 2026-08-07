import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (5/10): PROMPT ARRAY & DATA FORMATTING SCAN <<<')

formatter_path = os.path.join(AGENTS_DIR, 'qwen_dataset_formatter.py')
if os.path.exists(formatter_path):
    with open(formatter_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        
        # Extract PROMPTS array definition using regex
        match = re.search(r'PROMPTS\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            prompts_block = match.group(1)
            # Count string literals inside the block
            prompts_list = re.findall(r'["\'](.*?)["\']', prompts_block)
            print(f'  [+] Found PROMPTS array containing {len(prompts_list)} static template strings.')
            print('  [+] Sample templates currently used in training:')
            for idx, p in enumerate(prompts_list[:3]):
                print(f'      [{idx+1}] "{p}"')
        else:
            print('  [-] PROMPTS array not found in expected format.')

print('\n>>> PROBE 5/10 COMPLETE. READY FOR PROBE 6/10. <<<')
