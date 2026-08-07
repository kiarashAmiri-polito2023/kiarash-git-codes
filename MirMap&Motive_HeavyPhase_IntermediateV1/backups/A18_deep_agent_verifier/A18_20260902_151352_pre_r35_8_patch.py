import os
import sys
import json
import time
import ssl
import urllib.request
import urllib.error
import re
from collections import Counter

# Target candidates under evaluation (19 Active Agents, cvat_prepopulator archived)
CANDIDATES = [
    "auto_labeler.py", "label_registry_auto.py", "slam_to_bev.py",
    "slam_map_annotator.py", "vla_dataset_builder.py", "qwen_dataset_formatter.py",
    "co_pilot_agent.py", "video_narrator.py", "video_learning_agent.py",
    "video_event_extractor.py", "training_curriculum_advisor.py",
    "vla_supervisor_agent.py", "video_quality_agent.py", "cvat_converter.py",
    "offline_processor.py", "cross_modal_aligner.py", "robot_data_analyzer.py",
    "scene_object_detector.py", "launch_session.py"
]

def extract_json(text):
    if not text or not isinstance(text, str):
        return None
    try:
        return json.loads(text.strip())
    except:
        pass
    # Match markdown codeblocks
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    # Greedy match outermost braces
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    return None

def query_openrouter(model_name, prompt, api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a strict, world-class robotics software referee. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1200
    }
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"    [API-WARN] OpenRouter {model_name} failed: {e}")
    return None

def query_gemini(model_name, prompt, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1000,
            "responseMimeType": "application/json"
        }
    }
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception as e:
        print(f"    [API-WARN] Gemini {model_name} failed: {e}")
    return None

def analyze_agent(name, content, g_key, or_key):
    ref_prompt = (
        "You are an expert robotics system software referee. Audit this file for: "
        "1. Research integrity (no fraud/faking, proper metrics, valid datasets).\n"
        "2. Safety on physical mobile robots (collisions, localization drift, raw path validations).\n"
        "3. Semantic VLA best practices (multi-modal fusion, robust transformations).\n\n"
        "You MUST respond with pure JSON containing exactly this schema:\n"
        "{\n"
        '  "verdict": "PASS" or "FAIL",\n'
        '  "confidence": <integer 0-100>,\n'
        '  "rationale": "one-sentence critical reason for verdict",\n'
        '  "strengths": ["strength 1", "strength 2"],\n'
        '  "concerns": ["concern 1", "concern 2"],\n'
        '  "research_impact": "impact on Nature/IEEE paper quality (2 sentences)"\n'
        "}\n\n"
        f"File: {name}\n"
        f"Source Content:\n{content}"
    )

    # Multi-Model Panel
    models = {
        "gemini-robotics-er-2-preview": ("gemini", "gemini-robotics-er-2-preview"),
        "gemini-3.5-flash": ("gemini", "gemini-3.5-flash"),
        "nvidia/nemotron-3.5-lightning:free": ("openrouter", "nvidia/nemotron-3.5-lightning:free")
    }

    votes = []
    strengths, concerns, rationales = [], [], []
    confidences = []
    impacts = []

    for label, (provider, model_id) in models.items():
        # Avoid rate-limit spikes
        time.sleep(1.0)
        if provider == "gemini":
            raw_resp = query_gemini(model_id, ref_prompt, g_key)
        else:
            raw_resp = query_openrouter(model_id, ref_prompt, or_key)

        parsed = extract_json(raw_resp)
        if parsed and "verdict" in parsed:
            v = parsed["verdict"].upper()
            if v in ["PASS", "FAIL"]:
                votes.append(v)
                confidences.append(int(parsed.get("confidence", 70)))
                rationales.append(f"[{label}]: {parsed.get('rationale', 'N/A')}")
                strengths.extend(parsed.get("strengths", []))
                concerns.extend(parsed.get("concerns", []))
                if parsed.get("research_impact"):
                    impacts.append(parsed["research_impact"])
                print(f"    -> {label:<35} voted: {v} ({parsed.get('confidence') or 70}%)")
        else:
            print(f"    -> {label:<35} returned None or Invalid JSON.")

    if len(votes) < 2:
        return {
            "verdict": "INSUFFICIENT_QUORUM",
            "confidence": 0,
            "rationale": "Not enough AI models successfully returned valid audits.",
            "strengths": [],
            "concerns": [],
            "research_impact": "Consensus audit failed due to API limitations."
        }

    # Majority Vote
    vote_counts = Counter(votes)
    majority_verdict = vote_counts.most_common(1)[0][0]
    avg_conf = sum(confidences) // len(confidences)

    return {
        "verdict": majority_verdict,
        "confidence": avg_conf,
        "rationale": "; ".join(rationales),
        "strengths": list(set(strengths))[:5],
        "concerns": list(set(concerns))[:5],
        "research_impact": " ".join(set(impacts))[:400]
    }

def main():
    agents_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(agents_dir)
    output_dir = os.path.join(project_dir, "deep_agent_verification")
    os.makedirs(output_dir, exist_ok=True)

    secrets_dir = os.path.join(project_dir, ".secrets")
    g_key_path = os.path.join(secrets_dir, "gemini.key")
    or_key_path = os.path.join(secrets_dir, "openrouter.key")

    if not os.path.exists(g_key_path) or not os.path.exists(or_key_path):
        print("[CRITICAL] API keys missing in .secrets/")
        sys.exit(1)

    with open(g_key_path, "r", encoding="utf-8") as f:
        g_key = f.read().strip()
    with open(or_key_path, "r", encoding="utf-8") as f:
        or_key = f.read().strip()

    print("=" * 65)
    print(" STARTING MULTI-AI AGENT VERIFICATION (3-Model Robotics Panel)")
    print("=" * 65)

    summary = []
    for idx, name in enumerate(CANDIDATES):
        path = os.path.join(agents_dir, name)
        if not os.path.exists(path):
            print(f"[{idx+1}/{len(CANDIDATES)}] Skipping {name} (Not found)")
            continue
        print(f"\n[{idx+1}/{len(CANDIDATES)}] Auditing {name}...")
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        
        # Guard against empty files
        if len(content.strip()) < 10:
            print(f"    [WARN] {name} is empty, skipping.")
            continue

        verdict_data = analyze_agent(name, content, g_key, or_key)
        
        # Save per-agent detail
        agent_out = os.path.join(output_dir, f"{name}_verdict.json")
        with open(agent_out, "w", encoding="utf-8") as f:
            json.dump(verdict_data, f, indent=2, ensure_ascii=False)
        
        summary.append((name, verdict_data))
        print(f"    [RESULT] Verdict: {verdict_data['verdict']} | Conf: {verdict_data['confidence']}%")

    # Generate FINAL_VERDICT.md
    md_path = os.path.join(output_dir, "FINAL_VERDICT.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Consolidated Multi-Agent Verification Report\n\n")
        f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write("Panel: Gemini-Robotics-ER-2 + Gemini-3.5-Flash + Nemotron-3.5-Lightning\n\n")
        f.write("| Agent Name | Verdict | Confidence | Rationale |\n")
        f.write("|---|---|---|---|\n")
        for name, data in summary:
            rat = data["rationale"].replace("|", "\\|")
            f.write(f"| {name} | {data['verdict']} | {data['confidence']}% | {rat} |\n")
        
        f.write("\n\n## Detailed Research Impacts\n\n")
        for name, data in summary:
            f.write(f"### {name}\n")
            f.write(f"**Verdict:** {data['verdict']} ({data['confidence']}%)\n\n")
            f.write(f"**Research Impact:** {data['research_impact']}\n\n")
            f.write("**Strengths:**\n")
            for s in data["strengths"]: f.write(f"- {s}\n")
            f.write("\n**Concerns:**\n")
            for c in data["concerns"]: f.write(f"- {c}\n")
            f.write("\n---\n\n")

    print("\n" + "=" * 65)
    print(f" ALL AUDITS COMPLETED. Consolidated report saved to: {md_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
