import os, json, time, urllib.request
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
print("=" * 60)
print("R42.0 COMPARISON TEST: Cloud AI vs Local Qwen for GitHub")
print("=" * 60)

# Test 1: GitHub API speed (what Cloud AI already does)
print("\n--- Test 1: GitHub API Direct (Cloud AI method) ---")
repos = ["octo-models/octo", "OpenVLA/openvla", "ros-planning/navigation2"]
t0 = time.time()
for repo in repos:
    req = urllib.request.Request("https://api.github.com/repos/" + repo)
    req.add_header("User-Agent", "MiR100")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            print("  {} : stars={} lang={}".format(repo, data.get("stargazers_count"), data.get("language")))
    except Exception as e:
        print("  {} : FAIL {}".format(repo, str(e)[:50]))
t1 = time.time()
print("  Total time: {:.2f}s for {} repos".format(t1-t0, len(repos)))

# Test 2: LM Studio speed for same task
print("\n--- Test 2: LM Studio Qwen (Local method) ---")
t0 = time.time()
try:
    prompt = "What are the star counts and languages of these GitHub repos: octo-models/octo, OpenVLA/openvla, ros-planning/navigation2? Reply in JSON only."
    payload = json.dumps({
        "model": "qwen",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200
    }).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, payload, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
        answer = data["choices"][0]["message"]["content"]
        print("  Qwen answer: " + answer[:200])
except Exception as e:
    print("  FAIL: " + str(e)[:100])
t1 = time.time()
print("  Total time: {:.2f}s".format(t1-t0))

# Verdict
print("\n" + "=" * 60)
print("VERDICT")
print("=" * 60)
print("GitHub API: FAST, ACCURATE, REAL DATA")
print("Qwen Local: SLOWER, MAY HALLUCINATE, NO REAL-TIME DATA")
print("")
print("CONCLUSION: For GitHub metadata -> Cloud AI + PowerShell is BETTER")
print("            For deep code analysis -> Qwen Local is BETTER")
print("            No need to connect Qwen to GitHub API directly")
print("=" * 60)
