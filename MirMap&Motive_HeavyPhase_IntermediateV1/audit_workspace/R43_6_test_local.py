import sys, os, json, time, inspect
sys.path.insert(0, r'C:\Users\Admin\kiarash works\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents')

print('=' * 60)
print(' R43.6 PYTHON TESTS')
print('=' * 60)

# T1: Import
print('\n[T1] Import A18...')
try:
    import A18_deep_agent_verifier as a18
    print('  [PASS] Imported')
except Exception as e:
    print(f'  [FAIL] {e}')
    sys.exit(1)

# T2: qwen3.6-27b fast ping
print('\n[T2] qwen3.6-27b ping...')
t0 = time.time()
try:
    r = a18.query_lmstudio('qwen3.6-27b', 'Reply exactly: PONG', retries=1)
    lat = round(time.time() - t0, 2)
    ok = r and 'PONG' in r.upper()
    print(f'  [{"PASS" if ok else "WARN"}] {lat}s | {str(r)[:80]}')
except Exception as e:
    print(f'  [FAIL] {e}')

# T3: qwen/qwen3-vl-30b fast ping
print('\n[T3] qwen/qwen3-vl-30b ping...')
t0 = time.time()
try:
    r = a18.query_lmstudio('qwen/qwen3-vl-30b', 'Reply exactly: VL-OK', retries=1)
    lat = round(time.time() - t0, 2)
    ok = r and 'VL' in r.upper()
    print(f'  [{"PASS" if ok else "WARN"}] {lat}s | {str(r)[:80]}')
except Exception as e:
    print(f'  [FAIL] {e}')

# T4: extract_json clean
print('\n[T4] extract_json (clean)...')
mock = '{"verdict":"PASS","confidence":85,"rationale":"ok","strengths":["s"],"concerns":["c"],"research_impact":"ok"}'
p = a18.extract_json(mock)
print(f'  [{"PASS" if p and p.get("verdict")=="PASS" else "FAIL"}] {p}')

# T5: extract_json with CoT leak
print('\n[T5] extract_json (CoT leak)...')
mock2 = 'Thinking Process: blah\n{"verdict":"FAIL","confidence":60,"rationale":"bug","strengths":[],"concerns":["r"],"research_impact":"low"}'
p2 = a18.extract_json(mock2)
print(f'  [{"PASS" if p2 and p2.get("verdict")=="FAIL" else "FAIL"}] {p2}')

# T6: Real audit slam_to_bev.py via qwen3.6-27b
print('\n[T6] Real audit: slam_to_bev.py -> qwen3.6-27b...')
sa = os.path.join(r'C:\Users\Admin\kiarash works\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents', 'slam_to_bev.py')
if os.path.exists(sa):
    with open(sa, 'r', encoding='utf-8') as f:
        code = f.read()
    prompt = (
        'Audit this MiR100 robot code. Return ONLY JSON:\n'
        '{"verdict":"PASS|FAIL","confidence":0-100,"rationale":"1 sentence",'
        '"strengths":[],"concerns":[],"research_impact":"1 sentence"}\n\n'
        f'CODE:\n{code[:2000]}'
    )
    t0 = time.time()
    raw = a18.query_lmstudio('qwen3.6-27b', prompt, retries=1)
    lat = round(time.time() - t0, 2)
    if raw:
        p3 = a18.extract_json(raw)
        if p3 and 'verdict' in p3:
            print(f'  [PASS] {lat}s | {p3["verdict"]} ({p3.get("confidence")}%)')
            print(f'  Rationale: {p3.get("rationale","")[:120]}')
        else:
            print(f'  [WARN] {lat}s | JSON parse failed')
            print(f'  Raw (200): {raw[:200]}')
    else:
        print(f'  [FAIL] No response in {lat}s')

# T7: Real audit slam_to_bev.py via qwen/qwen3-vl-30b
print('\n[T7] Real audit: slam_to_bev.py -> qwen/qwen3-vl-30b...')
if os.path.exists(sa):
    t0 = time.time()
    raw = a18.query_lmstudio('qwen/qwen3-vl-30b', prompt, retries=1)
    lat = round(time.time() - t0, 2)
    if raw:
        p4 = a18.extract_json(raw)
        if p4 and 'verdict' in p4:
            print(f'  [PASS] {lat}s | {p4["verdict"]} ({p4.get("confidence")}%)')
        else:
            print(f'  [WARN] {lat}s | parse fail | Raw(200): {raw[:200]}')
    else:
        print(f'  [FAIL] No response in {lat}s')

# T8: Signature check (BUG-CO)
print('\n[T8] Function signatures (BUG-CO)...')
for fn_name in ['query_gemini', 'query_openrouter', 'query_lmstudio']:
    fn = getattr(a18, fn_name, None)
    if fn:
        sig = str(inspect.signature(fn))
        print(f'  {fn_name}: {sig}')
    else:
        print(f'  {fn_name}: NOT FOUND')

print('\n' + '=' * 60)
print(' R43.6 COMPLETE')
print('=' * 60)