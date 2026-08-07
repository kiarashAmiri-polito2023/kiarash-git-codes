import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
AGENTS_DIR = os.path.join(PROJECT_ROOT, 'agents')

print('\n>>> BEGIN 100x PRECISION FORENSIC PROBE (6/10): GLOBAL PROMPT SOURCE TRACING <<<')

found_sources = 0
for file in os.listdir(AGENTS_DIR):
    if file.endswith('.py'):
        path = os.path.join(AGENTS_DIR, file)
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
                if 'PROMPTS' in content or 'instruction' in content.lower() or 'system_prompt' in content.lower():
                    # Check if it defines actual text lists
                    if '[' in content and ']' in content and ('navigation' in content.lower() or 'robot' in content.lower()):
                        print(f'  [+] Potential Prompt Source Found in: {file}')
                        # Print matching lines
                        for line in content.split('\n'):
                            if any(kw in line.lower() for kw in ['prompt', 'instruction', 'template']) and len(line.strip()) > 10:
                                print(f'      -> {line.strip()[:100]}')
                        found_sources += 1
        except: pass

if found_sources == 0:
    print('  [-] No explicit prompt arrays found in any agent. Prompts might be entirely hidden inside JSON dataset generation or external LLM calls.')

print('\n>>> PROBE 6/10 COMPLETE. READY FOR PROBE 7/10. <<<')
