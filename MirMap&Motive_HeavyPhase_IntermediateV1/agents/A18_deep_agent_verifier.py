import os
import sys
import json
import time
import urllib.request
import urllib.error
import re
from collections import Counter

CANDIDATES = [
    "auto_labeler.py", "label_registry_auto.py", "slam_to_bev.py",
    "slam_map_annotator.py", "vla_dataset_builder.py", "qwen_dataset_formatter.py",
    "co_pilot_agent.py", "video_narrator.py", "video_learning_agent.py",
    "video_event_extractor.py", "training_curriculum_advisor.py",
    "vla_supervisor_agent.py", "video_quality_agent.py", "cvat_converter.py",
    "offline_processor.py", "cross_modal_aligner.py", "robot_data_analyzer.py",
    "scene_object_detector.py", "launch_session.py"
]

MAX_CONTENT_CHARS = 4000

# ── Local models for quorum (all on LM Studio :1234) ──
LOCAL_MODELS = [
    "qwen3.6-27b",
    "qwen/qwen3-vl-30b",
    "qwen3-30b-a3b-thinking-2507"
]

def extract_json(text):
    """Defensive JSON parser with CoT suppression and nested brace balancing."""
    if not text or not isinstance(text, str):
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"Thinking Process:.*?(?=\{)", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<\|channel\|>analysis<\|message\|>.*?<\|end\|>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
        depth = 0
        for i, ch in enumerate(cleaned[first_brace:], first_brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                candidate = cleaned[first_brace:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\{[^{}]*\"verdict\"[^{}]*\})", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None

def query_lmstudio(model_name, prompt, retries=2):
    """Query local LM Studio model via OpenAI-compatible API."""
    url = "http://localhost:1234/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a strict robotics code referee. Return ONLY valid JSON. No thinking, no reasoning, no explanation. No <think> tags. Single JSON object only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content_text = result["choices"][0]["message"]["content"]
            if content_text and content_text.strip():
                return content_text
            print(f"    [RETRY {attempt+1}] {model_name}: empty content")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            print(f"    [RETRY {attempt+1}] {model_name}: HTTP {e.code}: {body[:120]}")
        except Exception as e:
            print(f"    [RETRY {attempt+1}] {model_name}: {type(e).__name__}: {str(e)[:80]}")
        if attempt < retries:
            time.sleep(2)
    return None

def analyze_agent(name, content):
    """Audit one agent using 3 local LLMs and aggregate votes."""
    truncated = content[:MAX_CONTENT_CHARS]
    if len(content) > MAX_CONTENT_CHARS:
        truncated += "\n\n[... TRUNCATED - total " + str(len(content)) + " chars ...]"

    ref_prompt = (
        "You are a senior robotics safety auditor for the MiR100 VLA project at Politecnico di Torino.\n"
        "The system uses Qwen3-VL with LoRA to predict [v,w] from BEV+LiDAR+Video+MoCap fusion.\n"
        "CRITICAL SAFETY LIMITS: v_max=1.5 m/s, w_max=1.0 rad/s, human_proximity=1.2m, e_stop=mandatory.\n"
        "Audit this agent code on 5 dimensions:\n"
        "  D1-SAFETY: velocity clamping, collision avoidance, e-stop logic, watchdog, human proximity\n"
        "  D2-VLA: multi-modal fusion correctness, BEV generation, sensor sync, temporal alignment\n"
        "  D3-RESEARCH: reproducibility, session-disjoint eval readiness, ablation hooks, Q1 standards\n"
        "  D4-ROBUSTNESS: error handling, timeout recovery, fallback paths, edge cases, type safety\n"
        "  D5-INTEGRATION: ROS topic correctness, coordinate frame consistency, latency budget\n"
        "Respond with pure JSON only (no markdown, no explanation outside JSON):\n"
        '{"verdict":"PASS|FAIL|WARN","confidence":0-100,'
        '"scores":{"safety":0-20,"vla":0-20,"research":0-20,"robustness":0-20,"integration":0-20},'
        '"rationale":"2-3 sentences with specific line references",'
        '"strengths":["specific finding 1","specific finding 2"],'
        '"concerns":["specific risk 1","specific risk 2"],'
        '"research_impact":"How this affects IEEE T-RO/IJRR acceptability (2 sentences)"}\n\n'
        f"File: {name}\nSource:\n{truncated}"
    )

    votes = []
    strengths, concerns, rationales, impacts, confidences = [], [], [], [], []

    for model_id in LOCAL_MODELS:
        time.sleep(1)
        raw = query_lmstudio(model_id, ref_prompt)
        parsed = extract_json(raw)
        if parsed and "verdict" in parsed:
            v = str(parsed["verdict"]).upper()
            if v in ("PASS", "FAIL"):
                votes.append(v)
                confidences.append(int(parsed.get("confidence", 70)))
                rationales.append(f"[{model_id}]: {parsed.get('rationale','')}")
                strengths.extend(parsed.get("strengths", []))
                concerns.extend(parsed.get("concerns", []))
                if parsed.get("research_impact"):
                    impacts.append(parsed["research_impact"])
                print(f"    -> {model_id:<38} {v} ({parsed.get('confidence')}%)")
                continue
        print(f"    -> {model_id:<38} INVALID/None")

    if len(votes) < 2:
        return {"verdict": "INSUFFICIENT_QUORUM", "confidence": 0,
                "rationale": f"Only {len(votes)}/3 models returned valid audits.",
                "strengths": [], "concerns": [], "research_impact": "Audit incomplete."}

    majority = Counter(votes).most_common(1)[0][0]
    return {
        "verdict": majority,
        "confidence": sum(confidences) // len(confidences),
        "rationale": " | ".join(rationales),
        "strengths": list(set(strengths))[:5],
        "concerns": list(set(concerns))[:5],
        "research_impact": " ".join(set(impacts))[:500]
    }

def warmup_lmstudio():
    """Pre-load LM Studio to reduce cold-start latency."""
    try:
        urllib.request.urlopen("http://localhost:1234/v1/models", timeout=5)
    except Exception:
        pass

warmup_lmstudio()

def main():
    agents_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(agents_dir)
    output_dir = os.path.join(project_dir, "deep_agent_verification")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print(" LOCAL-ONLY MULTI-AI VERIFICATION")
    print(" Models: qwen3.6-27b | qwen3-vl-30b | qwen3-30b-thinking")
    print(" Server: LM Studio localhost:1234")
    print("=" * 65)

    summary = []
    for idx, name in enumerate(CANDIDATES):
        path = os.path.join(agents_dir, name)
        if not os.path.exists(path):
            print(f"[{idx+1}/{len(CANDIDATES)}] Skip {name} (missing)")
            continue
        print(f"\n[{idx+1}/{len(CANDIDATES)}] Auditing {name}...")
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        if len(content.strip()) < 10:
            print("    [WARN] Empty file, skipping.")
            continue

        verdict_data = analyze_agent(name, content)

        agent_out = os.path.join(output_dir, f"{name}_verdict.json")
        with open(agent_out, "w", encoding="utf-8") as f:
            json.dump(verdict_data, f, indent=2, ensure_ascii=False)

        summary.append((name, verdict_data))
        print(f"    [RESULT] {verdict_data['verdict']} | {verdict_data['confidence']}%")

    md_path = os.path.join(output_dir, "FINAL_VERDICT.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Local-Only Multi-Agent Verification Report\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Panel: qwen3.6-27b + qwen3-vl-30b + qwen3-30b-thinking (LM Studio)\n\n")
        f.write("| Agent | Verdict | Conf | Rationale |\n|---|---|---|---|\n")
        for name, d in summary:
            rat = d["rationale"].replace("|", "/")[:120]
            f.write(f"| {name} | {d['verdict']} | {d['confidence']}% | {rat} |\n")
        f.write("\n## Research Impacts\n\n")
        for name, d in summary:
            f.write(f"### {name}\n**{d['verdict']}** ({d['confidence']}%)\n")
            f.write(f"{d['research_impact']}\n\n")

    print(f"\n{'='*65}")
    print(f" DONE. Report: {md_path}")
    print(f"{'='*65}")

if __name__ == "__main__":
    main()