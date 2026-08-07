# -*- coding: utf-8 -*-
import os
import sys
import hashlib
import re
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
AGENTS_DIR = PROJECT_ROOT / "agents"
BACKUPS_DIR = PROJECT_ROOT / "backups" / "A18_deep_agent_verifier"
A18_PATH = AGENTS_DIR / "A18_deep_agent_verifier.py"
EXPECTED_A18_MD5 = "c6d4a87ca25d76c8afa3ac9e72aa9591"
TARGET_MODEL_KEYWORDS = ["qwen3.5-9b", "qwen3.5", "qwen-3.5", "qwen_3_5"]
A18_REFERENCE_KEYWORDS = ["A18", "deep_agent_verifier", "A18_deep_agent_verifier"]

OUT = {}

def md5_binary(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        return f"ERROR:{e}"

def read_text_safe(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except Exception as e:
        return None

q1 = {"question": "Does A18 exist with expected MD5?"}
q1["a18_exists"] = A18_PATH.is_file()
q1["a18_size"] = A18_PATH.stat().st_size if q1["a18_exists"] else 0
q1["a18_md5_actual"] = md5_binary(A18_PATH) if q1["a18_exists"] else "N/A"
q1["a18_md5_expected"] = EXPECTED_A18_MD5
q1["a18_md5_match"] = (q1["a18_md5_actual"] == EXPECTED_A18_MD5)
q1["verdict"] = "PASS" if (q1["a18_exists"] and q1["a18_md5_match"]) else "FAIL"
OUT["Q1_existence_first"] = q1

q2 = {"question": "Which agents depend on A18?"}
dependents = []
if AGENTS_DIR.is_dir():
    for py_file in AGENTS_DIR.glob("*.py"):
        if py_file.name == "A18_deep_agent_verifier.py":
            continue
        content = read_text_safe(py_file)
        if content is None:
            continue
        hits = []
        for kw in A18_REFERENCE_KEYWORDS:
            for lineno, line in enumerate(content.splitlines(), 1):
                if kw in line and not line.strip().startswith("#"):
                    hits.append({"line": lineno, "keyword": kw, "text": line.strip()[:120]})
        if hits:
            dependents.append({
                "agent": py_file.name,
                "hit_count": len(hits),
                "samples": hits[:3]
            })
q2["dependent_count"] = len(dependents)
q2["dependents"] = dependents
q2["verdict"] = "INFO"
OUT["Q2_a18_dependents"] = q2

q3 = {"question": "Which agents reference qwen3.5-9b?"}
model_refs = []
if AGENTS_DIR.is_dir():
    for py_file in AGENTS_DIR.glob("*.py"):
        content = read_text_safe(py_file)
        if content is None:
            continue
        hits = []
        content_lower = content.lower()
        for kw in TARGET_MODEL_KEYWORDS:
            if kw in content_lower:
                for lineno, line in enumerate(content.splitlines(), 1):
                    if kw in line.lower():
                        hits.append({"line": lineno, "keyword": kw, "text": line.strip()[:120]})
        if hits:
            model_refs.append({
                "agent": py_file.name,
                "hit_count": len(hits),
                "samples": hits[:3]
            })
q3["ref_count"] = len(model_refs)
q3["references"] = model_refs
q3["verdict"] = "INFO"
OUT["Q3_qwen35_references"] = q3

q4 = {"question": "Is A18 called by launch_session.py orchestrator?"}
launch_path = AGENTS_DIR / "launch_session.py"
q4["launch_exists"] = launch_path.is_file()
if q4["launch_exists"]:
    content = read_text_safe(launch_path)
    hits = []
    for kw in A18_REFERENCE_KEYWORDS:
        for lineno, line in enumerate(content.splitlines(), 1):
            if kw in line:
                hits.append({"line": lineno, "keyword": kw, "text": line.strip()[:150]})
    q4["a18_hits_in_launch"] = len(hits)
    q4["samples"] = hits[:5]
else:
    q4["a18_hits_in_launch"] = 0
    q4["samples"] = []
q4["verdict"] = "INFO"
OUT["Q4_orchestrator_call"] = q4

q5 = {"question": "A18 anatomy for surgery planning"}
if q1["a18_exists"]:
    content = read_text_safe(A18_PATH)
    lines = content.splitlines()
    q5["total_lines"] = len(lines)
    q5["total_chars"] = len(content)
    func_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith("def ") or l.strip().startswith("async def ")]
    q5["function_count"] = len(func_lines)
    q5["functions"] = func_lines
    class_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith("class ")]
    q5["class_count"] = len(class_lines)
    q5["classes"] = class_lines
    import_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith(("import ", "from "))]
    q5["import_count"] = len(import_lines)
    q5["imports"] = import_lines[:30]
    q5["has_system_prompt_var"] = any(kw in content for kw in ["SYSTEM_PROMPT", "system_prompt", '"role": "system"', "'role': 'system'"])
    q5["json_loads_count"] = content.count("json.loads")
    q5["has_find_brace"] = "find('{')" in content or 'find("{")' in content
    q5["has_rfind_brace"] = "rfind('}')" in content or 'rfind("}")' in content
    q5["has_regex_extract"] = "re.search" in content or "re.findall" in content or "re.compile" in content
    q5["has_thinking_keyword"] = any(kw in content.lower() for kw in ["thinking", "<think>", "chain-of-thought", "cot"])
    q5["has_lmstudio_ref"] = "lmstudio" in content.lower() or "localhost:1234" in content or "127.0.0.1:1234" in content
    q5["raw_open_count"] = len(re.findall(r'\bopen\s*\([^)]*\)', content)) - content.count("encoding=")
else:
    q5["error"] = "A18 not found"
q5["verdict"] = "INFO"
OUT["Q5_a18_anatomy"] = q5

q6 = {"question": "Is latest A18 backup available and readable?"}
q6["backup_dir_exists"] = BACKUPS_DIR.is_dir()
if q6["backup_dir_exists"]:
    backups = sorted([p for p in BACKUPS_DIR.iterdir() if p.is_file() and p.suffix == ".py"],
                     key=lambda p: p.stat().st_mtime, reverse=True)
    q6["backup_count"] = len(backups)
    q6["latest_backups"] = []
    for bk in backups[:5]:
        q6["latest_backups"].append({
            "name": bk.name,
            "size": bk.stat().st_size,
            "mtime": datetime.fromtimestamp(bk.stat().st_mtime).isoformat(),
            "md5": md5_binary(bk)
        })
else:
    q6["backup_count"] = 0
    q6["latest_backups"] = []
q6["verdict"] = "PASS" if q6["backup_count"] > 0 else "WARN"
OUT["Q6_backup_integrity"] = q6

q7 = {"question": "Systemic Impact Gate — is surgery safe?"}
critical_deps = q2["dependent_count"]
orchestrator_hits = q4["a18_hits_in_launch"]
model_dependents = q3["ref_count"]
q7["a18_direct_dependents"] = critical_deps
q7["orchestrator_dependency"] = orchestrator_hits
q7["shared_model_agents"] = model_dependents
if critical_deps == 0 and orchestrator_hits == 0:
    q7["impact_level"] = "ISOLATED"
    q7["surgery_safe"] = True
elif critical_deps <= 2 and orchestrator_hits <= 5:
    q7["impact_level"] = "LOW"
    q7["surgery_safe"] = True
elif critical_deps <= 5:
    q7["impact_level"] = "MEDIUM"
    q7["surgery_safe"] = True
else:
    q7["impact_level"] = "HIGH"
    q7["surgery_safe"] = False
q7["verdict"] = "PASS" if q7["surgery_safe"] else "BLOCK"
OUT["Q7_systemic_impact"] = q7

summary = {
    "timestamp": datetime.now().isoformat(),
    "total_questions": 7,
    "verdicts": {k: v["verdict"] for k, v in OUT.items()},
    "critical_flags": []
}
if not q1["a18_md5_match"]:
    summary["critical_flags"].append("A18 MD5 MISMATCH!")
if q6["backup_count"] == 0:
    summary["critical_flags"].append("NO BACKUPS FOUND!")
if not q7["surgery_safe"]:
    summary["critical_flags"].append("Systemic impact blocked!")
OUT["_SUMMARY"] = summary

out_path = PROJECT_ROOT / "R38_1_systemic_impact_report.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=2)

print("=" * 70)
print("R38.1 SYSTEMIC IMPACT DIAGNOSTIC — COMPLETE")
print("=" * 70)
print(f"Report saved: {out_path}")
print()
print("VERDICT SUMMARY:")
for k, v in OUT.items():
    if k == "_SUMMARY":
        continue
    print(f"  {k}: {v['verdict']}")
print()
print(f"A18 MD5 match: {q1['a18_md5_match']}  (actual={q1['a18_md5_actual'][:16]}...)")
print(f"A18 dependents: {q2['dependent_count']}")
print(f"qwen3.5 references: {q3['ref_count']}")
print(f"launch_session A18 hits: {q4['a18_hits_in_launch']}")
print(f"Backup count: {q6['backup_count']}")
print(f"Impact level: {q7['impact_level']}  |  Surgery safe: {q7['surgery_safe']}")
print()
if OUT["_SUMMARY"]["critical_flags"]:
    print("CRITICAL FLAGS DETECTED!")
    for flag in OUT["_SUMMARY"]["critical_flags"]:
        print(f"  - {flag}")
else:
    print("SUCCESS: NO CRITICAL FLAGS")
print("=" * 70)