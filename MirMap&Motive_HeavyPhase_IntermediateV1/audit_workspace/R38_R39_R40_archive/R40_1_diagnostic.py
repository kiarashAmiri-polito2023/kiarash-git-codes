import os, sys, hashlib, json, time, importlib.util, py_compile
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18 = os.path.join(ROOT, "agents", "A18_deep_agent_verifier.py")
VAULT = os.path.join(ROOT, "github_curation_vault")
BACKUP_DIR = os.path.join(ROOT, "backups", "A18_deep_agent_verifier")

R = {"ts": datetime.now().isoformat(), "t": {}}

# T1: A18 existence + MD5
if os.path.exists(A18):
    with open(A18, "rb") as f:
        data = f.read()
    R["t"]["A18_md5"] = hashlib.md5(data).hexdigest()
    R["t"]["A18_lines"] = data.count(b"\n") + 1
    R["t"]["A18_bytes"] = len(data)
else:
    R["t"]["A18_md5"] = "MISSING"

# T2: py_compile
try:
    py_compile.compile(A18, doraise=True)
    R["t"]["A18_compile"] = "PASS"
except Exception as e:
    R["t"]["A18_compile"] = "FAIL:" + str(e)[:80]

# T3: import + functions
try:
    spec = importlib.util.spec_from_file_location("A18", A18)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    funcs = [x for x in dir(mod) if callable(getattr(mod, x)) and not x.startswith("_")]
    R["t"]["A18_import"] = "PASS"
    R["t"]["A18_funcs"] = funcs
except Exception as e:
    R["t"]["A18_import"] = "FAIL:" + str(e)[:80]

# T4: temp files inventory
temps = [f for f in os.listdir(ROOT) if f.startswith("R38_") or f.startswith("R39_") or f.startswith("R40_")]
R["t"]["temp_count"] = len(temps)
R["t"]["temp_files"] = temps[:30]

# T5: Vault audit
deferred = 0
sota_missing = 0
total_v = 0
phantom_hits = {"qwen_inference_engine": 0, "kiarash_gemeni_python_client": 0, "qwen_dataset_builder": 0}
if os.path.isdir(VAULT):
    for d in sorted(os.listdir(VAULT)):
        rp = os.path.join(VAULT, d, "solution_report.txt")
        if not os.path.isfile(rp):
            continue
        total_v += 1
        with open(rp, "r", encoding="utf-8-sig") as f:
            c = f.read()
        if "DEFERRED" in c:
            deferred += 1
        if "primary_sota_repo" not in c or "UNKNOWN" in c:
            sota_missing += 1
        for pn in phantom_hits:
            if pn in c:
                phantom_hits[pn] += 1
R["t"]["vault_total"] = total_v
R["t"]["vault_deferred"] = deferred
R["t"]["vault_sota_missing"] = sota_missing
R["t"]["vault_phantom_refs"] = phantom_hits

# T6: Backup integrity
bc = 0
if os.path.isdir(BACKUP_DIR):
    bc = len([f for f in os.listdir(BACKUP_DIR) if f.endswith(".py")])
R["t"]["backup_count"] = bc

# T7: BUG-CC time.sleep count
if os.path.exists(A18):
    with open(A18, "r", encoding="utf-8-sig") as f:
        src = f.read()
    R["t"]["BUG_CC_sleeps"] = src.count("time.sleep")
    R["t"]["BUG_CA_opens"] = src.count("open(")
    R["t"]["BUG_CA_encodings"] = src.count("encoding=")
    R["t"]["BUG_BV_has_cot_strip"] = any(k in src for k in ["Thinking", "thinking", "cot_strip", "strip_cot"])
    R["t"]["BUG_BV_has_depth"] = "depth" in src.lower() or "brace" in src.lower()
    R["t"]["provider_lmstudio"] = "lmstudio" in src.lower()
    R["t"]["provider_gemini"] = "gemini" in src.lower()
    R["t"]["provider_nemotron"] = "nemotron" in src.lower()
    R["t"]["provider_flash_ref"] = "flash" in src.lower()
    R["t"]["has_retry"] = "retry" in src.lower() or "backoff" in src.lower()
    R["t"]["has_warmup"] = "warmup" in src.lower()

print("=" * 60)
print("R40.1 READ-ONLY FULL DIAGNOSTIC")
print("=" * 60)
for k, v in R["t"].items():
    print("  {:<30s} {}".format(str(k), str(v)))
print("=" * 60)

out = os.path.join(ROOT, "R40_1_diagnostic_report.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(R, f, indent=2, ensure_ascii=False)
print("Saved: " + out)
