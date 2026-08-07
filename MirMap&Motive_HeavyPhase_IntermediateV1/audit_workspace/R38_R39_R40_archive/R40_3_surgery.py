import os,hashlib,json,shutil,py_compile,importlib.util
from datetime import datetime
ROOT=r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
A18=os.path.join(ROOT,"agents","A18_deep_agent_verifier.py")
BD=os.path.join(ROOT,"backups","A18_deep_agent_verifier")
ts=datetime.now().strftime("%Y%m%d_%H%M%S")
with open(A18,"r",encoding="utf-8-sig") as f: lines=f.readlines()
with open(A18,"rb") as f: pre=hashlib.md5(f.read()).hexdigest()
print("PRE: "+pre)
os.makedirs(BD,exist_ok=True)
bp=os.path.join(BD,"A18_pre_R403_"+ts+".py")
shutil.copy2(A18,bp)
print("BACKUP: "+bp)
nl=list(lines); ch=[]
# BUG-CA: find ALL open() without encoding, skip binary/urlopen/comments
print("\n--- BUG-CA SCAN ---")
for i in range(len(nl)):
    s=nl[i]
    st=s.strip()
    if st.startswith("#"): continue
    if "open(" not in s: continue
    if "encoding" in s: continue
    if "urlopen" in s: continue
    if '"rb"' in s or "'rb'" in s: continue
    if '"wb"' in s or "'wb'" in s: continue
    if '"ab"' in s or "'ab'" in s: continue
    p=s.find("open(")
    d=0; pe=-1
    for j in range(p+4,len(s)):
        if s[j]=="(": d+=1
        elif s[j]==")":
            if d==0: pe=j; break
            d-=1
    if pe>0:
        nl[i]=s[:pe]+', encoding="utf-8"'+s[pe:]
        ch.append("CA:L"+str(i+1)+": "+st[:60])
        print("  FIXED L"+str(i+1)+": "+st[:60])
if not any(c.startswith("CA") for c in ch):
    print("  No text-mode open() missing encoding found")
# BUG-BU: add retry wrapper
print("\n--- BUG-BU RETRY ---")
src="".join(nl)
if "with_retry" not in src:
    rc="def with_retry(fn, retries=3, delay=2):\n"
    rc+="    import time as _t\n"
    rc+="    def w(*a,**kw):\n"
    rc+="        for i in range(retries):\n"
    rc+="            try: return fn(*a,**kw)\n"
    rc+="            except Exception:\n"
    rc+="                if i==retries-1: raise\n"
    rc+="                _t.sleep(delay*(i+1))\n"
    rc+="    return w\n\n"
    for i in range(len(nl)):
        if "def query_gemini" in nl[i]:
            nl.insert(i, rc)
            ch.append("BU:+retry_func")
            offset=nl[i:].index(nl[i]) if nl[i].strip().startswith("def") else 0
            for j in range(i+1, min(i+80, len(nl))):
                if nl[j].strip().startswith("def ") and "query_gemini" not in nl[j]:
                    nl.insert(j, "query_gemini = with_retry(query_gemini)\n")
                    nl.insert(j+1, "query_openrouter = with_retry(query_openrouter)\n")
                    ch.append("BU:wrap_gemini+openrouter")
                    print("  Added retry for gemini + openrouter")
                    break
            break
else:
    print("  retry already exists")
with open(A18,"w",encoding="utf-8") as f: f.writelines(nl)
with open(A18,"rb") as f: post=hashlib.md5(f.read()).hexdigest()
try:
    py_compile.compile(A18,doraise=True); comp="PASS"
except Exception as e: comp="FAIL:"+str(e)[:80]
try:
    sp=importlib.util.spec_from_file_location("A18x",A18)
    md=importlib.util.module_from_spec(sp); sp.loader.exec_module(md)
    imp="PASS"
    funcs=[x for x in dir(md) if callable(getattr(md,x)) and not x.startswith("_")]
except Exception as e: imp="FAIL:"+str(e)[:80]; funcs=[]
with open(A18,"r",encoding="utf-8-sig") as f: fs=f.read()
print("\n=== R40.3 RESULT ===")
print("PRE:  "+pre)
print("POST: "+post)
print("COMPILE: "+comp)
print("IMPORT: "+imp)
print("CHANGES: "+str(ch))
print("OPENS:"+str(fs.count("open("))+" ENC:"+str(fs.count("encoding=")))
print("RETRY:"+str("with_retry" in fs))
rp=os.path.join(ROOT,"R40_3_report.json")
with open(rp,"w",encoding="utf-8") as f:
    json.dump({"pre":pre,"post":post,"compile":comp,"import":imp,"changes":ch,"funcs":funcs},f,indent=2)
print("SAVED: "+rp)
