import os,sys,json,time,importlib.util
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18 = os.path.join(ROOT, "agents", "A18_deep_agent_verifier.py")

print("=" * 60)
print("R40.9 E2E QUORUM SMOKE - FINAL CLEAN")
print("BUG-AR: multi-model consensus in A18")
print("=" * 60)

# Import A18
sp = importlib.util.spec_from_file_location("A18clean", A18)
mod = importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)
print("IMPORT: PASS")

# Load keys safely
gk = ""
ok_key = ""
gkp = os.path.join(ROOT, ".secrets", "gemini.key")
okp = os.path.join(ROOT, ".secrets", "openrouter.key")

if os.path.exists(gkp):
    with open(gkp, "r", encoding="utf-8-sig") as f:
        gk = f.read().strip()
    print("Gemini key loaded: " + str(len(gk)) + " chars")
else:
    print("Gemini key: MISSING")

if os.path.exists(okp):
    with open(okp, "r", encoding="utf-8-sig") as f:
        ok_key = f.read().strip()
    print("OpenRouter key loaded: " + str(len(ok_key)) + " chars")
else:
    print("OpenRouter key: MISSING")

# Load target agent
tgt = os.path.join(ROOT, "agents", "launch_session.py")
with open(tgt, "r", encoding="utf-8-sig") as f:
    content = f.read()
print("Target: launch_session.py (" + str(len(content)) + " chars)")

R = {}
prompt = 'Analyze this code. Reply ONLY with valid JSON: {"verdict":"PASS","score":85,"issues":[]}'

# Test 1: LMStudio
print("\n[1/3] LMStudio direct probe ...")
t0 = time.time()
try:
    raw = mod.query_lmstudio("qwen3.5-9b", prompt)
    dt = time.time() - t0
    parsed = mod.extract_json(raw) if raw else None
    R["lmstudio"] = {
        "ok": bool(raw),
        "sec": round(dt, 2),
        "parsed": parsed is not None,
        "prefix": str(raw)[:60] if raw else "NONE"
    }
    print("  ok={} | {:.2f}s | parsed={} | prefix={}".format(
        R["lmstudio"]["ok"], dt, R["lmstudio"]["parsed"], R["lmstudio"]["prefix"]
    ))
except Exception as e:
    R["lmstudio"] = {"ok": False, "err": str(e)[:100]}
    print("  FAIL: " + str(e)[:100])

# Test 2: Gemini direct probe
print("\n[2/3] Gemini direct probe ...")
t0 = time.time()
try:
    raw = mod.query_gemini(prompt, gk)
    dt = time.time() - t0
    parsed = mod.extract_json(raw) if raw else None
    R["gemini"] = {
        "ok": bool(raw),
        "sec": round(dt, 2),
        "parsed": parsed is not None,
        "prefix": str(raw)[:60] if raw else "NONE"
    }
    print("  ok={} | {:.2f}s | parsed={} | prefix={}".format(
        R["gemini"]["ok"], dt, R["gemini"]["parsed"], R["gemini"]["prefix"]
    ))
except Exception as e:
    R["gemini"] = {"ok": False, "err": str(e)[:100]}
    print("  FAIL: " + str(e)[:100])

# Test 3: Nemotron direct probe
print("\n[3/3] Nemotron direct probe ...")
t0 = time.time()
try:
    raw = mod.query_openrouter(prompt, ok_key)
    dt = time.time() - t0
    parsed = mod.extract_json(raw) if raw else None
    R["nemotron"] = {
        "ok": bool(raw),
        "sec": round(dt, 2),
        "parsed": parsed is not None,
        "prefix": str(raw)[:60] if raw else "NONE"
    }
    print("  ok={} | {:.2f}s | parsed={} | prefix={}".format(
        R["nemotron"]["ok"], dt, R["nemotron"]["parsed"], R["nemotron"]["prefix"]
    ))
except Exception as e:
    R["nemotron"] = {"ok": False, "err": str(e)[:100]}
    print("  FAIL: " + str(e)[:100])

# Test 4: Full analyze_agent E2E
print("\n--- Full analyze_agent E2E ---")
t0 = time.time()
try:
    res = mod.analyze_agent("launch_session.py", content, gk, ok_key)
    dt = time.time() - t0
    R["e2e"] = {"ok": True, "sec": round(dt, 2), "type": type(res).__name__, "data": res}
    print("  TIME: {:.2f}s".format(dt))
    if isinstance(res, dict):
        print("  KEYS: " + str(list(res.keys())[:10]))
        for k, v in list(res.items())[:6]:
            print("    {}: {}".format(k, str(v)[:90]))
    elif isinstance(res, str):
        print("  OUT: " + res[:300])
    else:
        print("  OUT: " + str(res)[:300])
except Exception as e:
    R["e2e"] = {"ok": False, "err": str(e)[:200]}
    print("  FAIL: " + str(e)[:200])

# Summary & Verdict
ok_p = sum(1 for n in ["lmstudio", "gemini", "nemotron"] if R.get(n, {}).get("ok"))
ok_j = sum(1 for n in ["lmstudio", "gemini", "nemotron"] if R.get(n, {}).get("parsed"))
e2e_ok = R.get("e2e", {}).get("ok", False)

print("\n" + "=" * 60)
print("QUORUM VERIFICATION SUMMARY")
print("=" * 60)
print("  Providers responding : {}/3".format(ok_p))
print("  JSON successfully parsed : {}/3".format(ok_j))
print("  Full E2E analyze_agent  : {}".format("PASS" if e2e_ok else "FAIL"))

if ok_p >= 2 and ok_j >= 2 and e2e_ok:
    verdict = "BUG-AR (عدم تشکیل اجماع چندمدلی در A18) RESOLVED — QUORUM ACTIVE"
elif ok_p >= 2 and ok_j >= 2:
    verdict = "BUG-AR (عدم تشکیل اجماع چندمدلی در A18) PARTIALLY RESOLVED — Direct OK, E2E issue"
elif ok_p >= 2:
    verdict = "BUG-AR (عدم تشکیل اجماع چندمدلی در A18) PARTIALLY RESOLVED — Providers up, Parser failed"
else:
    verdict = "BUG-AR (عدم تشکیل اجماع چندمدلی در A18) OPEN — Insufficient live providers"

print("  VERDICT: " + verdict)
print("=" * 60)

rp = os.path.join(ROOT, "R40_9_quorum_report.json")
with open(rp, "w", encoding="utf-8") as f:
    json.dump({"R": R, "verdict": verdict, "ts": datetime.now().isoformat()}, f, indent=2, default=str)
print("SAVED: " + rp)
