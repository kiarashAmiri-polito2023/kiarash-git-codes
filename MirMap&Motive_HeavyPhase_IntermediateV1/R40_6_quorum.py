import os,sys,json,time,importlib.util
from datetime import datetime
ROOT=r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18=os.path.join(ROOT,"agents","A18_deep_agent_verifier.py")
print("="*60)
print("R40.6 E2E QUORUM SMOKE - BUG-AR")
print("="*60)
sp=importlib.util.spec_from_file_location("A18q",A18)
mod=importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)
print("IMPORT: PASS")
tgt=os.path.join(ROOT,"agents","launch_session.py")
print("TARGET: "+tgt)
R={}
for name,fn in [("lmstudio",mod.query_lmstudio),("gemini",mod.query_gemini),("nemotron",mod.query_openrouter)]:
    print("\n["+name+"] calling ...")
    t0=time.time()
    try:
        raw=fn("Reply ONLY with JSON: {\"verdict\":\"PASS\",\"score\":85,\"issues\":[]}")
        dt=time.time()-t0
        parsed=mod.extract_json(raw) if raw else None
        R[name]={"ok":bool(raw),"sec":round(dt,2),"len":len(str(raw)),"parsed":parsed is not None,"prefix":str(raw)[:50]}
        print("  ok={} {:.1f}s parsed={} prefix={}".format(R[name]["ok"],dt,R[name]["parsed"],R[name]["prefix"]))
    except Exception as e:
        R[name]={"ok":False,"err":str(e)[:80]}
        print("  FAIL: "+str(e)[:80])
print("\n--- Full analyze_agent ---")
t0=time.time()
try:
    res=mod.analyze_agent(tgt)
    dt=time.time()-t0
    R["e2e"]={"ok":True,"sec":round(dt,2),"type":type(res).__name__}
    if isinstance(res,dict):
        print("  KEYS: "+str(list(res.keys())[:8]))
        for k,v in list(res.items())[:5]:
            print("    {}: {}".format(k,str(v)[:80]))
    else:
        print("  OUT: "+str(res)[:200])
except Exception as e:
    R["e2e"]={"ok":False,"err":str(e)[:120]}
    print("  FAIL: "+str(e)[:120])
ok_p=sum(1 for n in ["lmstudio","gemini","nemotron"] if R.get(n,{}).get("ok"))
ok_j=sum(1 for n in ["lmstudio","gemini","nemotron"] if R.get(n,{}).get("parsed"))
print("\n"+"="*60)
print("Providers: {}/3 | Parsers: {}/3 | E2E: {}".format(ok_p,ok_j,"PASS" if R.get("e2e",{}).get("ok") else "FAIL"))
if ok_p>=2 and ok_j>=2 and R.get("e2e",{}).get("ok"):
    v="BUG-AR RESOLVED"
elif ok_p>=2:
    v="BUG-AR PARTIAL"
else:
    v="BUG-AR OPEN"
print("VERDICT: "+v)
print("="*60)
rp=os.path.join(ROOT,"R40_6_quorum_report.json")
with open(rp,"w",encoding="utf-8") as f:
    json.dump({"R":R,"verdict":v,"ts":datetime.now().isoformat()},f,indent=2,default=str)
print("SAVED: "+rp)
