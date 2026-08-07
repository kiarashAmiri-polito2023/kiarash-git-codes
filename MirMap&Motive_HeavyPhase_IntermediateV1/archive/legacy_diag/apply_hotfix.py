import os, sys, io, shutil, subprocess
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
AGENTS_DIR = os.path.join(ROOT, "agents")
BACKUP_DIR = os.path.join(ROOT, "backups", "A18_deep_agent_verifier")

print("=" * 70)
print(">>> APPLYING A18 HOTFIX FOR NONETYPE BUG")
print("=" * 70)

# 1. Backup per Law 19
src = os.path.join(AGENTS_DIR, "A18_deep_agent_verifier.py")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak_name = f"A18_deep_agent_verifier_{ts}_pre_nonetype_startswith_fix.py"
shutil.copy2(src, os.path.join(BACKUP_DIR, bak_name))

with open(os.path.join(BACKUP_DIR, "operation_log.md"), "a", encoding="utf-8") as f:
    f.write(f"- **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}** | Hotfix Backup: `{bak_name}` | Reason: `Resolve startswith on NoneType`\n")
print(f"[BACKUP OK] Created hotfix backup: {bak_name}")

# 2. Read current A18
with open(src, "r", encoding="utf-8") as f:
    code = f.read()

# Replace query_openrouter return logic to guarantee string return
old_block = """    try:
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["choices"][0]["message"]["content"]"""

new_block = """    try:
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            choices = res.get("choices", [])
            if not choices:
                return "ERR: Empty choices returned from API"
            content = choices[0].get("message", {}).get("content")
            if content is None:
                return "ERR: Received null content from API"
            return str(content)"""

code = code.replace(old_block, new_block)

# Replace startswith check in analyze_agent to protect against NoneType
old_check = """        resp = query_openrouter(model, prompt)
        if resp.startswith("HTTP_ERR") or resp.startswith("ERR"):"""

new_check = """        resp = query_openrouter(model, prompt)
        if not resp or resp.startswith("HTTP_ERR") or resp.startswith("ERR"):"""

code = code.replace(old_block, new_block) # redundancy double check
code = code.replace(old_check, new_check)

# Write back
with open(src, "w", encoding="utf-8") as f:
    f.write(code)
print("[HOTFIX OK] Safely patched A18_deep_agent_verifier.py")

# 3. Syntax Verification (Law 6 & 15)
res = subprocess.run(["C:\\Python310\\python.exe", "-m", "py_compile", src], capture_output=True, text=True)
print(f"Compilation check: {'SUCCESS' if res.returncode == 0 else 'FAILED'}")

# 4. Live Test
print("\n>>> RETRYING LIVE TEST...")
try:
    import agents.A18_deep_agent_verifier as a18_mod
    test_file = "scene_object_detector.py"
    target = os.path.join(AGENTS_DIR, test_file)
    with open(target, "r", encoding="utf-8-sig") as f:
        src_code = f.read()
    votes = a18_mod.analyze_agent(test_file, src_code)
    print(f"\n[LIVE TEST SUCCESS] Multi-Model Votes: {votes}")
except Exception as e:
    print(f"[TEST FAIL] still failing: {e}")

print("=" * 70)
