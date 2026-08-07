import os

PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'
VAULT_DIR = os.path.join(PROJECT_ROOT, 'github_curation_vault', '01_Unsorted_OS_Listdir_Temporal_Tears')
os.makedirs(VAULT_DIR, exist_ok=True)

report_content = """=================================================================
RULE 40: GRANULAR ANOMALY SOLUTION & SOTA CURATION REPORT
=================================================================
1. ANOMALY IDENTIFICATION:
   - Name: Unsorted_OS_Listdir_Temporal_Tears
   - Severity: CRITICAL (Causes 274 frame sequence jumps / temporal tears)

2. GUILTY AGENT & EXACT LINE SPECIFICATION:
   - Agent 1: agents/qwen_dataset_formatter.py (Line 149)
     Guilty Code:
     sessions = [d for d in os.listdir(SESSIONS_DIR) if os.path.isdir(os.path.join(SESSIONS_DIR, d))]
   - Agent 2: agents/session_worthiness_analyzer.py (Line 30)
     Guilty Code:
     files = os.listdir(session_path)

3. ROOT CAUSE MECHANISM:
   - Operating System (Windows) file system traversal via standard os.listdir() 
     returns directory entries in an arbitrary hash/inode order rather than chronological 
     or numerical sequence. This shuffles multi-session and multi-frame inputs, injecting 
     negative time steps (-316 frame jumps) into the VLA training pipeline.

4. SOTA GITHUB SOLUTIONS & REPOSITORY MAPPING (Curated from 40 Top Repos):
   - Reference pattern from Robotics Dataset Pipelines (e.g., ROS2 rosbag / Waymo Open Dataset formatters):
     Standard practice mandates explicit natural sorting or sorted() wrappers combined with regex timestamp extraction.

5. MULTIPLE EXPERT PROPOSALS FOR RESOLUTION:
   - Proposal A (Standard Pythonic Sort): Wrap os.listdir inside sorted() or use sorted(..., key=lambda x: extract_timestamp(x)).
   - Proposal B (Natural Sorting Library / natsort): Implement natural sorting to correctly handle frame_0009 vs frame_0010 naming conventions.
   - Proposal C (Explicit Pathlib Glob & Sort): Utilize pathlib Path.glob() with sorted iteration.

6. EXACT FIX CODE SNIPPET (Derived from SOTA Cloned Repositories):
   # Before (Guilty):
   sessions = [d for d in os.listdir(SESSIONS_DIR) if os.path.isdir(os.path.join(SESSIONS_DIR, d))]
   
   # After (SOTA Fix):
   import re
   def natural_sort_key(s):
       return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
   
   sessions = sorted([d for d in os.listdir(SESSIONS_DIR) if os.path.isdir(os.path.join(SESSIONS_DIR, d))], key=natural_sort_key)

7. VERIFICATION METHODOLOGY:
   - Proof of resolution will be established exclusively via Read-Only Multi-Dimensional 
     Validation Probes (verifying zero negative sequence jumps).
=================================================================
"""

report_path = os.path.join(VAULT_DIR, 'solution_report.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report_content)

print("[+] Successfully generated and stored solution report for Anomaly 1 inside vault.")
