import sys, os, time, json
sys.path.insert(0, 'C:/Users/Admin/kiarash works/kiarash git codes/MirMap&Motive_HeavyPhase_IntermediateV1/agents')

import A18_deep_agent_verifier as a18

print('=' * 60)
print(' R43.10 E2E QUORUM TEST')
print(' Models: ' + ', '.join(a18.LOCAL_MODELS))
print('=' * 60)

# ─── Test 1: Warmup all 3 models ───
print('\n[T1] Warmup all 3 models (ping test)...')
warmup_results = {}
for m in a18.LOCAL_MODELS:
    t0 = time.time()
    r = a18.query_lmstudio(m, 'Reply exactly: OK', retries=1)
    lat = round(time.time()-t0, 2)
    ok = r is not None and len(r) > 0
    warmup_results[m] = {'latency': lat, 'ok': ok, 'reply_len': len(r) if r else 0}
    status_str = 'OK' if ok else 'FAIL'
    print(f'  {m:<38} {lat:>6.2f}s | {status_str} | reply_len=' + str(len(r) if r else 0))

# ─── Test 2: Real E2E audit of slam_to_bev.py ───
print('\n[T2] Full E2E audit: slam_to_bev.py (all 3 models + quorum)...')
target_file = os.path.join('C:/Users/Admin/kiarash works/kiarash git codes/MirMap&Motive_HeavyPhase_IntermediateV1/agents', 'slam_to_bev.py')
if not os.path.exists(target_file):
    print('  [SKIP] Target file missing: ' + target_file)
    sys.exit(1)

with open(target_file, 'r', encoding='utf-8-sig', errors='replace') as f:
    content = f.read()

print('  Target: slam_to_bev.py (' + str(len(content)) + ' chars)')
print()

t0 = time.time()
verdict = a18.analyze_agent('slam_to_bev.py', content)
total_lat = round(time.time()-t0, 2)

print()
print(f'  ── QUORUM RESULT (in {total_lat}s) ──')
print('  Verdict:      ' + str(verdict.get('verdict')))
print('  Confidence:   ' + str(verdict.get('confidence')) + '%')
print('  Strengths:    ' + str(len(verdict.get('strengths', []))))
print('  Concerns:     ' + str(len(verdict.get('concerns', []))))
rat = str(verdict.get('rationale', ''))
print('  Rationale:    ' + rat[:200] + '...')

# ─── Test 3: BUG-AR verdict ───
print('\n[T3] BUG-AR VERDICT:')
v = verdict.get('verdict')
if v == 'INSUFFICIENT_QUORUM':
    print('  [FAIL] BUG-AR still OPEN: quorum not reached')
    print('  Rationale: ' + str(verdict.get('rationale')))
elif v in ('PASS', 'FAIL'):
    print('  [SUCCESS] BUG-AR CLOSED: quorum reached with verdict=' + str(v))
else:
    print('  [WARN] Unexpected verdict: ' + str(v))

# ─── Save report ───
report = {
    'round': 'R43.10',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'models': a18.LOCAL_MODELS,
    'warmup': warmup_results,
    'target_agent': 'slam_to_bev.py',
    'total_latency_sec': total_lat,
    'verdict': verdict,
    'bug_ar_status': 'CLOSED' if v in ('PASS', 'FAIL') else 'OPEN'
}

report_out = 'C:/Users/Admin/kiarash works/kiarash git codes/MirMap&Motive_HeavyPhase_IntermediateV1/audit_workspace/R43_10_e2e_report.json'
with open(report_out, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print('\n  [SAVED] ' + report_out)

print('\n' + '=' * 60)
print(' R43.10 COMPLETE')
print('=' * 60)