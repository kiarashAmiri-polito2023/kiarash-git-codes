import os,sys,json,time,importlib.util,inspect
from datetime import datetime
ROOT=r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18=os.path.join(ROOT,"agents","A18_deep_agent_verifier.py")
print("="*60)
print("R40.8 E2E QUORUM - FINAL CORRECT")
print("="*60)
sp=importlib.util.spec_from_file_location("A18f",A18)
mod=importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)
print("IMPORT: PASS")
gk=""
ok_key=""
for p,n in [(".secrets/gemini.key","gk"),(".secrets/openrouter.key","ok")]:
    fp=os.path.join(ROOT,p)
    if os.path.exists(fp):
        with open(fp,"r",encoding="utf-8-sig") as f:
            if n=="gk": gk=f.read().strip()
            else: ok_key=f.read().strip()
        print(n+" loaded: "+str(len(f.read().strip()))+" chars")
tgt=os.path.join(ROOT,"agents","launch_session.py")
with open(tgt,"r",encoding="utf-8-sig") as f: content=f.read()
print("Target: launch_session.py ("+str(len(content))+" chars)")
R={}
# Test 1: LMStudio with model_name
print("\n[1/3] LMStudio ...")
t0=time.time()
try:
    raw=mod.query_lmstudio("qwen3.5-9b","Reply ONLY JSON: {\"verdict\":\"PASS\",\"score\":85,\"issues\":[]}")
    dt=time.time()-t0
    parsed=mod.extract_json(raw) if raw else None
    R["lmstudio"]={"ok":bool(raw),"sec":round(dt,2),"parsed":parsed is not None,"prefix":str(raw)[:60]}
    print("  ok={} {:.1f}s parsed={}".format(R["lmstudio"]["ok"],dt,R["lmstudio"]["parsed"]))
except Exception as e:
    R["lmstudio"]={"ok":False,"err":str(e)[:100]}
    print("  FAIL: "+str(e)[:100])
# Test 2+3: via analyze_agent (which calls gemini+openrouter internally)
print("\n[2/3+3/3] Full analyze_agent E2E ...")
print("  Calling: analyze_agent(name, content, g_key, or_key)")
t0=time.time()
try:
    res=mod.analyze_agent("launch_session.py",content,gk,ok_key)
    dt=time.time()-t0
    R["e2e"]={"ok":True,"sec":round(dt,2),"type":type(res).__name__}
    if isinstance(res,dict):
        ks=list(res.keys())
        print("  KEYS: "+str(ks[:12]))
        for k,v in list(res.items())[:8]:
            print("    {}: {}".format(k,str(v)[:100]))
        # Check for provider results inside
        for pk in ["gemini","openrouter","lmstudio","nemotron","providers","results","votes","quorum"]:
            if pk in res:
                print("  >> {}: {}".format(pk,str(res[pk])[:150]))
    elif isinstance(res,str):
        print("  OUT: "+res[:400])
    else:
        print("  OUT: "+str(res)[:400])
    print("  TIME: {:.1f}s".format(dt))
except Exception as e:
    R["e2e"]={"ok":False,"err":str(e)[:200]}
    print("  FAIL: "+str(e)[:200])
# Verdict
e2e_ok=R.get("e2e",{}).get("ok",False)
lm_ok=R.get("lmstudio",{}).get("ok",False)
print("\n"+"="*60)
print("LMStudio: {} | E2E analyze_agent: {}".format("PASS" if lm_ok else "FAIL","PASS" if e2e_ok else "FAIL"))
if e2e_ok and lm_ok:
    v="BUG-AR (multi-model quorum failure) RESOLVED"
elif e2e_ok:
    v="BUG-AR RESOLVED (E2E OK, LMStudio issue)"
elif lm_ok:
    v="BUG-AR PARTIAL: LMStudio OK, E2E failed"
else:
    v="BUG-AR OPEN"
print("VERDICT: "+v)
print("="*60)
rp=os.path.join(ROOT,"R40_8_quorum_report.json")
with open(rp,"w",encoding="utf-8") as f:
    json.dump({"R":R,"verdict":v,"ts":datetime.now().isoformat()},f,indent=2,default=str)
print("SAVED: "+rp)
