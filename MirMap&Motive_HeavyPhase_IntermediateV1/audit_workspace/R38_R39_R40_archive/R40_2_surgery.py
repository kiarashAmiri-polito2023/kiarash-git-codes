import os, hashlib, json, shutil, py_compile, importlib.util, re
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18 = os.path.join(ROOT, "agents", "A18_deep_agent_verifier.py")
BD = os.path.join(ROOT, "backups", "A18_deep_agent_verifier")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")

with open(A18, "rb") as f:
    pre_md5 = hashlib.md5(f.read()).hexdigest()
with open(A18, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

print("PRE MD5: " + pre_md5 + " | Lines: " + str(len(lines)))

os.makedirs(BD, exist_ok=True)
bp = os.path.join(BD, "A18_pre_R40_" + ts + ".py")
shutil.copy2(A18, bp)
print("BACKUP: " + bp)

changes = []
new_lines = list(lines)

# === FIX BUG-CA: open() text mode without encoding ===
for i in range(len(new_lines)):
    s = new_lines[i].strip()
    if s.startswith("#") or "open(" not in s or "encoding" in s:
        continue
    if '"rb"' in s or '"wb"' in s or '"ab"' in s:
        continue
    idx = new_lines[i].find("open(")
    d, pe = 0, -1
    for j in range(idx + 4, len(new_lines[i])):
        if new_lines[i][j] == "(":
            d += 1
        elif new_lines[i][j] == ")":
            if d == 0:
                pe = j
                break
            d -= 1
    if pe > 0:
        new_lines[i] = new_lines[i][:pe] + ', encoding="utf-8"' + new_lines[i][pe:]
        changes.append("CA L" + str(i+1) + ": +encoding")

# === FIX BUG-CC: reduce long sleeps ===
for i in range(len(new_lines)):
    m = re.search(r"time\.sleep\((\d+\.?\d*)\)", new_lines[i])
    if m and float(m.group(1)) > 3:
        old = "time.sleep(" + m.group(1) + ")"
        new_lines[i] = new_lines[i].replace(old, "time.sleep(2)")
        changes.append("CC L" + str(i+1) + ": " + m.group(1) + "s->2s")

# === FIX BUG-BW: add warmup ===
full_src = "".join(lines)
if "warmup" not in full_src.lower():
    wf = "\ndef warmup_lmstudio():\n"
    wf += '    """BUG-BW: reduce cold-load latency"""\n'
    wf += "    import urllib.request\n"
    wf += "    try:\n"
    wf += '        urllib.request.urlopen("http://localhost:1234/v1/models", timeout=3)\n'
    wf += "    except Exception:\n"
    wf += "        pass\n\n"
    mi = -1
    for i in range(len(new_lines)):
        if new_lines[i].strip().startswith("def main("):
            mi = i
            break
    if mi > 0:
        new_lines.insert(mi, wf)
        for i in range(mi + 1, min(mi + 15, len(new_lines))):
            s2 = new_lines[i].strip()
            if s2 and not s2.startswith("#") and not s2.startswith('"""'):
                ind = len(new_lines[i]) - len(new_lines[i].lstrip())
                new_lines.insert(i, " " * ind + "warmup_lmstudio()  # BUG-BW\n")
                changes.append("BW: +warmup_lmstudio")
                break

with open(A18, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

with open(A18, "rb") as f:
    post_md5 = hashlib.md5(f.read()).hexdigest()

try:
    py_compile.compile(A18, doraise=True)
    comp = "PASS"
except Exception as e:
    comp = "FAIL:" + str(e)[:80]

try:
    sp = importlib.util.spec_from_file_location("A18t", A18)
    md = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(md)
    imp = "PASS"
    funcs = [x for x in dir(md) if callable(getattr(md, x)) and not x.startswith("_")]
except Exception as e:
    imp = "FAIL:" + str(e)[:80]
    funcs = []

with open(A18, "r", encoding="utf-8-sig") as f:
    ps = f.read()

print("POST MD5: " + post_md5)
print("CHANGED: " + str(pre_md5 != post_md5))
print("COMPILE: " + comp)
print("IMPORT: " + imp)
print("FUNCS: " + str(funcs))
print("CHANGES: " + str(len(changes)))
for c in changes:
    print("  " + c)
print("OPENS: " + str(ps.count("open(")) + " | ENCODINGS: " + str(ps.count("encoding=")))
print("SLEEPS: " + str(ps.count("time.sleep")) + " | WARMUP: " + str("warmup" in ps.lower()))

rp = os.path.join(ROOT, "R40_2_surgery_report.json")
with open(rp, "w", encoding="utf-8") as f:
    json.dump({"pre": pre_md5, "post": post_md5, "backup": bp, "changes": changes, "compile": comp, "import": imp, "funcs": funcs}, f, indent=2)
print("REPORT: " + rp)
