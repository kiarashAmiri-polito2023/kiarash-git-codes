# -*- coding: utf-8 -*-
import os, sys, json, time, ssl, urllib.request, urllib.error, re
from collections import Counter

# Fix Windows console encoding crashes
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(PROJECT_DIR, ".secrets", "openrouter.key")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
if not OPENROUTER_KEY and os.path.exists(KEY_FILE):
    with open(KEY_FILE, "r", encoding="utf-8-sig") as f:
        OPENROUTER_KEY = f.read().strip()

print(f"API Key Active: {OPENROUTER_KEY[:10]}*** | Length: {len(OPENROUTER_KEY)}")

ssl_context = ssl._create_unverified_context()

# 3 verified live, fast & robust free models (Round 10 Benchmarked)
MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "cohere/north-mini-code:free",
    "inclusionai/ling-3.0-flash-fin:free"
]

CANDIDATES = [
    "auto_labeler.py", "label_registry_auto.py", "slam_to_bev.py",
    "slam_map_annotator.py", "vla_dataset_builder.py", "qwen_dataset_formatter.py",
    "co_pilot_agent.py", "video_narrator.py", "video_learning_agent.py",
    "video_event_extractor.py", "training_curriculum_advisor.py",
    "vla_supervisor_agent.py", "video_quality_agent.py", "cvat_converter.py",
    "cvat_prepopulator.py", "offline_processor.py", "cross_modal_aligner.py",
    "robot_data_analyzer.py", "scene_object_detector.py", "launch_session.py"
]

def extract_json(text):
    """Robust JSON extractor handling markdown blocks and reasoning text (Solves BUG-P)."""
    if not text:
        return None
    # 1. Markdown block ```json ... ```
    m = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if m:
        for block in reversed(m):
            try:
                return json.loads(block)
            except Exception:
                pass
    # 2. Bracket matching with verdict key
    m2 = re.findall(r'(\{[^{}]*"verdict"[^{}]*\})', text)
    if m2:
        for block in reversed(m2):
            try:
                return json.loads(block)
            except Exception:
                pass
    # 3. Direct parse
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    return None

def query_openrouter(model, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/PoliTo/MirMap",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a senior robotics peer reviewer for an IEEE Q1 Journal. Analyze the code and answer strictly with a JSON object: {\"verdict\": \"KEEP\"|\"FIX\"|\"DELETE\"|\"MERGE\", \"reason\": \"1 sentence\"}."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return f"HTTP_ERR_{e.code}: {err_body[:100]}"
    except Exception as e:
        return f"ERR: {str(e)[:100]}"

def analyze_agent(name, content):
    prompt = f"Evaluate this agent for a Q1 paper (Qwen-VL on MiR100):\nFile: {name}\nCode:\n{content[:8000]}\nOutput ONLY JSON: {{\"verdict\": \"KEEP|FIX|DELETE|MERGE\", \"reason\": \"...\"}}"
    votes = []
    for model in MODELS:
        m_tag = model.split("/")[-1].split(":")[0]
        resp = query_openrouter(model, prompt)
        if resp.startswith("HTTP_ERR") or resp.startswith("ERR"):
            print(f"    - {m_tag}: {resp}")
            continue
        parsed = extract_json(resp)
        if parsed and "verdict" in parsed:
            verdict = str(parsed.get("verdict", "UNSURE")).upper()
            if verdict in ["KEEP", "FIX", "DELETE", "MERGE"]:
                votes.append(verdict)
                print(f"    - {m_tag}: {verdict} ({parsed.get('reason', '')[:60]})")
                time.sleep(0.3)
                continue
        # Fallback substring
        u = resp.upper()
        v = "DELETE" if "DELETE" in u else ("KEEP" if "KEEP" in u else ("MERGE" if "MERGE" in u else ("FIX" if "FIX" in u else "UNSURE")))
        votes.append(v)
        print(f"    - {m_tag}: {v} (parsed via fallback)")
        time.sleep(0.3)
    return votes

def main():
    agents_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(os.path.dirname(agents_dir), "deep_agent_verification")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print(" STARTING MULTI-AI AGENT VERIFICATION (3-Model Consensus)")
    print("=" * 65)

    summary = []
    for idx, name in enumerate(CANDIDATES):
        path = os.path.join(agents_dir, name)
        if not os.path.exists(path):
            continue
        print(f"\n[{idx+1}/{len(CANDIDATES)}] Auditing {name}...")
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        votes = analyze_agent(name, content)
        consensus = Counter(votes).most_common(1)[0][0] if votes else "NO_RESPONSE"
        summary.append({"agent": name, "consensus": consensus, "votes": votes})

    md_path = os.path.join(output_dir, "FINAL_VERDICT.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Deep Multi-AI Agent Verification Results\n\n")
        f.write("| Agent | Consensus | Votes |\n")
        f.write("|---|---|---|\n")
        for s in summary:
            f.write(f"| `{s['agent']}` | **{s['consensus']}** | {s['votes']} |\n")

    print("\n" + "=" * 65)
    print(f" SUCCESS! Verification finished. Verdict file:\n {md_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
