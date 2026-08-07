# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import urllib.request
import ssl
from pathlib import Path

# Force unbuffered stdout for immediate output
sys.stdout.reconfigure(line_buffering=True)

PROJECT_ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
AGENTS_DIR = PROJECT_ROOT / "agents"
SECRETS_DIR = PROJECT_ROOT / ".secrets"

sys.path.insert(0, str(AGENTS_DIR))

try:
    import A18_deep_agent_verifier as a18
except Exception as e:
    print(f"FATAL: Cannot import A18: {e}", flush=True)
    sys.exit(1)

print("=" * 70, flush=True)
print("R38.5 FAST LIVE PROBE (10s Hard Timeout per Slot)", flush=True)
print("=" * 70, flush=True)

# Load secrets
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

print(f"[*] Gemini Key loaded:     {bool(g_key)}", flush=True)
print(f"[*] OpenRouter Key loaded: {bool(or_key)}", flush=True)

SAMPLE_PROMPT = 'Return ONLY valid JSON: {"verdict": "PASS", "confidence": 95, "rationale": "ok", "research_impact": "high"}'

# -------------------------------------------------------------
# 1. LMStudio Fast Probe (Port 1234)
# -------------------------------------------------------------
print("\n[1/3] Probing LMStudio (http://localhost:1234/v1/chat/completions)...", flush=True)
t0 = time.time()
try:
    url = "http://localhost:1234/v1/chat/completions"
    payload = {
        "model": "qwen3.5-9b",
        "messages": [{"role": "user", "content": SAMPLE_PROMPT}],
        "temperature": 0.1,
        "max_tokens": 200
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw = res["choices"][0]["message"]["content"]
        dt = time.time() - t0
        print(f"  --> LMStudio SUCCESS ({dt:.2f}s)! Raw: {repr(raw[:60])}", flush=True)
        parsed = a18.extract_json(raw)
        print(f"  --> Parser Result: {parsed}", flush=True)
except Exception as e:
    dt = time.time() - t0
    print(f"  --> LMStudio FAILED/TIMEOUT ({dt:.2f}s): {type(e).__name__}: {str(e)[:60]}", flush=True)

# -------------------------------------------------------------
# 2. Gemini Robotics-ER Fast Probe
# -------------------------------------------------------------
print("\n[2/3] Probing Gemini Robotics-ER API...", flush=True)
t0 = time.time()
try:
    if not g_key:
        print("  --> SKIPPED: gemini.key is empty", flush=True)
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-robotics-er-2-preview:generateContent?key={g_key}"
        payload = {"contents": [{"parts": [{"text": SAMPLE_PROMPT}]}], "generationConfig": {"temperature": 0.1}}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            raw = res["candidates"][0]["content"]["parts"][0]["text"]
            dt = time.time() - t0
            print(f"  --> Gemini SUCCESS ({dt:.2f}s)! Raw: {repr(raw[:60])}", flush=True)
            parsed = a18.extract_json(raw)
            print(f"  --> Parser Result: {parsed}", flush=True)
except Exception as e:
    dt = time.time() - t0
    print(f"  --> Gemini FAILED/TIMEOUT ({dt:.2f}s): {type(e).__name__}: {str(e)[:60]}", flush=True)

# -------------------------------------------------------------
# 3. OpenRouter Nemotron Fast Probe
# -------------------------------------------------------------
print("\n[3/3] Probing OpenRouter Nemotron API...", flush=True)
t0 = time.time()
try:
    if not or_key:
        print("  --> SKIPPED: openrouter.key is empty", flush=True)
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "nvidia/nemotron-3.5-lightning:free",
            "messages": [{"role": "user", "content": SAMPLE_PROMPT}],
            "temperature": 0.1,
            "max_tokens": 200
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {or_key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            raw = res["choices"][0]["message"]["content"]
            dt = time.time() - t0
            print(f"  --> Nemotron SUCCESS ({dt:.2f}s)! Raw: {repr(raw[:60])}", flush=True)
            parsed = a18.extract_json(raw)
            print(f"  --> Parser Result: {parsed}", flush=True)
except Exception as e:
    dt = time.time() - t0
    print(f"  --> Nemotron FAILED/TIMEOUT ({dt:.2f}s): {type(e).__name__}: {str(e)[:60]}", flush=True)

print("\n" + "=" * 70, flush=True)
print("PROBE FINISHED", flush=True)
print("=" * 70, flush=True)