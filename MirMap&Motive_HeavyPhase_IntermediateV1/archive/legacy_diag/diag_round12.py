import os, re

root = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
a18 = os.path.join(root, "agents", "A18_deep_agent_verifier.py")
a15 = os.path.join(root, "agents", "A15_referee_ai_loop.py")

def analyze(path, label):
    print("")
    print("=== " + label + " ===")
    if not os.path.exists(path):
        print("MISSING")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    print("Lines: " + str(len(lines)) + " | Size: " + str(os.path.getsize(path)) + "B")
    funcs = re.findall(r"def\s+(\w+)\s*\(", content)
    print("Functions (" + str(len(funcs)) + "): " + ", ".join(funcs))
    mt = re.search(r"max_tokens[\"\s:]+(\d+)", content)
    print("max_tokens: " + (mt.group(1) if mt else "NOT FOUND"))
    print("openrouter/auto present: " + str("openrouter/auto" in content))
    print("extract_json present: " + str("extract_json" in content))
    print("nemotron present: " + str("nemotron" in content))
    models = re.findall(r"[\"']([\w\-\.]+/[\w\-\.]+:free)[\"']", content)
    print("Model slugs found: " + str(models))

analyze(a18, "A18 STRUCTURAL/FUNCTIONAL")
analyze(a15, "A15 STRUCTURAL/FUNCTIONAL")

verdict_path = os.path.join(root, "deep_agent_verification", "FINAL_VERDICT.md")
print("")
print("=== BEHAVIORAL ===")
if os.path.exists(verdict_path):
    with open(verdict_path, "r", encoding="utf-8") as f:
        vc = f.read()
    print("NO_RESPONSE count: " + str(vc.count("NO_RESPONSE")))
    print("KEEP count: " + str(vc.count("KEEP")))
    print("FIX count: " + str(vc.count("FIX")))
else:
    print("FINAL_VERDICT.md MISSING")

backup_dir = os.path.join(root, "backups")
print("")
print("=== BACKUP FOLDER ===")
if os.path.exists(backup_dir):
    print("Exists. Contents: " + str(os.listdir(backup_dir)))
else:
    print("Does not exist yet - will be created per Law 19")

print("")
print("=== ROUND 12 DONE ===")
