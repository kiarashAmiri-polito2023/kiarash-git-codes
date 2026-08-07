#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A15_referee_ai_loop.py v3.0 — Auto Model Discovery
Queries OpenRouter /models endpoint to find real free models.
No more guessing model names.
"""
import os, sys, json, glob, time, base64, ast, traceback
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

PROJECT   = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
KEY_FILE  = os.path.join(PROJECT, ".secrets", "openrouter.key")
API_URL   = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
OUT_DIR   = os.path.join(PROJECT, "audit_workspace")
MAX_CHARS = 15000
TIMEOUT   = 240

PROJECT_CONTEXT = """
PROJECT: MirMap&Motive - Semantic VLA for MiR100 Mobile Robot
STUDENT: Kiarash Amiri, PoliTo DIGEP, thesis project.
GOAL: Fine-tune Qwen-VL so MiR100 navigates safely among humans
      using SLAM + YOLO + OptiTrack MoCap synchronized data.
HARDWARE: MiR100 (max 1.5 m/s, max angular 1.0 rad/s),
          8x OptiTrack PrimeX cameras, RTX 3090 GPU.
DATA PIPELINE:
  session_N/ -> agents/ (40 Python files) -> slam_data.pkl, mocap_data.pkl,
  yolo_results.json -> generate_publication_report_v5.py -> Qwen-VL fine-tuning
CRITICAL BUGS KIARASH OBSERVED:
  BUG-A: Robot FROZEN on SLAM map while human MOVES on MoCap (sync failure)
  BUG-B: YOLO labels human as chair, robot as person (detection failure)
  BUG-C: max velocity = 9.13 m/s (MiR100 max is 1.5!) (calculation bug)
  BUG-D: R2_w = 0.134 (angular channel worthless)
  BUG-E: 344 frames from ONE session (overfit)
  BUG-F: Rotation class val n=3 (no statistical power)
  BUG-G: Self-score 88.5/100 (circular validation)
YOUR JOB: Hostile Q1 reviewer. Find every flaw, name exact file:line,
          give fixed code, give PowerShell patches, prescribe new sessions.
"""

PERSONAS = [
  {"id":"P1","name":"Data-Bug Explainer","vision":True,
   "focus":"Look at dashboard images. Robot SLAM vs human MoCap sync. Explain simply."},
  {"id":"P2","name":"Agent Code Auditor","vision":False,
   "focus":"Read agent source. Frozen vars, pinned [0] indices, coord bugs. Name file:line."},
  {"id":"P3","name":"YOLO Detection Skeptic","vision":True,
   "focus":"YOLO labels in images. Person vs chair confusion. Confidence threshold."},
  {"id":"P4","name":"Robotics Physicist","vision":False,
   "focus":"max 1.5 m/s vs reported 9.13. Wrong dt? Wrong sample rate? Find the file."},
  {"id":"P5","name":"Sync Detective","vision":True,
   "focus":"Frozen robot + moving human = timestamp sync bug. Which agent aligns them?"},
  {"id":"P6","name":"Qwen-VL Training Skeptic","vision":False,
   "focus":"Training data quality. Which agent builds dataset? Garbage in = garbage out."},
  {"id":"P7","name":"Redundant-Agent Hunter","vision":False,
   "focus":"40 agents. Which overlap? Which are dead? Propose clean architecture."},
  {"id":"P8","name":"New-Sequence Prescriber","vision":False,
   "focus":"Prescribe 5-10 new sessions with exact params to fix data gaps."},
  {"id":"P9","name":"PowerShell-Patch Generator","vision":False,
   "focus":"Write ready-to-paste PowerShell patches for RemoteDaily for each bug."},
  {"id":"P10","name":"Consensus Judge","vision":True,
   "focus":"Synthesize all. Final verdict. Most urgent fix. Will thesis pass defense?"},
]

def load_key():
    with open(KEY_FILE, "r", encoding="utf-8-sig") as f:
        return f.read().strip()

def discover_free_models():
    """Query OpenRouter API to find REAL free models."""
    import requests
    key = load_key()
    print("\n[DISCOVERY] Querying OpenRouter for free models...", flush=True)
    try:
        resp = requests.get(MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=30)
        if resp.status_code != 200:
            print(f"  [WARN] Models API returned {resp.status_code}", flush=True)
            return [], []
        models = resp.json().get("data", [])
        text_free = []
        vision_free = []
        for m in models:
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            prompt_price = pricing.get("prompt", "1")
            # Check if truly free (price = "0" as string)
            try:
                if float(prompt_price) > 0:
                    continue
            except:
                continue
            # Check context length (prefer larger)
            ctx = m.get("context_length", 4096)
            if ctx < 8000:
                continue
            # Check modality
            arch = m.get("architecture", {})
            modality = arch.get("modality", "text->text")
            name = m.get("name", mid)
            entry = {"id": mid, "ctx": ctx, "name": name}
            if "image" in modality.lower():
                vision_free.append(entry)
            else:
                text_free.append(entry)
        # Sort by context length (larger = smarter)
        text_free.sort(key=lambda x: x["ctx"], reverse=True)
        vision_free.sort(key=lambda x: x["ctx"], reverse=True)
        # Pick top models
        text_picks = text_free[:5]
        vision_picks = vision_free[:3]
        print(f"  Found {len(text_free)} free text models, {len(vision_free)} free vision models", flush=True)
        for t in text_picks:
            print(f"    TEXT:   {t['id']} (ctx={t['ctx']})", flush=True)
        for v in vision_picks:
            print(f"    VISION: {v['id']} (ctx={v['ctx']})", flush=True)
        if not text_picks and not vision_picks:
            print("  [WARN] No free models found! Check API key.", flush=True)
        return [t["id"] for t in text_picks], [v["id"] for v in vision_picks]
    except Exception as e:
        print(f"  [ERROR] Discovery failed: {e}", flush=True)
        return [], []

def read_safe(path, max_c=MAX_CHARS):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            txt = f.read()
        if len(txt) > max_c:
            txt = txt[:max_c] + f"\n...[TRUNCATED]..."
        return txt
    except Exception as e:
        return f"[READ ERROR: {e}]"

def find_files(pattern):
    return sorted(glob.glob(os.path.join(PROJECT, pattern), recursive=True))

def encode_image_b64(path, max_kb=200):
    try:
        from PIL import Image
        import io
        img = Image.open(path)
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=75)
        data = buf.getvalue()
        if len(data) > max_kb * 1024:
            img.thumbnail((640, 640))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=60)
            data = buf.getvalue()
        return base64.b64encode(data).decode("ascii")
    except:
        return None

def scan_agent_code():
    agents = find_files("agents/*.py")
    summary = []
    full = {}
    for a in agents:
        name = os.path.basename(a)
        try:
            with open(a, "r", encoding="utf-8-sig", errors="replace") as f:
                src = f.read()
            lines = src.count("\n")
            try:
                tree = ast.parse(src)
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            except:
                funcs, classes = [], []
            summary.append(f"  {name} ({lines}L, {len(funcs)}F, {len(classes)}C)")
            full[name] = src[:6000]
        except:
            summary.append(f"  {name} [ERROR]")
    return "\n".join(summary), full

def get_dashboard_images(n=3):
    runs = sorted(glob.glob(os.path.join(PROJECT, "Visual_Archives", "Run_*")), reverse=True)
    if not runs: return []
    imgs = []
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        imgs.extend(glob.glob(os.path.join(runs[0], "**", ext), recursive=True))
    imgs = sorted(imgs)
    if len(imgs) <= n: return imgs
    step = len(imgs) // n
    return [imgs[i*step] for i in range(n)]

def gather_data():
    d = {}
    mr = find_files("MASTER_REPORT.md") + find_files("Visual_Archives/Run_*/MASTER_REPORT.md")
    if mr: d["MASTER_REPORT"] = read_safe(mr[-1], 8000)
    for pat, key in [
        ("**/eval_results*.json", "EVAL"),
        ("**/training_history*.json", "TRAINING"),
        ("**/yolo_results*.json", "YOLO"),
    ]:
        files = find_files(pat)
        if files:
            d[key] = "\n---\n".join(f"[{os.path.basename(f)}]\n{read_safe(f,3000)}" for f in files[:3])
    gen = find_files("generate_publication_report*.py")
    if gen: d["GENERATOR"] = read_safe(gen[-1], 10000)
    return d

def call_ai(system, user_content, text_models, vision_models, need_vision=False):
    key = load_key()
    pool = vision_models if (need_vision and vision_models) else text_models
    if not pool:
        pool = text_models if text_models else vision_models
    if not pool:
        return None, None
    import requests
    for model in pool:
        try:
            messages = [{"role":"system","content":system},
                        {"role":"user","content":user_content}]
            resp = requests.post(API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://polito.it/mirmap",
                    "X-Title": "A15-Referee"
                },
                json={"model": model, "max_tokens": 4096, "messages": messages},
                timeout=TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"], model
            else:
                print(f"    {model} -> HTTP {resp.status_code}", flush=True)
                continue
        except Exception as e:
            print(f"    {model} -> {e}", flush=True)
            continue
    return None, None

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = os.path.join(OUT_DIR, f"run_{ts}")
    os.makedirs(run_dir, exist_ok=True)

    print("=" * 72)
    print("  A15 REFEREE AI LOOP v3.0 — AUTO MODEL DISCOVERY")
    print(f"  {ts}")
    print("=" * 72, flush=True)

    # STEP 1: Discover real free models
    text_models, vision_models = discover_free_models()
    if not text_models and not vision_models:
        print("\n[FATAL] No free models available. Check your API key at openrouter.ai", flush=True)
        sys.exit(1)

    # STEP 2: Gather data
    print("\n[GATHER] Reading project files...", flush=True)
    data = gather_data()
    for k, v in data.items():
        print(f"    {k}: {len(v)} chars", flush=True)

    print("\n[SCAN] Reading all agents...", flush=True)
    agent_summary, agent_full = scan_agent_code()
    print(agent_summary, flush=True)

    print("\n[IMAGES] Loading dashboards...", flush=True)
    imgs = get_dashboard_images(3)
    for p in imgs:
        print(f"    {os.path.basename(p)}", flush=True)

    data_block = "\n\n".join(f"=== {k} ===\n{v}" for k, v in data.items())
    agent_block = "=== AGENTS ===\n" + agent_summary + "\n"
    for name, code in list(agent_full.items())[:10]:
        agent_block += f"\n--- {name} ---\n{code}\n"

    cumulative = ""
    results = []

    for i, persona in enumerate(PERSONAS):
        pn = i + 1
        print(f"\n{'#'*72}")
        print(f"  PASS {pn}/10 | {persona['name']} | vision={persona['vision']}")
        print(f"{'#'*72}", flush=True)

        system = (
            f"You are {persona['name']}, a hostile Q1 reviewer and kind teacher.\n"
            f"Focus: {persona['focus']}\n"
            f"Output sections: [WHAT] [EVIDENCE] [TEST] [FIX] [POWERSHELL] [SEQUENCES] [VERDICT]\n"
            f"Be brutal. Cite file:line. Give copy-paste code and PowerShell patches."
        )

        user_text = f"""{PROJECT_CONTEXT}

=== DATA ===
{data_block[:MAX_CHARS]}

=== AGENTS ===
{agent_block[:MAX_CHARS]}

=== PREVIOUS FINDINGS ===
{cumulative[-6000:] if cumulative else "(first pass)"}

=== TASK: Pass {pn}/10 as {persona['name']} ===
{persona['focus']}
Be specific. File names. Line numbers. Copy-paste fixes."""

        t0 = time.time()
        if persona["vision"] and imgs:
            content = [{"type":"text","text":user_text}]
            for p in imgs:
                b64 = encode_image_b64(p)
                if b64:
                    content.append({"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}})
            response, model = call_ai(system, content, text_models, vision_models, need_vision=True)
        else:
            response, model = call_ai(system, user_text, text_models, vision_models, need_vision=False)
        elapsed = time.time() - t0

        if response:
            print(f"  [OK] {model} ({elapsed:.0f}s, {len(response)} chars)", flush=True)
            print(f"  Preview: {response[:300].replace(chr(10),' ')}...", flush=True)
            cumulative += f"\n--- Pass {pn} ({persona['name']}) ---\n{response[:2000]}"
            results.append({"pass":pn,"persona":persona["name"],"model":model,
                          "time":elapsed,"response":response,"status":"OK"})
            with open(os.path.join(run_dir, f"pass_{pn:02d}.md"), "w", encoding="utf-8") as f:
                f.write(f"# Pass {pn}: {persona['name']}\nModel: {model}\n\n{response}")
        else:
            print(f"  [FAIL] Pass {pn} — all models failed", flush=True)
            results.append({"pass":pn,"persona":persona["name"],"model":"NONE",
                          "time":elapsed,"response":"","status":"FAIL"})

    # FINAL REPORT
    print(f"\n{'='*72}\n  Building final report...", flush=True)
    md = f"# FINAL REFEREE VERDICT v3.0\n**Date:** {ts}\n"
    md += f"**Models used:** {', '.join(set(r['model'] for r in results if r['model']!='NONE'))}\n\n"
    ok_count = len([r for r in results if r["status"]=="OK"])
    md += f"**Result:** {ok_count}/10 passes succeeded\n\n"
    for r in results:
        if r["response"]:
            md += f"---\n## PASS {r['pass']}: {r['persona']}\n**Model:** {r['model']} ({r['time']:.0f}s)\n\n{r['response']}\n\n"
    if ok_count == 0:
        md += "\n## [CRITICAL] ALL PASSES FAILED\nCheck API key and model availability.\n"

    final = os.path.join(run_dir, "FINAL_REFEREE_VERDICT.md")
    with open(final, "w", encoding="utf-8") as f: f.write(md)
    root_copy = os.path.join(PROJECT, "FINAL_REFEREE_VERDICT.md")
    with open(root_copy, "w", encoding="utf-8") as f: f.write(md)
    print(f"  Saved: {final}", flush=True)
    print(f"  Done: {ok_count}/10 passes OK", flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"\nFATAL: {e}", flush=True)
        traceback.print_exc()
