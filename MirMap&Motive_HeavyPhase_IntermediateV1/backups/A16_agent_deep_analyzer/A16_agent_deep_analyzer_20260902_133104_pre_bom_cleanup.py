#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A16_agent_deep_analyzer.py — Intelligent Multi-AI Agent Analyzer v1.0

PURPOSE:
    Reads ALL agent files in the project, analyzes their purpose, quality,
    and relevance to the thesis goal (Q1 paper on Qwen-VL VLA for MiR100),
    then consults multiple AI models (Claude, Grok, Gemini) for consensus
    on what to fix, merge, or delete.

CONNECTS TO:
    1. Anthropic Claude (claude-sonnet-4-20250514)
    2. xAI Grok (grok-3)
    3. Google Gemini Pro (gemini-2.5-pro)
    4. OpenRouter (fallback)

OUTPUTS:
    - agents/analysis_report/agent_audit_TIMESTAMP.json
    - agents/analysis_report/agent_audit_TIMESTAMP.md
    - Console summary with color-coded recommendations
"""

import os
import sys
import json
import glob
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# API CONFIGURATION — Fill in your keys
# ============================================================

API_KEYS = {
    "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
    "xai": os.environ.get("XAI_API_KEY", ""),
    "google": os.environ.get("GOOGLE_API_KEY", ""),  # Gemini Pro
    "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
}

# Check which APIs are available
def check_api_availability():
    available = {}
    missing = []
    for name, key in API_KEYS.items():
        if key and len(key) > 10:
            available[name] = True
            logger.info(f"  API [{name}]: AVAILABLE")
        else:
            available[name] = False
            missing.append(name)
            logger.warning(f"  API [{name}]: MISSING KEY")
    
    if missing:
        logger.warning(
            f"\n  MISSING API KEYS: {missing}\n"
            f"  Set environment variables:\n"
            f"    $env:ANTHROPIC_API_KEY = 'sk-ant-...'\n"
            f"    $env:XAI_API_KEY = 'xai-...'\n"
            f"    $env:GOOGLE_API_KEY = 'AIza...'\n"
            f"    $env:OPENROUTER_API_KEY = 'sk-or-...'\n"
        )
    
    return available


# ============================================================
# AI CLIENT WRAPPERS
# ============================================================

def query_claude(prompt: str, system: str = "", max_tokens: int = 4000) -> Optional[str]:
    """Query Anthropic Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEYS["anthropic"])
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system if system else "You are a senior robotics software architect reviewing agent code for a Q1 publication.",
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        logger.error(f"Claude query failed: {e}")
        return None


def query_grok(prompt: str, system: str = "", max_tokens: int = 4000) -> Optional[str]:
    """Query xAI Grok API."""
    try:
        import openai
        client = openai.OpenAI(
            api_key=API_KEYS["xai"],
            base_url="https://api.x.ai/v1"
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        resp = client.chat.completions.create(
            model="grok-3",
            messages=messages,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Grok query failed: {e}")
        return None


def query_gemini(prompt: str, system: str = "", max_tokens: int = 4000) -> Optional[str]:
    """Query Google Gemini Pro API."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEYS["google"])
        model = genai.GenerativeModel(
            "gemini-2.5-pro",
            system_instruction=system if system else "You are a senior robotics software architect."
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini query failed: {e}")
        return None


def query_openrouter(prompt: str, system: str = "", max_tokens: int = 4000) -> Optional[str]:
    """Query OpenRouter API (fallback)."""
    try:
        import openai
        client = openai.OpenAI(
            api_key=API_KEYS["openrouter"],
            base_url="https://openrouter.ai/api/v1"
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        resp = client.chat.completions.create(
            model="openrouter/auto",
            messages=messages,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenRouter query failed: {e}")
        return None


def query_all_models(prompt: str, system: str = "") -> Dict[str, Optional[str]]:
    """Query all available models and return responses."""
    available = check_api_availability()
    responses = {}
    
    model_funcs = {
        "anthropic": query_claude,
        "xai": query_grok,
        "google": query_gemini,
        "openrouter": query_openrouter,
    }
    
    for name, func in model_funcs.items():
        if available.get(name, False):
            logger.info(f"  Querying {name}...")
            start = time.time()
            resp = func(prompt, system)
            elapsed = time.time() - start
            responses[name] = {
                "response": resp,
                "elapsed_s": round(elapsed, 2),
                "success": resp is not None
            }
            logger.info(f"  {name}: {'OK' if resp else 'FAILED'} ({elapsed:.1f}s)")
        else:
            responses[name] = {"response": None, "elapsed_s": 0, "success": False}
    
    return responses


# ============================================================
# AGENT FILE SCANNER
# ============================================================

def scan_agent_files(agents_dir: str) -> List[Dict]:
    """Scan all Python files in agents directory and extract metadata."""
    agents = []
    
    for py_file in sorted(glob.glob(os.path.join(agents_dir, "*.py"))):
        filename = os.path.basename(py_file)
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Cannot read {filename}: {e}")
            continue
        
        lines = content.split('\n')
        
        # Extract metadata
        agent_info = {
            "filename": filename,
            "filepath": py_file,
            "lines": len(lines),
            "size_bytes": os.path.getsize(py_file),
            "sha256": hashlib.sha256(content.encode()).hexdigest()[:16],
            "imports": [],
            "functions": [],
            "classes": [],
            "docstring": "",
            "has_main": "__main__" in content or "if __name__" in content,
            "has_logging": "logging" in content or "logger" in content,
            "has_api_calls": any(kw in content for kw in ["requests.", "openai.", "anthropic.", "genai."]),
            "has_file_io": any(kw in content for kw in ["pickle.load", "json.load", "open(", "pd.read"]),
            "has_numpy": "numpy" in content or "np." in content,
            "has_yolo": "YOLO" in content or "ultralytics" in content,
            "has_ros": "rospy" in content or "rclpy" in content or "cmd_vel" in content,
            "references_slam": "slam" in content.lower(),
            "references_mocap": "mocap" in content.lower() or "optitrack" in content.lower(),
            "references_qwen": "qwen" in content.lower() or "vla" in content.lower(),
            "first_100_lines": '\n'.join(lines[:100]),
            "last_20_lines": '\n'.join(lines[-20:]),
        }
        
        # Extract imports
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                agent_info["imports"].append(stripped)
        
        # Extract function names
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def "):
                func_name = stripped.split("(")[0].replace("def ", "")
                agent_info["functions"].append(func_name)
        
        # Extract class names
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("class "):
                class_name = stripped.split("(")[0].split(":")[0].replace("class ", "")
                agent_info["classes"].append(class_name)
        
        # Extract docstring
        if '"""' in content:
            try:
                first_doc = content.split('"""')[1]
                agent_info["docstring"] = first_doc[:500]
            except IndexError:
                pass
        
        agents.append(agent_info)
    
    return agents


# ============================================================
# SESSION ANALYZER
# ============================================================

def analyze_session_quality(session_dir: str) -> Dict:
    """Analyze a single session's data quality and completeness."""
    result = {
        "session_dir": session_dir,
        "session_name": os.path.basename(session_dir),
        "files_present": {},
        "quality_checks": {},
        "issues": [],
        "recommendations": []
    }
    
    # Check required files
    required_files = {
        "slam_data.pkl": "SLAM trajectory data",
        "mocap_data.pkl": "OptiTrack MoCap human tracking",
        "yolo_results.json": "YOLO object detections",
        "camera_frames/": "IR camera frames directory",
        "bev_images/": "Bird's Eye View rendered images",
    }
    
    for fname, desc in required_files.items():
        path = os.path.join(session_dir, fname)
        exists = os.path.exists(path)
        result["files_present"][fname] = exists
        if not exists:
            result["issues"].append(f"MISSING: {fname} ({desc})")
    
    # Check SLAM data quality
    slam_path = os.path.join(session_dir, "slam_data.pkl")
    if os.path.exists(slam_path):
        try:
            import pickle
            import numpy as np
            with open(slam_path, 'rb') as f:
                slam = pickle.load(f)
            
            if isinstance(slam, dict):
                result["quality_checks"]["slam_keys"] = list(slam.keys())
                
                # Check for timestamps
                ts_key = None
                for k in ["timestamps", "t", "time", "timestamp"]:
                    if k in slam:
                        ts_key = k
                        break
                
                if ts_key:
                    ts = np.asarray(slam[ts_key])
                    result["quality_checks"]["slam_n_frames"] = len(ts)
                    result["quality_checks"]["slam_duration_s"] = float(ts[-1] - ts[0]) if len(ts) > 1 else 0
                    result["quality_checks"]["slam_fps"] = len(ts) / max(1e-6, float(ts[-1] - ts[0])) if len(ts) > 1 else 0
                    
                    # Check monotonicity
                    dt = np.diff(ts)
                    n_backward = int(np.sum(dt <= 0))
                    if n_backward > 0:
                        result["issues"].append(f"SLAM has {n_backward} non-monotonic timestamps!")
                else:
                    result["issues"].append("SLAM data has no timestamp field!")
        except Exception as e:
            result["issues"].append(f"Cannot parse slam_data.pkl: {e}")
    
    # Check MoCap data quality
    mocap_path = os.path.join(session_dir, "mocap_data.pkl")
    if os.path.exists(mocap_path):
        try:
            import pickle
            import numpy as np
            with open(mocap_path, 'rb') as f:
                mocap = pickle.load(f)
            
            if isinstance(mocap, dict):
                result["quality_checks"]["mocap_keys"] = list(mocap.keys())
        except Exception as e:
            result["issues"].append(f"Cannot parse mocap_data.pkl: {e}")
    
    # Check YOLO results
    yolo_path = os.path.join(session_dir, "yolo_results.json")
    if os.path.exists(yolo_path):
        try:
            with open(yolo_path, 'r') as f:
                yolo = json.load(f)
            
            if isinstance(yolo, list):
                result["quality_checks"]["yolo_n_frames"] = len(yolo)
            elif isinstance(yolo, dict):
                result["quality_checks"]["yolo_keys"] = list(yolo.keys())
        except Exception as e:
            result["issues"].append(f"Cannot parse yolo_results.json: {e}")
    
    # Check BEV images
    bev_dir = os.path.join(session_dir, "bev_images")
    if os.path.exists(bev_dir):
        bev_pngs = glob.glob(os.path.join(bev_dir, "*.png"))
        result["quality_checks"]["bev_count"] = len(bev_pngs)
        if len(bev_pngs) < 50:
            result["issues"].append(f"Only {len(bev_pngs)} BEV images (minimum 50 recommended)")
    
    return result


# ============================================================
# MAIN ANALYSIS PIPELINE
# ============================================================

def build_analysis_prompt(agents: List[Dict], sessions_analysis: List[Dict]) -> str:
    """Build the comprehensive prompt for AI analysis."""
    
    prompt = """# COMPREHENSIVE AGENT AUDIT FOR Q1 THESIS PUBLICATION

## THESIS GOAL
Fine-tune Qwen-VL (Vision-Language-Action model) for safe autonomous navigation
of MiR100 mobile robot in human-occupied industrial environments.
The system uses SLAM + YOLO + OptiTrack MoCap data fusion.

## KNOWN CRITICAL BUGS (confirmed by 9/10 AI referees):
- BUG-A: Robot frozen on SLAM map while human moves (sync failure)
- BUG-B: YOLO mislabels humans as chairs, robots as persons
- BUG-C: Computed max velocity = 9.13 m/s (physical limit is 1.5 m/s)
- BUG-D: R²_w = 0.134 (angular velocity regression worthless)
- BUG-E: Only 344 frames from ONE session (severe overfitting risk)
- BUG-F: Only 3 rotation validation samples (no statistical power)
- BUG-G: Self-score 88.5/100 is circular validation

## YOUR TASK
For EACH agent file listed below, provide:
1. VERDICT: KEEP / FIX / MERGE / DELETE
2. REASON: Why this verdict (1-2 sentences)
3. BUG_LINK: Which bugs (A-G) does this file contribute to?
4. FIX_PRIORITY: 1 (urgent) / 2 (important) / 3 (nice-to-have) / 0 (delete)
5. MERGE_TARGET: If merging, which file should absorb this one?
6. MISSING_STANDARDS: What Q1 publication standards does this file violate?

Format your response as a JSON array of objects.

## AGENT FILES TO ANALYZE:

"""
    
    for i, agent in enumerate(agents):
        prompt += f"\n### Agent {i+1}: {agent['filename']}\n"
        prompt += f"- Lines: {agent['lines']}\n"
        prompt += f"- Functions: {agent['functions']}\n"
        prompt += f"- Classes: {agent['classes']}\n"
        prompt += f"- Has YOLO: {agent['has_yolo']}\n"
        prompt += f"- Has ROS: {agent['has_ros']}\n"
        prompt += f"- Has NumPy: {agent['has_numpy']}\n"
        prompt += f"- Has API calls: {agent['has_api_calls']}\n"
        prompt += f"- References SLAM: {agent['references_slam']}\n"
        prompt += f"- References MoCap: {agent['references_mocap']}\n"
        prompt += f"- References Qwen/VLA: {agent['references_qwen']}\n"
        prompt += f"- Docstring: {agent['docstring'][:200]}\n"
        prompt += f"- First 50 lines:\n```python\n{chr(10).join(agent['first_100_lines'].split(chr(10))[:50])}\n```\n"
    
    if sessions_analysis:
        prompt += "\n## SESSION QUALITY ANALYSIS:\n"
        for sess in sessions_analysis:
            prompt += f"\n### {sess['session_name']}\n"
            prompt += f"- Files: {json.dumps(sess['files_present'])}\n"
            prompt += f"- Quality: {json.dumps(sess.get('quality_checks', {}))}\n"
            prompt += f"- Issues: {sess['issues']}\n"
    
    return prompt


def run_full_analysis():
    """Main entry point: scan agents, analyze sessions, query AIs, produce report."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_root = Path(__file__).parent.parent
    agents_dir = str(Path(__file__).parent)
    sessions_dir = str(project_root / "sessions")
    report_dir = str(Path(__file__).parent / "analysis_report")
    os.makedirs(report_dir, exist_ok=True)
    
    print("=" * 70)
    print(f" A16 DEEP AGENT ANALYZER — {timestamp}")
    print("=" * 70)
    
    # Step 1: Check API availability
    print("\n[1/5] Checking API connections...")
    available = check_api_availability()
    n_apis = sum(1 for v in available.values() if v)
    print(f"  {n_apis}/4 APIs available")
    
    if n_apis == 0:
        print("\n  NO API KEYS FOUND!")
        print("  Please set at least one of these environment variables:")
        print("    $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
        print("    $env:XAI_API_KEY = 'xai-...'")
        print("    $env:GOOGLE_API_KEY = 'AIza...'")
        print("    $env:OPENROUTER_API_KEY = 'sk-or-...'")
        print("\n  Or enter them now:")
        
        for name in ["ANTHROPIC_API_KEY", "XAI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"]:
            if not os.environ.get(name):
                val = input(f"    {name} (press Enter to skip): ").strip()
                if val:
                    os.environ[name] = val
                    API_KEYS[name.split("_")[0].lower()] = val
        
        available = check_api_availability()
        n_apis = sum(1 for v in available.values() if v)
    
    # Step 2: Scan agent files
    print(f"\n[2/5] Scanning agent files in {agents_dir}...")
    agents = scan_agent_files(agents_dir)
    print(f"  Found {len(agents)} Python files")
    for a in agents:
        print(f"    {a['filename']:40s} {a['lines']:5d} lines  funcs={len(a['functions'])}  classes={len(a['classes'])}")
    
    # Step 3: Analyze sessions
    print(f"\n[3/5] Analyzing sessions in {sessions_dir}...")
    sessions_analysis = []
    if os.path.exists(sessions_dir):
        for sess_dir in sorted(glob.glob(os.path.join(sessions_dir, "session_*"))):
            analysis = analyze_session_quality(sess_dir)
            sessions_analysis.append(analysis)
            n_issues = len(analysis['issues'])
            status = "OK" if n_issues == 0 else f"{n_issues} ISSUES"
            print(f"    {analysis['session_name']}: {status}")
    else:
        print("  No sessions directory found!")
    
    # Step 4: Build prompt and query AIs
    print(f"\n[4/5] Building analysis prompt and querying AI models...")
    system_prompt = """You are a senior robotics software architect and Q1 journal reviewer.
You are auditing a thesis project that fine-tunes Qwen-VL for MiR100 robot navigation.
The project has 7 confirmed critical bugs (BUG-A through BUG-G).
Your job is to analyze each agent file and determine:
- Is it needed for the thesis goal?
- Does it contribute to any known bugs?
- Should it be KEPT, FIXED, MERGED with another file, or DELETED?
- What Q1 publication standards does it violate?
Be brutal but constructive. Give specific file:line references where possible.
Output valid JSON."""
    
    analysis_prompt = build_analysis_prompt(agents, sessions_analysis)
    
    # Query each available AI
    ai_responses = query_all_models(analysis_prompt, system_prompt)
    
    # Step 5: Compile report
    print(f"\n[5/5] Compiling final report...")
    
    report = {
        "timestamp": timestamp,
        "project": str(project_root),
        "n_agents": len(agents),
        "n_sessions": len(sessions_analysis),
        "apis_available": {k: v for k, v in available.items()},
        "agents": [{k: v for k, v in a.items() if k not in ['first_100_lines', 'last_20_lines']} for a in agents],
        "sessions": sessions_analysis,
        "ai_responses": ai_responses,
    }
    
    # Save JSON report
    json_path = os.path.join(report_dir, f"agent_audit_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"  JSON report: {json_path}")
    
    # Save Markdown summary
    md_path = os.path.join(report_dir, f"agent_audit_{timestamp}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# Agent Audit Report — {timestamp}\n\n")
        f.write(f"## Summary\n")
        f.write(f"- Total agents scanned: {len(agents)}\n")
        f.write(f"- Total sessions analyzed: {len(sessions_analysis)}\n")
        f.write(f"- APIs consulted: {n_apis}/4\n\n")
        
        f.write(f"## Agent List\n\n")
        f.write("| # | File | Lines | Functions | YOLO | ROS | SLAM | MoCap | VLA |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, a in enumerate(agents):
            f.write(f"| {i+1} | `{a['filename']}` | {a['lines']} | {len(a['functions'])} | "
                   f"{'Y' if a['has_yolo'] else ''} | {'Y' if a['has_ros'] else ''} | "
                   f"{'Y' if a['references_slam'] else ''} | {'Y' if a['references_mocap'] else ''} | "
                   f"{'Y' if a['references_qwen'] else ''} |\n")
        
        f.write(f"\n## AI Responses\n\n")
        for model_name, resp_data in ai_responses.items():
            f.write(f"### {model_name} ({resp_data.get('elapsed_s', '?')}s)\n\n")
            if resp_data.get('success') and resp_data.get('response'):
                f.write(f"```\n{resp_data['response'][:3000]}\n```\n\n")
            else:
                f.write("*No response or API unavailable*\n\n")
        
        f.write(f"\n## Session Quality\n\n")
        for sess in sessions_analysis:
            f.write(f"### {sess['session_name']}\n")
            f.write(f"- Files: {json.dumps(sess['files_present'])}\n")
            if sess['issues']:
                f.write(f"- **Issues:**\n")
                for issue in sess['issues']:
                    f.write(f"  - {issue}\n")
            f.write("\n")
    
    print(f"  Markdown report: {md_path}")
    
    # Print console summary
    print("\n" + "=" * 70)
    print(" ANALYSIS COMPLETE")
    print("=" * 70)
    
    successful_ais = [k for k, v in ai_responses.items() if v.get('success')]
    if successful_ais:
        print(f"\n  AI models consulted: {', '.join(successful_ais)}")
    
    print(f"\n  Reports saved to: {report_dir}")
    print(f"  JSON: agent_audit_{timestamp}.json")
    print(f"  Markdown: agent_audit_{timestamp}.md")
    
    return report


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    report = run_full_analysis()
