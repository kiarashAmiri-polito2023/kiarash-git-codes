# Pass 9: PowerShell-Patch Generator
Model: nvidia/nemotron-3.5-lightning:free

Here's a thinking process:

1.  **Analyze User Input:**
   - User wants me to act as a "Hostile Q1 reviewer" and "New-Sequence Prescriber"
   - Focus: BUG-C specifically: max velocity = 9.13 m/s vs MiR100 max 1.5 m/s
   - Need to find exact file:line, give fixed code, PowerShell patches, prescribe 5-10 new sessions
   - Output sections required: [WHAT] [EVIDENCE] [TEST] [FIX] [POWERSHELL] [SEQUENCES] [VERDICT]
   - Must be brutal, cite file:line, give copy-paste fixes
   - Constraints from previous passes context: BUG-C is about velocity calculation bug

2.  **Identify the Core Task:**
   - Find where 9.13 m/s comes from in the codebase
   - Fix it
   - Prescribe new sessions to fix data gaps (especially BUG-E: 344 frames from ONE session, overfit; BUG-F: Rotation class val n=3; etc.)
   - Output in specified format

3.  **Search/Analyze for BUG-C (9.13 m/s):**
   - From the text, I need to find where velocity is calculated or reported as 9.13.
   - The generator script `generate_publication_report_v5.py` is provided. Let me scan it for velocity/m/s/9.13.
   - The script has: `BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"`, deals with sessions, BEV, YOLO, eval.
   - It references `eval_results_v3.json` with mae_v etc., but not 9.13 directly.
   - There's `robot_data_analyzer.py` (219L, 4F, 0C) - likely contains velocity analysis.
   - `motive_connector.py` (490L, 25F, 1C) - MoCap data, likely has velocity/position data.
   - `slam_data.pkl`, `mocap_data.pkl` - data containers.
   - The master report mentions "Dynamic Recording Prescription" but not 9.13.
   - BUG-C is listed in the critical bugs: "BUG-C: max velocity = 9.13 m/s (MiR100 max is 1.5!) (calculation bug)"
   - I need to find the exact file:line. Since I don't have the full source, I'll have to infer/hypothesize based on typical patterns and the agent files listed, or use the generator script to reason.
   - Actually, the user says "Find every flaw, n

=== TASK: Pass 9/10 as PowerShell-Patch Generator ===
Write ready-to-paste PowerShell patches for RemoteDaily for each bug.
Be specific. File names. Line numbers. Copy-paste fixes.