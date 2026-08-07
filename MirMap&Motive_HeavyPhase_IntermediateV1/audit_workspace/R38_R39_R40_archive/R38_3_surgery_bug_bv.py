# -*- coding: utf-8 -*-
"""
R38.3 — BUG-BV Surgery: L1(System Prompt) + L2(Defensive Parser) + L3(LMStudio Slot)
Rules: 0,5,6,7,25,28,34,43,45
"""
import os
import sys
import hashlib
import shutil
import py_compile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
A18_PATH = PROJECT_ROOT / "agents" / "A18_deep_agent_verifier.py"
BACKUP_DIR = PROJECT_ROOT / "backups" / "A18_deep_agent_verifier"
EXPECTED_MD5 = "c6d4a87ca25d76c8afa3ac9e72aa9591"

LOG = []

def md5_binary(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def log(msg):
    LOG.append(msg)
    print(msg)

# ================================================================
# PHASE 0: PRE-FLIGHT CHECKS
# ================================================================
log("=" * 70)
log("R38.3 BUG-BV SURGERY — STARTING")
log("=" * 70)

if not A18_PATH.is_file():
    log("FATAL: A18 not found!")
    sys.exit(1)

actual_md5 = md5_binary(A18_PATH)
log(f"A18 MD5 actual:   {actual_md5}")
log(f"A18 MD5 expected: {EXPECTED_MD5}")
if actual_md5 != EXPECTED_MD5:
    log("FATAL: MD5 mismatch! File changed since baseline. ABORTING.")
    sys.exit(1)
log("MD5 match: OK")

# Read file (Rule 7: utf-8-sig)
with open(A18_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
    original = f.read()
original_lines = original.splitlines()
log(f"Original: {len(original_lines)} lines, {len(original)} chars")

# ================================================================
# PHASE 1: BACKUP (Rule 5, 25, 34)
# ================================================================
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_name = f"A18_deep_agent_verifier_pre_surgery_R38_{ts}.py"
backup_path = BACKUP_DIR / backup_name
shutil.copy2(str(A18_PATH), str(backup_path))
backup_md5 = md5_binary(backup_path)
log(f"Backup created: {backup_path.name}")
log(f"Backup MD5: {backup_md5}")
if backup_md5 != actual_md5:
    log("FATAL: Backup MD5 mismatch! ABORTING.")
    sys.exit(1)
log("Backup integrity: OK")

# ================================================================
# PHASE 2: APPLY SURGERY (Rule 28: line-based exact match)
# ================================================================
content = original
changes_applied = 0
changes_failed = 0

def apply_replace(label, old_str, new_str):
    global content, changes_applied, changes_failed
    if old_str not in content:
        log(f"  [FAIL] {label}: target string NOT FOUND in A18!")
        changes_failed += 1
        return False
    count = content.count(old_str)
    if count > 1:
        log(f"  [WARN] {label}: target found {count} times, replacing first only")
    content = content.replace(old_str, new_str, 1)
    log(f"  [OK] {label}")
    changes_applied += 1
    return True

def apply_insert_before(label, anchor_str, insert_str):
    global content, changes_applied, changes_failed
    if anchor_str not in content:
        log(f"  [FAIL] {label}: anchor NOT FOUND!")
        changes_failed += 1
        return False
    content = content.replace(anchor_str, insert_str + "\n" + anchor_str, 1)
    log(f"  [OK] {label}")
    changes_applied += 1
    return True

def apply_insert_after(label, anchor_str, insert_str):
    global content, changes_applied, changes_failed
    if anchor_str not in content:
        log(f"  [FAIL] {label}: anchor NOT FOUND!")
        changes_failed += 1
        return False
    content = content.replace(anchor_str, anchor_str + "\n" + insert_str, 1)
    log(f"  [OK] {label}")
    changes_applied += 1
    return True

# ---- S1: REPLACE extract_json (L23-48) ----
log("\n--- S1: L2 Defensive Parser (D16,D17,D26,D27,D92) ---")
OLD_EXTRACT = '''def extract_json(text):
    if not text or not isinstance(text, str):
        return None
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    m = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\\{[^{}]*\\"verdict\\"[^{}]*\\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\\{.*\\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None'''

NEW_EXTRACT = '''def extract_json(text):
    """L2 Defensive Parser - CoT suppression + find/rfind + nested braces."""
    if not text or not isinstance(text, str):
        return None
    # --- Strip thinking/CoT leaks (D26, D27) ---
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"Thinking Process:.*?(?=\\{)", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<\\|channel\\|>analysis<\\|message\\|>.*?<\\|end\\|>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    # --- Direct parse ---
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # --- find/rfind defensive extraction (D16, D17, D92) ---
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
        # Nested brace balancing
        depth = 0
        for i, ch in enumerate(cleaned[first_brace:], first_brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                candidate = cleaned[first_brace:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    break
    # --- Fallback: regex patterns ---
    m = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\\{[^{}]*\\"verdict\\"[^{}]*\\})", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None'''

apply_replace("S1: extract_json rewrite", OLD_EXTRACT, NEW_EXTRACT)

# ---- S2: REPLACE system prompt in query_openrouter (L55) ----
log("\n--- S2: L1 Anti-CoT System Prompt - OpenRouter (D31, D93) ---")
OLD_SYS = '{"role": "system", "content": "You are a strict robotics code referee. Return ONLY valid JSON."}'
NEW_SYS = '{"role": "system", "content": "You are a strict robotics code referee. Return ONLY valid JSON. Do NOT include thinking, reasoning, or explanation. Do NOT use <think> tags. Your entire response must be a single JSON object and nothing else."}'
apply_replace("S2: OpenRouter system prompt", OLD_SYS, NEW_SYS)

# ---- S3: INSERT anti-CoT prefix in query_gemini ----
log("\n--- S3: L1 Anti-CoT System Prompt - Gemini (D31, D93) ---")
GEMINI_ANCHOR = 'def query_gemini(model_name, prompt, api_key, use_json_mode=False, retries=2):'
GEMINI_INSERT = '''    # L1: Anti-CoT prefix for Gemini (D26, D27, D31)
    prompt = "IMPORTANT: Return ONLY a valid JSON object. Do NOT include any thinking, reasoning, chain-of-thought, or <think> tags. Your entire response must be parseable as JSON.\\n\\n" + prompt'''
apply_insert_after("S3: Gemini anti-CoT prefix", GEMINI_ANCHOR, GEMINI_INSERT)

# ---- S4: INSERT query_lmstudio function before analyze_agent ----
log("\n--- S4: L3 LMStudio Slot Handler (D96) ---")
LMSTUDIO_FUNC = '''
def query_lmstudio(model_name, prompt, retries=2):
    """L3: LMStudio local model query - OpenAI-compatible API (D96)."""
    url = "http://localhost:1234/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a strict robotics code referee. Return ONLY valid JSON. Do NOT include thinking, reasoning, or explanation. Do NOT use <think> tags. Your entire response must be a single JSON object and nothing else."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }
    data = json.dumps(payload).encode("utf-8")
    ctx = ssl.create_default_context()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content_text = result["choices"][0]["message"]["content"]
            if content_text and content_text.strip():
                return content_text
            print(f"    [RETRY {attempt+1}] LMStudio {model_name}: empty content")
        except Exception as e:
            print(f"    [RETRY {attempt+1}] LMStudio {model_name}: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(2)
    return None
'''
ANALYZE_ANCHOR = "def analyze_agent(name, content, g_key, or_key):"
apply_insert_before("S4: query_lmstudio function", ANALYZE_ANCHOR, LMSTUDIO_FUNC)

# ---- S5: REPLACE model slots (L142-144) ----
log("\n--- S5: L3 Replace dead Flash with LMStudio (D46, D48) ---")
OLD_SLOTS = '''        ("gemini-robotics-er-2-preview", "gemini", False),
        ("gemini-2.5-flash", "gemini", True),
        ("nvidia/nemotron-3.5-lightning:free", "openrouter", False),'''
NEW_SLOTS = '''        ("gemini-robotics-er-2-preview", "gemini", False),
        ("qwen3.5-9b", "lmstudio", False),
        ("nvidia/nemotron-3.5-lightning:free", "openrouter", False),'''
apply_replace("S5: Model slots (Flash->LMStudio)", OLD_SLOTS, NEW_SLOTS)

# ---- S6: REPLACE dispatch logic ----
log("\n--- S6: L3 Add LMStudio dispatch (D53) ---")
OLD_DISPATCH = '''        if provider == "gemini":
            raw = query_gemini(model_id, ref_prompt, g_key, use_json_mode=json_mode)
            # R35.10b: Fallback to OpenRouter if Gemini API returns 503/timeout
            if raw is None and "flash" in model_id:
                print(f"    [FALLBACK] Gemini 503 -> OpenRouter mirror for {model_id}")
                raw = query_openrouter("google/gemini-2.5-flash", ref_prompt, or_key)
        else:
            raw = query_openrouter(model_id, ref_prompt, or_key)'''
NEW_DISPATCH = '''        if provider == "gemini":
            raw = query_gemini(model_id, ref_prompt, g_key, use_json_mode=json_mode)
            if raw is None:
                print(f"    [FALLBACK] Gemini failed -> LMStudio for {model_id}")
                raw = query_lmstudio("qwen3.5-9b", ref_prompt)
        elif provider == "lmstudio":
            raw = query_lmstudio(model_id, ref_prompt)
        else:
            raw = query_openrouter(model_id, ref_prompt, or_key)'''
apply_replace("S6: Dispatch logic", OLD_DISPATCH, NEW_DISPATCH)

# ---- S7: UPDATE panel names ----
log("\n--- S7: Update panel names ---")
apply_replace("S7a: Print panel name",
    "MULTI-AI VERIFICATION (3-Model: Robotics-ER + Flash + Nemotron)",
    "MULTI-AI VERIFICATION (3-Model: Robotics-ER + LMStudio-Qwen3.5 + Nemotron)")
apply_replace("S7b: Report panel name",
    "Panel: Gemini-Robotics-ER-2 + Gemini-3.5-Flash + Nemotron-3.5-Lightning",
    "Panel: Gemini-Robotics-ER-2 + LMStudio-Qwen3.5-9B + Nemotron-3.5-Lightning")

# ================================================================
# PHASE 3: WRITE & VERIFY (Rule 6, 7)
# ================================================================
log(f"\n--- RESULTS ---")
log(f"Changes applied: {changes_applied}")
log(f"Changes failed:  {changes_failed}")

if changes_failed > 0:
    log("WARNING: Some changes failed! Review above.")
    if changes_applied == 0:
        log("FATAL: No changes applied. ABORTING without writing.")
        sys.exit(1)

# Write (Rule 7: utf-8, no BOM)
with open(A18_PATH, "w", encoding="utf-8") as f:
    f.write(content)
log(f"File written: {A18_PATH}")

new_md5 = md5_binary(A18_PATH)
log(f"New MD5: {new_md5}")
new_lines = content.splitlines()
log(f"New size: {len(new_lines)} lines, {len(content)} chars")
log(f"Line delta: {len(new_lines) - len(original_lines):+d}")

# py_compile (Rule 6)
try:
    py_compile.compile(str(A18_PATH), doraise=True)
    log("py_compile: PASS")
except py_compile.PyCompileError as e:
    log(f"py_compile: FAIL - {e}")
    log("ROLLING BACK to backup!")
    shutil.copy2(str(backup_path), str(A18_PATH))
    rollback_md5 = md5_binary(A18_PATH)
    log(f"Rollback MD5: {rollback_md5} (expected {actual_md5})")
    sys.exit(1)

log("\n" + "=" * 70)
log("SURGERY COMPLETE — A18 modified successfully")
log(f"Backup at: {backup_path}")
log(f"New MD5: {new_md5}")
log("=" * 70)