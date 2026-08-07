# -*- coding: utf-8 -*-
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
A18_PATH = PROJECT_ROOT / "agents" / "A18_deep_agent_verifier.py"
AGENTS_DIR = PROJECT_ROOT / "agents"

with open(A18_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
    content = f.read()
lines = content.splitlines()

print("=" * 80)
print("R38.2 A18 DEEP ANATOMY DUMP")
print("=" * 80)
print(f"File: {A18_PATH.name}")
print(f"Total lines: {len(lines)}")
print(f"Total chars: {len(content)}")
print()

# ================================================================
# SECTION 1: All Imports (line-numbered)
# ================================================================
print("-" * 80)
print("SECTION 1: IMPORTS")
print("-" * 80)
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("import ") or s.startswith("from "):
        print(f"L{i:4d}: {line}")
print()

# ================================================================
# SECTION 2: All Functions & Classes
# ================================================================
print("-" * 80)
print("SECTION 2: FUNCTIONS & CLASSES")
print("-" * 80)
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("def ") or s.startswith("async def ") or s.startswith("class "):
        indent = len(line) - len(line.lstrip())
        prefix = "  " * (indent // 4)
        print(f"L{i:4d}: {prefix}{s[:100]}")
print()

# ================================================================
# SECTION 3: JSON parsing locations
# ================================================================
print("-" * 80)
print("SECTION 3: JSON PARSING SITES")
print("-" * 80)
for i, line in enumerate(lines, 1):
    if "json.loads" in line or "json.load(" in line:
        # print 2 lines of context before + the line
        start = max(0, i - 3)
        for j in range(start, i):
            print(f"L{j+1:4d}: {lines[j]}")
        print(f"  >>> HIT at L{i}")
        print()

# ================================================================
# SECTION 4: System prompt / role="system" sites
# ================================================================
print("-" * 80)
print("SECTION 4: SYSTEM PROMPT / MESSAGE ROLES")
print("-" * 80)
for i, line in enumerate(lines, 1):
    l = line.lower()
    if ('"role"' in line or "'role'" in line or 
        "system_prompt" in l or "SYSTEM_PROMPT" in line or
        '"system"' in line or "'system'" in line):
        print(f"L{i:4d}: {line[:150]}")
print()

# ================================================================
# SECTION 5: API endpoints / model names
# ================================================================
print("-" * 80)
print("SECTION 5: API / MODEL REFERENCES")
print("-" * 80)
patterns = ["http://", "https://", "openai", "gemini", "nemotron", "flash", 
            "generativelanguage", "openrouter", "1234", "localhost", "127.0.0.1",
            "model=", "'model'", '"model"', "gpt-", "qwen"]
for i, line in enumerate(lines, 1):
    for p in patterns:
        if p in line.lower():
            print(f"L{i:4d}: {line.strip()[:140]}")
            break
print()

# ================================================================
# SECTION 6: First 60 lines (imports + header + config)
# ================================================================
print("-" * 80)
print("SECTION 6: FIRST 60 LINES (HEADER + CONFIG)")
print("-" * 80)
for i, line in enumerate(lines[:60], 1):
    print(f"L{i:4d}: {line}")
print()

# ================================================================
# SECTION 7: Last 40 lines (main / entrypoint)
# ================================================================
print("-" * 80)
print("SECTION 7: LAST 40 LINES (MAIN / ENTRYPOINT)")
print("-" * 80)
start = max(0, len(lines) - 40)
for i, line in enumerate(lines[start:], start + 1):
    print(f"L{i:4d}: {line}")
print()

# ================================================================
# SECTION 8: Which agent depends on A18? (from Q2)
# ================================================================
print("-" * 80)
print("SECTION 8: THE 1 DEPENDENT AGENT")
print("-" * 80)
A18_KW = ["A18", "deep_agent_verifier"]
for py_file in AGENTS_DIR.glob("*.py"):
    if py_file.name == "A18_deep_agent_verifier.py":
        continue
    try:
        with open(py_file, "r", encoding="utf-8-sig", errors="replace") as f:
            c = f.read()
    except:
        continue
    for kw in A18_KW:
        if kw in c:
            print(f"\n>>> Dependent: {py_file.name}")
            for i, line in enumerate(c.splitlines(), 1):
                if kw in line and not line.strip().startswith("#"):
                    print(f"  L{i:4d}: {line.strip()[:130]}")
            break
print()
print("=" * 80)
print("ANATOMY DUMP COMPLETE")
print("=" * 80)