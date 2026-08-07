# -*- coding: utf-8 -*-
import os
import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
AGENTS_DIR = PROJECT_ROOT / "agents"
SECRETS_DIR = PROJECT_ROOT / ".secrets"

sys.path.insert(0, str(AGENTS_DIR))

try:
    import A18_deep_agent_verifier as a18
except Exception as e:
    print(f"FATAL: Cannot import A18: {e}")
    sys.exit(1)

print("=" * 75)
print("R38.5 LIVE QUORUM SMOKE TEST - A18")
print("=" * 75)

g_key = ""
or_key = ""
g_key_path = SECRETS_DIR / "gemini.key"
or_key_path = SECRETS_DIR / "openrouter.key"

if g_key_path.is_file():
    with open(g_key_path, "r", encoding="utf-8") as f:
        g_key = f.read().strip()
if or_key_path.is_file():
    with open(or_key_path, "r", encoding="utf-8") as f:
        or_key = f.read().strip()

print(f"Gemini Key present:     {bool(g_key)}")
print(f"OpenRouter Key present: {bool(or_key)}")
print()

SAMPLE_CODE = """
import numpy as np
def project_lidar_to_bev(points, grid_size=0.05):
    grid = np.zeros((400, 400), dtype=np.uint8)
    return grid
"""

REF_PROMPT = f"You are a robotics code auditor. Evaluate sample_test.py with code:\n{SAMPLE_CODE}\nReturn strictly valid JSON in format: {{\n  \"verdict\": \"PASS\",\n  \"confidence\": 95,\n  \"rationale\": \"explanation\",\n  \"research_impact\": \"impact\"\n}}"

print("-" * 75)
print("PROBE 1: Testing LMStudio Local (qwen3.5-9b)")
print("-" * 75)
t0 = time.time()
lm_raw = a18.query_lmstudio("qwen3.5-9b", REF_PROMPT)
dt_lm = time.time() - t0

if lm_raw:
    print(f"  [HTTP 200 OK] Response time: {dt_lm:.2f}s")
    lm_parsed = a18.extract_json(lm_raw)
    if lm_parsed and "verdict" in lm_parsed:
        print(f"  [PARSER PASS] Parsed Verdict: {lm_parsed.get('verdict')} | Confidence: {lm_parsed.get('confidence')}%")
    else:
        print(f"  [PARSER FAIL] JSON error or thinking leak. Raw: {repr(lm_raw[:150])}")
else:
    print(f"  [FAIL] LMStudio timeout or connection refused (Time: {dt_lm:.2f}s)")

print()
print("-" * 75)
print("PROBE 2: Testing Gemini Robotics-ER")
print("-" * 75)
t0 = time.time()
g_raw = a18.query_gemini("gemini-robotics-er-2-preview", REF_PROMPT, g_key, use_json_mode=False)
dt_g = time.time() - t0

if g_raw:
    print(f"  [HTTP 200 OK] Response time: {dt_g:.2f}s")
    g_parsed = a18.extract_json(g_raw)
    if g_parsed and "verdict" in g_parsed:
        print(f"  [PARSER PASS] Parsed Verdict: {g_parsed.get('verdict')} | Confidence: {g_parsed.get('confidence')}%")
    else:
        print(f"  [PARSER FAIL] Parsed: {g_parsed}")
else:
    print(f"  [WARN] Gemini failed (503 or network) - Time: {dt_g:.2f}s")

print()
print("-" * 75)
print("PROBE 3: Testing Nemotron")
print("-" * 75)
t0 = time.time()
or_raw = a18.query_openrouter("nvidia/nemotron-3.5-lightning:free", REF_PROMPT, or_key)
dt_or = time.time() - t0

if or_raw:
    print(f"  [HTTP 200 OK] Response time: {dt_or:.2f}s")
    or_parsed = a18.extract_json(or_raw)
    if or_parsed and "verdict" in or_parsed:
        print(f"  [PARSER PASS] Parsed Verdict: {or_parsed.get('verdict')} | Confidence: {or_parsed.get('confidence')}%")
    else:
        print(f"  [PARSER FAIL] Parsed: {or_parsed}")
else:
    print(f"  [WARN] OpenRouter Nemotron failed - Time: {dt_or:.2f}s")

print()
print("=" * 75)
print("PROBE 4: Full End-to-End A18.analyze_agent Quorum Test (slam_to_bev.py)")
print("=" * 75)
target_agent = AGENTS_DIR / "slam_to_bev.py"
if target_agent.is_file():
    with open(target_agent, "r", encoding="utf-8-sig", errors="replace") as f:
        code_content = f.read()
    
    t0 = time.time()
    verdict_data = a18.analyze_agent("slam_to_bev.py", code_content, g_key, or_key)
    dt_total = time.time() - t0
    
    print(f"Total Verification Time: {dt_total:.2f}s")
    print(f"Consensus Verdict:      {verdict_data.get('verdict')}")
    print(f"Consensus Confidence:   {verdict_data.get('confidence')}%")
    print(f"Votes Breakdown:        {verdict_data.get('votes')}")
    print(f"Panel Status:           {verdict_data.get('panel')}")
    print(f"Rationale:              {verdict_data.get('rationale')}")
    
    print()
    if verdict_data.get("verdict") in ["PASS", "WARN", "FAIL"] and verdict_data.get("verdict") != "INSUFFICIENT_QUORUM":
        print(">>> SUCCESS: QUORUM ACHIEVED! BUG-AR AND BUG-BV RESOLVED! <<<")
    else:
        print(">>> FAIL: Still INSUFFICIENT_QUORUM! <<<")
else:
    print(f"Target agent {target_agent} not found.")

print("=" * 75)