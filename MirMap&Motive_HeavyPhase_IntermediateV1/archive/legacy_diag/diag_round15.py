import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"

print("=" * 70)
print("[1/3] STRUCTURAL: FINAL_REFEREE_VERDICT.md (A15 output)")
print("=" * 70)
frv = os.path.join(root, "FINAL_REFEREE_VERDICT.md")
if os.path.exists(frv):
    info = os.stat(frv)
    print("Size: " + str(info.st_size) + "B")
    with open(frv, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()
    print("Contains 'passes succeeded': " + str("passes succeeded" in content))
    idx = content.find("**Result:**")
    if idx >= 0:
        print("Result line: " + content[idx:idx+60])
    print("Contains ALL PASSES FAILED: " + str("ALL PASSES FAILED" in content))
else:
    print("MISSING")

print("")
print("=" * 70)
print("[2/3] FUNCTIONAL: audit_workspace/ run folders")
print("=" * 70)
aw = os.path.join(root, "audit_workspace")
if os.path.exists(aw):
    runs = sorted(os.listdir(aw))
    print("Runs found: " + str(len(runs)))
    for r in runs[-3:]:
        rp = os.path.join(aw, r)
        if os.path.isdir(rp):
            files = os.listdir(rp)
            print("  " + r + " -> " + str(len(files)) + " files: " + str(files[:5]))
else:
    print("audit_workspace/ MISSING")

print("")
print("=" * 70)
print("[3/3] BEHAVIORAL: requests library + py_compile check")
print("=" * 70)
try:
    import requests
    print("requests library: OK (version " + requests.__version__ + ")")
except Exception as e:
    print("requests library: MISSING - " + str(e))

import subprocess
for fname in ["A15_referee_ai_loop.py", "A18_deep_agent_verifier.py"]:
    fpath = os.path.join(root, "agents", fname)
    result = subprocess.run(["C:\\Python310\\python.exe", "-m", "py_compile", fpath],
                             capture_output=True, text=True)
    status = "OK" if result.returncode == 0 else "FAIL: " + result.stderr[:200]
    print(fname + " py_compile: " + status)

print("")
print("=== ROUND 15 DONE ===")
