#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
project_snapshot.py — Intelligent AI Handoff System v4

New in v4:
  - Section 13: Deep agent code analysis (patterns, tools, concepts)
  - Section 14: Comparison framework with big tech pipelines
  - Section 15: Forced 3-4 layer AI reasoning prompts
  - Section 16: Paper-readiness checklist

Usage:
  python agents/project_snapshot.py
  Or double-click the file.

Outputs:
  reports/latest_snapshot_for_ai.md
  project_history/CHANGELOG.md
  project_history/latest_state.json
  project_history/snapshots/snapshot_<timestamp>.json
"""

import ast
import difflib
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


STATE_SCHEMA_VERSION = 4
MAX_SOURCE_DIFF_LINES = 160
MAX_HISTORY_DOCUMENT_CHARS = 120000
MAX_LATEST_REPORT_CHARS = 18000

HISTORY_EXTENSIONS = {".md", ".txt", ".rst"}
HISTORY_EXCLUDED_FILES = {
    "CHANGELOG.md",
    "latest_state.json",
    "run_count.txt",
}
HISTORY_EXCLUDED_DIRS = {"snapshots"}


ROADMAP = [
    {
        "step": 1,
        "name": "Fix Bug #7 — Zero Placeholder Filtering",
        "intent": "Prevent false Motive positions near (0,0,0) from contaminating fusion.",
        "evidence": [
            {"kind": "contains", "path": "agents/spatial_temporal_fusion.py",
             "marker": "motive_samples_skipped_zero_placeholder"},
            {"kind": "contains", "path": "agents/spatial_temporal_fusion.py",
             "marker": "zero_placeholder"},
        ],
    },
    {
        "step": 2,
        "name": "Human-in-the-Loop Merge System",
        "intent": "Never modify deep memory without explicit human approval.",
        "evidence": [
            {"kind": "path", "path": "agents/apply_merge.py"},
            {"kind": "contains", "path": "agents/knowledge_engine.py", "marker": "SAFE"},
            {"kind": "contains", "path": "agents/quality_gate.py", "marker": "Learning Progress"},
        ],
    },
    {
        "step": 3,
        "name": "Persistent Label Registry",
        "intent": "Share confirmed object names across Motive and SLAM sessions.",
        "evidence": [
            {"kind": "any_path", "paths": ["agents/label_registry.py",
                                            "agents/persistent_label_registry.py"]},
            {"kind": "path", "path": "persistent_knowledge/label_registry.pkl"},
        ],
    },
    {
        "step": 4,
        "name": "SLAM Map Annotator and Map-Video Renderer",
        "intent": "Auto-cluster obstacles, render map video and let the user confirm names.",
        "evidence": [
            {"kind": "path", "path": "agents/slam_map_annotator.py"},
            {"kind": "contains", "path": "agents/slam_map_annotator.py", "marker": "DBSCAN"},
        ],
    },
    {
        "step": 5,
        "name": "Motive Video Annotation (CVAT-based)",
        "intent": "Use CVAT + auto-labeler instead of building annotation tool from scratch.",
        "evidence": [
            {"kind": "any_path", "paths": ["agents/cvat_converter.py",
                                            "agents/motive_video_annotator.py"]},
            {"kind": "any_path", "paths": ["agents/auto_labeler.py"]},
        ],
    },
    {
        "step": 6,
        "name": "Cross-Modal Aligner",
        "intent": "Suggest probabilistic Motive-to-SLAM label matches using Hungarian algorithm.",
        "evidence": [
            {"kind": "any_path", "paths": ["agents/cross_modal_aligner.py",
                                            "agents/cross_reference_engine.py"]},
        ],
    },
    {
        "step": 7,
        "name": "Unified Session Report Integration",
        "intent": "Combine fusion, knowledge, quality, both annotators and cross-reference results.",
        "evidence": [
            {"kind": "contains", "path": "agents/run_session_analysis.py",
             "marker": "session_comprehensive_report"},
            {"kind": "contains", "path": "agents/launch_session.py",
             "marker": "label_registry_auto"},
            {"kind": "contains", "path": "agents/launch_session.py",
             "marker": "cross_modal_aligner"},
        ],
    },
    {
        "step": 8,
        "name": "Robot Command and Decision History Importer",
        "intent": "Learn robot intent from velocity commands, safety overrides and decisions.",
        "evidence": [
            {"kind": "path", "path": "agents/robot_command_history_importer.py"},
        ],
    },
    {
        "step": 9,
        "name": "Dual-Mode AI Advisor",
        "intent": "Provide Session Review and Deep Memory Reflection every session.",
        "evidence": [
            {"kind": "path", "path": "agents/ai_advisor.py"},
        ],
    },
    {
        "step": 10,
        "name": "VLA Dataset Builder",
        "intent": "Create synchronized Vision-Language-Action training records for QwenVLA.",
        "evidence": [
            {"kind": "path", "path": "agents/vla_dataset_builder.py"},
        ],
    },
]


AGENT_PLANS = {
    "NatNetClient.py": {"category": "Vendor SDK",
        "current": "Low-level NatNet network client.",
        "future": "Keep isolated; do not add project business logic."},
    "DataDescriptions.py": {"category": "Vendor SDK",
        "current": "NatNet model-description data structures.",
        "future": "Remain unchanged unless SDK compatibility requires it."},
    "MoCapData.py": {"category": "Vendor SDK",
        "current": "NatNet motion-capture frame data structures.",
        "future": "Remain unchanged unless SDK compatibility requires it."},
    "motive_connector.py": {"category": "Runtime connector",
        "current": "The only module allowed to access NatNet directly.",
        "future": "Expose safe live Motive metadata; never own the MiR API."},
    "launch_session.py": {"category": "Session orchestrator",
        "current": "Coordinates live session acquisition and Motive recording.",
        "future": "Offer an optional post-session annotation prompt with default=no."},
    "spatial_temporal_fusion.py": {"category": "Fusion agent",
        "current": "Combines Motive and SLAM observations in the MiR coordinate frame.",
        "future": "Add synchronized robot command/decision observations."},
    "knowledge_engine.py": {"category": "Learning agent",
        "current": "Builds safe pending cumulative-memory candidates.",
        "future": "Enrich VLA language/action labels without direct auto-merge."},
    "quality_gate.py": {"category": "Quality agent",
        "current": "Generates flags and Learning Progress Score.",
        "future": "Remain advisory; never become an automatic merge judge."},
    "apply_merge.py": {"category": "Human approval",
        "current": "Backs up and merges a candidate only after explicit yes.",
        "future": "Support audited rollback and optional AI recommendation display."},
    "run_session_analysis.py": {"category": "Analysis orchestrator",
        "current": "Runs fusion, safe knowledge analysis and quality reporting.",
        "future": "Integrate Motive/SLAM annotation and cross-reference report sections."},
    "co_pilot_agent.py": {"category": "Reporting assistant",
        "current": "Produces post-session assistance and reports.",
        "future": "Consume unified reports and avoid duplicating the AI Advisor."},
    "session_manager.py": {"category": "Project/session manager",
        "current": "Creates sessions and inspects persistent environment knowledge.",
        "future": "Keep session lifecycle separate from AI handoff history."},
    "project_snapshot.py": {"category": "Project history",
        "current": "Builds persistent AI handoff snapshots and exact diffs.",
        "future": "Use project_history documents as the semantic source of truth."},
    "inspect_motive_pipeline.py": {"category": "Diagnostic utility",
        "current": "Inspects Motive/AVI/CSV acquisition paths.",
        "future": "Remain diagnostic; do not become production annotation logic."},
    "label_registry.py": {"category": "Label management",
        "current": "Persistent cross-source registry of environment objects.",
        "future": "Support automatic conflict resolution suggestions."},
    "label_registry_auto.py": {"category": "Label management",
        "current": "Auto-checks and imports new labels after each session.",
        "future": "Integrate with taxonomy versioning."},
    "cvat_converter.py": {"category": "Annotation bridge",
        "current": "Converts CVAT exports to project JSONL format.",
        "future": "Support multi-camera batch conversion."},
    "auto_labeler.py": {"category": "AI-assisted labeling",
        "current": "Pre-labels videos using Grounding DINO.",
        "future": "Add SAM2 for segmentation masks."},
    "cross_modal_aligner.py": {"category": "Cross-modal fusion",
        "current": "Matches Motive to SLAM using Hungarian algorithm.",
        "future": "Add trajectory-based similarity."},
    "offline_processor.py": {"category": "Standalone processor",
        "current": "Runs full pipeline on existing sessions without new recording.",
        "future": "Add batch mode for multiple sessions."},
}


ROBOT_PATTERNS = [
    r"192\.168\.", r"\b9090\b", r"rosbridge", r"roslibpy", r"websocket",
    r"/cmd_vel", r"/robot_pose", r"/scan", r"/map", r"mission_queue", r"/api/v[0-9]",
]

MOTIVE_PATTERNS = [
    r"MotiveConnector", r"NatNetClient", r"get_full_state",
    r"get_latest_frame", r"start_recording", r"stop_recording",
]


# ============================================================
# NEW v4: Deep code analysis patterns
# ============================================================
TOOL_PATTERNS = {
    "ROS Bridge": r"roslibpy",
    "NatNet SDK": r"NatNetClient",
    "OpenCV": r"\bcv2\b|opencv",
    "NumPy": r"\bnumpy\b|\bnp\.",
    "SciPy": r"\bscipy\b",
    "Scikit-learn": r"\bsklearn\b|scikit-learn",
    "PyTorch": r"\btorch\b|pytorch",
    "TensorFlow": r"tensorflow",
    "HuggingFace": r"transformers|huggingface",
    "Grounding DINO": r"groundingdino",
    "SAM (Segment Anything)": r"segment[_-]anything",
    "HTTP requests": r"\brequests\b|urllib",
    "LLM API": r"openai|anthropic|openrouter",
    "CVAT": r"cvat",
    "Hungarian algorithm": r"linear_sum_assignment|hungarian",
    "DBSCAN": r"DBSCAN|dbscan",
}

ENGINEERING_PATTERNS = {
    "Atomic writes": r"safe_pickle|\.tmp['\"]|os\.replace",
    "Backups": r"\.backup|backup_dir",
    "Human-in-loop": r"human.*confirm|user.*approve|is_confirmed|input\(",
    "Safe mode": r"SAFE|pending_merge|SAFE_MODE",
    "Crash logging": r"crash_log|CrashLogger|traceback",
    "UTC timestamps": r"utc|timezone\.utc",
    "SHA256 hashing": r"sha256|hashlib",
    "Threading": r"threading\.|Thread\(",
    "Subprocess": r"subprocess\.",
    "Type hints": r"->\s*(?:str|int|float|bool|list|dict|None|Optional|List|Dict|Tuple)",
    "Docstrings": r'"""[\s\S]{20,}?"""',
    "Try-except": r"try:\s*\n",
    "Logging": r"\blogging\b|logger\.",
    "Config files": r"config\.txt|config\.json|\.yaml|\.yml",
    "Version control": r"git\.|__version__",
}

# Big tech company patterns for comparison
BIG_TECH_PRACTICES = {
    "Fixed taxonomy (Google RT-X style)": {
        "check": "persistent_knowledge/taxonomy.json",
        "importance": "HIGH",
        "reason": "All big tech projects define object classes BEFORE data collection.",
    },
    "Human-in-loop (Figure AI style)": {
        "check": "agents/apply_merge.py",
        "importance": "CRITICAL",
        "reason": "No AI decision is final without human approval.",
    },
    "Atomic saves (industry standard)": {
        "check_content": "safe_pickle_dump",
        "check_path": "agents/knowledge_engine.py",
        "importance": "HIGH",
        "reason": "Prevents data corruption on crash.",
    },
    "SAFE mode (never auto-merge)": {
        "check_content": "SAFE",
        "check_path": "agents/knowledge_engine.py",
        "importance": "CRITICAL",
        "reason": "Deep memory must be protected from bad sessions.",
    },
    "External annotation tool (CVAT)": {
        "check": "agents/cvat_converter.py",
        "importance": "HIGH",
        "reason": "Tesla, Figure AI, 1X all use CVAT or similar. Never build from scratch.",
    },
    "Auto-labeling with vision models": {
        "check": "agents/auto_labeler.py",
        "importance": "MEDIUM",
        "reason": "Physical Intelligence, Google use Grounding DINO / SAM for pre-labeling.",
    },
    "Cross-modal alignment": {
        "check": "agents/cross_modal_aligner.py",
        "importance": "MEDIUM",
        "reason": "DeepMind and Meta use Hungarian algorithm for multi-sensor fusion.",
    },
    "Persistent label registry": {
        "check": "agents/label_registry.py",
        "importance": "HIGH",
        "reason": "Ensures object identity consistency across sessions.",
    },
    "Session versioning / snapshots": {
        "check": "project_history/snapshots",
        "importance": "HIGH",
        "reason": "HuggingFace, DVC standard practice.",
    },
    "Quality flagging": {
        "check": "agents/quality_gate.py",
        "importance": "HIGH",
        "reason": "Every big pipeline has automated quality checks.",
    },
    "AI Advisor / LLM feedback": {
        "check": "agents/ai_advisor.py",
        "importance": "MEDIUM",
        "reason": "Modern pipelines use LLMs to critique their own data.",
    },
    "VLA dataset builder": {
        "check": "agents/vla_dataset_builder.py",
        "importance": "HIGH",
        "reason": "Final output must be in standard format (RLDS/LeRobot).",
    },
}


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def utc_stamp():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")


def find_project_root():
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "agents").is_dir() and (current / "sessions").is_dir():
            return current
        current = current.parent
    return Path.cwd()


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def file_metadata(path):
    stat = path.stat()
    return {
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


class StructureVisitor(ast.NodeVisitor):
    def __init__(self, source):
        self.source = source
        self.scope = []
        self.functions = {}
        self.classes = {}
        self.imports = set()

    def qualified_name(self, name):
        return ".".join(self.scope + [name])

    def segment_hash(self, node):
        segment = ast.get_source_segment(self.source, node) or ""
        return sha256_text(segment)[:16]

    def visit_Import(self, node):
        for item in node.names:
            self.imports.add(item.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        self.imports.add(module)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        name = self.qualified_name(node.name)
        methods = [child.name for child in node.body
                   if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.classes[name] = {
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
            "methods": methods,
            "hash": self.segment_hash(node),
        }
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def handle_function(self, node):
        name = self.qualified_name(node.name)
        end_line = getattr(node, "end_lineno", node.lineno)
        self.functions[name] = {
            "line_start": node.lineno,
            "line_end": end_line,
            "line_count": end_line - node.lineno + 1,
            "hash": self.segment_hash(node),
        }
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self.handle_function(node)


def scan_python_file(path):
    record = {
        "metadata": file_metadata(path),
        "line_count": 0,
        "sha256_full": None,
        "module_docstring": None,
        "functions": {},
        "classes": {},
        "imports": [],
        "parse_error": None,
        "source_text": "",
        "detected_tools": [],
        "detected_patterns": [],
    }

    try:
        source = read_text(path)
        record["source_text"] = source
        record["line_count"] = len(source.splitlines())
        record["sha256_full"] = sha256_text(source)
        tree = ast.parse(source)
        record["module_docstring"] = ast.get_docstring(tree)
        visitor = StructureVisitor(source)
        visitor.visit(tree)
        record["functions"] = visitor.functions
        record["classes"] = visitor.classes
        record["imports"] = sorted(visitor.imports)

        # NEW v4: Detect tools and engineering patterns
        for tool_name, pattern in TOOL_PATTERNS.items():
            if re.search(pattern, source, re.IGNORECASE):
                record["detected_tools"].append(tool_name)
        for concept, pattern in ENGINEERING_PATTERNS.items():
            if re.search(pattern, source):
                record["detected_patterns"].append(concept)

    except Exception as exc:
        record["parse_error"] = str(exc)

    return record


def scan_agents(root):
    result = {}
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return result
    for path in sorted(agents_dir.glob("*.py")):
        if path.name.startswith("__"):
            continue
        result[path.name] = scan_python_file(path)
    return result


def scan_history_documents(root):
    history_root = root / "project_history"
    documents = {}
    if not history_root.is_dir():
        return documents
    for path in sorted(history_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(history_root)
        if any(part in HISTORY_EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.name in HISTORY_EXCLUDED_FILES:
            continue
        if path.suffix.lower() not in HISTORY_EXTENSIONS:
            continue
        try:
            content = read_text(path)
            headings = [line.strip() for line in content.splitlines()
                        if line.strip().startswith("#")]
            documents[str(relative)] = {
                "metadata": file_metadata(path),
                "line_count": len(content.splitlines()),
                "sha256": sha256_text(content),
                "headings": headings,
                "content": content,
            }
        except Exception as exc:
            documents[str(relative)] = {"read_error": str(exc)}
    return documents


def scan_sessions(root):
    sessions = {}
    sessions_root = root / "sessions"
    if not sessions_root.is_dir():
        return sessions
    for folder in sorted(sessions_root.glob("session_*")):
        if not folder.is_dir():
            continue
        artifacts = {}
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            relative = str(path.relative_to(folder))
            artifacts[relative] = file_metadata(path)
        sessions[folder.name] = {
            "metadata": file_metadata(folder),
            "artifacts": artifacts,
            "has_fused_data": (folder / "fused_data.pkl").exists(),
            "has_report": (folder / "session_comprehensive_report.txt").exists(),
            "has_pending_candidate": (folder / "pending_merge_candidate.pkl").exists(),
            "has_auto_labels": (folder / "auto_labels.xml").exists(),
            "has_cross_modal": (folder / "cross_modal_matches.jsonl").exists(),
        }
    return sessions


def extract_session_id(filename):
    match = re.search(r"session_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", filename)
    return match.group(0) if match else "unmatched"


def scan_motive_files(root):
    motive_root = root / "motive sessions"
    result = {}
    if not motive_root.is_dir():
        return result
    for path in sorted(motive_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".avi", ".csv", ".tak", ".json"}:
            continue
        relative = str(path.relative_to(motive_root))
        record = file_metadata(path)
        record["extension"] = path.suffix.lower()
        record["session_id"] = extract_session_id(path.name)
        result[relative] = record
    return result


def scan_reports(root):
    reports_root = root / "reports"
    result = {}
    if not reports_root.is_dir():
        return result
    for path in sorted(reports_root.glob("*")):
        if path.is_file():
            result[path.name] = file_metadata(path)
    return result


def safe_length(value):
    try:
        return len(value)
    except Exception:
        return 0


def load_environment_knowledge(root):
    path = root / "persistent_knowledge" / "environment_knowledge.pkl"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        objects = data.get("objects", [])
        names = []
        for obj in objects:
            names_seen = obj.get("names_seen", [])
            if names_seen:
                names.append(names_seen[0])
            else:
                names.append(obj.get("object_id", "unknown"))
        return {
            "sessions_processed": data.get("total_sessions_processed", 0),
            "object_count": len(objects),
            "object_names": sorted(names),
            "last_updated": data.get("last_updated_utc"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def load_deep_memory(root):
    path = root / "persistent_knowledge" / "deep_learning_memory.pkl"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        tracks = data.get("object_tracks", {})
        track_names = sorted(tracks.keys()) if isinstance(tracks, dict) else []
        return {
            "sessions_analyzed": data.get("total_sessions_analyzed", 0),
            "object_tracks": track_names,
            "safety_events": safe_length(data.get("safety_events", [])),
        }
    except Exception as exc:
        return {"error": str(exc)}


def load_label_registry(root):
    """NEW v4: Load label registry summary."""
    path = root / "persistent_knowledge" / "label_registry.pkl"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        labels = data.get("labels", {})
        confirmed = sum(1 for e in labels.values() if e.get("is_confirmed"))
        return {
            "total_labels": len(labels),
            "confirmed_labels": confirmed,
            "pending_labels": len(labels) - confirmed,
            "label_names": sorted([e.get("canonical_name", "") for e in labels.values()]),
        }
    except Exception as exc:
        return {"error": str(exc)}


def load_taxonomy(root):
    """NEW v4: Load taxonomy.json."""
    path = root / "persistent_knowledge" / "taxonomy.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "version": data.get("version", "unknown"),
            "class_count": len(data.get("classes", {})),
            "classes": list(data.get("classes", {}).keys()),
        }
    except Exception as exc:
        return {"error": str(exc)}


def check_evidence(root, item):
    kind = item["kind"]
    if kind == "path":
        return (root / item["path"]).exists()
    if kind == "any_path":
        return any((root / path).exists() for path in item["paths"])
    if kind == "contains":
        path = root / item["path"]
        if not path.exists():
            return False
        try:
            return item["marker"] in read_text(path)
        except Exception:
            return False
    return False


def calculate_roadmap(root):
    result = {}
    for item in ROADMAP:
        checks = [check_evidence(root, ev) for ev in item["evidence"]]
        passed = sum(1 for v in checks if v)
        if checks and passed == len(checks):
            status = "DONE"
        elif passed > 0:
            status = "PARTIAL"
        else:
            status = "NOT_STARTED"
        result[str(item["step"])] = {
            "name": item["name"],
            "intent": item["intent"],
            "status": status,
            "evidence_passed": passed,
            "evidence_total": len(checks),
        }
    return result


def scan_integration_references(agents):
    result = {"robot_api": [], "motive_natnet": []}
    excluded = {"project_snapshot.py", "inspect_motive_pipeline.py"}
    pattern_groups = {"robot_api": ROBOT_PATTERNS, "motive_natnet": MOTIVE_PATTERNS}
    for filename, record in agents.items():
        if filename in excluded:
            continue
        source = record.get("source_text", "")
        lines = source.splitlines()
        for group_name, patterns in pattern_groups.items():
            for line_number, line in enumerate(lines, start=1):
                if any(re.search(p, line, flags=re.IGNORECASE) for p in patterns):
                    result[group_name].append({
                        "file": filename,
                        "line": line_number,
                        "text": line.strip()[:300],
                    })
    return result


def read_latest_session_report(root):
    candidates = list((root / "sessions").glob("session_*/session_comprehensive_report.txt"))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    content = read_text(latest)
    if len(content) > MAX_LATEST_REPORT_CHARS:
        half = MAX_LATEST_REPORT_CHARS // 2
        content = (content[:half] + "\n\n[... REPORT MIDDLE TRUNCATED ...]\n\n"
                   + content[-half:])
    return {
        "path": str(latest.relative_to(root)),
        "content": content,
        "metadata": file_metadata(latest),
    }


def check_python_packages():
    """NEW v4: Check which key Python packages are installed."""
    packages = [
        "numpy", "scipy", "cv2", "sklearn", "roslibpy",
        "requests", "torch", "transformers", "groundingdino",
    ]
    results = {}
    for pkg in packages:
        try:
            module = pkg.replace("-", "_")
            result = subprocess.run(
                [sys.executable, "-c", "import " + module + "; print('OK')"],
                capture_output=True, text=True, timeout=5,
            )
            results[pkg] = "installed" if "OK" in result.stdout else "missing"
        except Exception:
            results[pkg] = "missing"
    return results


def compare_with_big_tech(root):
    """NEW v4: Compare project state with big tech practices."""
    results = {}
    for practice, details in BIG_TECH_PRACTICES.items():
        status = "MISSING"
        if "check" in details:
            check_path = root / details["check"]
            if check_path.exists():
                status = "PRESENT"
        elif "check_content" in details:
            content_path = root / details["check_path"]
            if content_path.exists():
                try:
                    if details["check_content"] in read_text(content_path):
                        status = "PRESENT"
                except Exception:
                    pass
        results[practice] = {
            "status": status,
            "importance": details["importance"],
            "reason": details["reason"],
        }
    return results


def build_state(root):
    agents = scan_agents(root)
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "root": str(root),
        "agents": agents,
        "sessions": scan_sessions(root),
        "motive_files": scan_motive_files(root),
        "reports": scan_reports(root),
        "history_documents": scan_history_documents(root),
        "environment_knowledge": load_environment_knowledge(root),
        "deep_memory": load_deep_memory(root),
        "label_registry": load_label_registry(root),
        "taxonomy": load_taxonomy(root),
        "roadmap": calculate_roadmap(root),
        "integration_references": scan_integration_references(agents),
        "latest_session_report": read_latest_session_report(root),
        "python_packages": check_python_packages(),
        "big_tech_comparison": compare_with_big_tech(root),
    }


def history_directory(root):
    path = root / "project_history"
    (path / "snapshots").mkdir(parents=True, exist_ok=True)
    return path


def load_previous_state(root):
    path = history_directory(root) / "latest_state.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def unified_source_diff(old_source, new_source):
    if old_source is None:
        return ["Previous source text is unavailable in the old baseline."]
    diff_lines = list(difflib.unified_diff(
        old_source.splitlines(), new_source.splitlines(),
        fromfile="previous", tofile="current", lineterm="",
    ))
    if len(diff_lines) > MAX_SOURCE_DIFF_LINES:
        hidden = len(diff_lines) - MAX_SOURCE_DIFF_LINES
        diff_lines = diff_lines[:MAX_SOURCE_DIFF_LINES]
        diff_lines.append("[... " + str(hidden) + " additional diff lines truncated ...]")
    return diff_lines


def diff_named_hashes(old_items, new_items):
    old_items = old_items or {}
    new_items = new_items or {}
    added = sorted(set(new_items) - set(old_items))
    removed = sorted(set(old_items) - set(new_items))
    modified = []
    for name in sorted(set(old_items) & set(new_items)):
        if old_items[name].get("hash") != new_items[name].get("hash"):
            modified.append(name)
    return {"added": added, "removed": removed, "modified": modified}


def hash_from_record(record):
    if not record:
        return None
    return record.get("sha256_full") or record.get("sha256")


def compare_states(old, new):
    diff = {
        "first_run": old is None,
        "agents": {"added": [], "removed": [], "modified": {}},
        "history_documents": {"added": [], "removed": [], "modified": {}},
        "sessions_added": [], "sessions_removed": [],
        "motive_files_added": [], "motive_files_removed": [],
        "reports_added": [], "roadmap_changes": [], "knowledge_changes": {},
    }
    old = old or {}
    old_agents = old.get("agents", {})
    new_agents = new.get("agents", {})
    diff["agents"]["added"] = sorted(set(new_agents) - set(old_agents))
    diff["agents"]["removed"] = sorted(set(old_agents) - set(new_agents))
    for name in sorted(set(old_agents) & set(new_agents)):
        old_record = old_agents[name]
        new_record = new_agents[name]
        if hash_from_record(old_record) == hash_from_record(new_record):
            continue
        function_diff = diff_named_hashes(old_record.get("functions", {}),
                                           new_record.get("functions", {}))
        class_diff = diff_named_hashes(old_record.get("classes", {}),
                                        new_record.get("classes", {}))
        old_lines = old_record.get("line_count", 0)
        new_lines = new_record.get("line_count", 0)
        diff["agents"]["modified"][name] = {
            "line_change": new_lines - old_lines,
            "old_mtime": old_record.get("metadata", {}).get("mtime",
                         old_record.get("mtime")),
            "new_mtime": new_record.get("metadata", {}).get("mtime"),
            "functions": function_diff,
            "classes": class_diff,
            "source_diff": unified_source_diff(
                old_record.get("source_text"),
                new_record.get("source_text", "")),
        }
    old_docs = old.get("history_documents", old.get("manual_notes", {}))
    new_docs = new.get("history_documents", {})
    diff["history_documents"]["added"] = sorted(set(new_docs) - set(old_docs))
    diff["history_documents"]["removed"] = sorted(set(old_docs) - set(new_docs))
    for name in sorted(set(old_docs) & set(new_docs)):
        if hash_from_record(old_docs[name]) == hash_from_record(new_docs[name]):
            continue
        diff["history_documents"]["modified"][name] = {
            "source_diff": unified_source_diff(
                old_docs[name].get("content"),
                new_docs[name].get("content", ""))
        }
    old_sessions = set(old.get("sessions", {}))
    new_sessions = set(new.get("sessions", {}))
    diff["sessions_added"] = sorted(new_sessions - old_sessions)
    diff["sessions_removed"] = sorted(old_sessions - new_sessions)
    old_motive = set(old.get("motive_files", {}))
    new_motive = set(new.get("motive_files", {}))
    diff["motive_files_added"] = sorted(new_motive - old_motive)
    diff["motive_files_removed"] = sorted(old_motive - new_motive)
    old_reports = set(old.get("reports", {}))
    new_reports = set(new.get("reports", {}))
    diff["reports_added"] = sorted(new_reports - old_reports)
    old_roadmap = old.get("roadmap", {})
    new_roadmap = new.get("roadmap", {})
    for step, current in new_roadmap.items():
        previous = old_roadmap.get(step, {})
        old_status = previous.get("status")
        new_status = current.get("status")
        if old_status is not None and old_status != new_status:
            diff["roadmap_changes"].append({
                "step": step, "name": current["name"],
                "old_status": old_status, "new_status": new_status,
            })
    old_knowledge = old.get("environment_knowledge") or {}
    new_knowledge = new.get("environment_knowledge") or {}
    old_names = set(old_knowledge.get("object_names", []))
    new_names = set(new_knowledge.get("object_names", []))
    diff["knowledge_changes"] = {
        "objects_added": sorted(new_names - old_names),
        "objects_removed": sorted(old_names - new_names),
        "session_count_change": (new_knowledge.get("sessions_processed", 0)
                                  - old_knowledge.get("sessions_processed", 0)),
    }
    return diff


def save_state(root, state):
    directory = history_directory(root)
    latest = directory / "latest_state.json"
    temporary = directory / "latest_state.json.tmp"
    archive = directory / "snapshots" / ("snapshot_" + utc_stamp() + ".json")
    serialized = json.dumps(state, indent=2, ensure_ascii=False)
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, latest)
    archive.write_text(serialized, encoding="utf-8")


def append_changelog(root, diff):
    path = history_directory(root) / "CHANGELOG.md"
    lines = ["\n## " + utc_now_iso() + "\n"]
    if diff["first_run"]:
        lines.append("- Baseline snapshot created.\n")
    for name in diff["agents"]["added"]:
        lines.append("- NEW AGENT FILE: `" + name + "`\n")
    for name in diff["agents"]["removed"]:
        lines.append("- REMOVED AGENT FILE: `" + name + "`\n")
    for name, record in diff["agents"]["modified"].items():
        line_change = record["line_change"]
        sign = "+" if line_change >= 0 else ""
        lines.append("- MODIFIED AGENT: `" + name +
                     "` (line change: " + sign + str(line_change) + ")\n")
        fd = record["functions"]
        if fd["added"]:
            lines.append("  - Functions added: " + ", ".join(fd["added"]) + "\n")
        if fd["removed"]:
            lines.append("  - Functions removed: " + ", ".join(fd["removed"]) + "\n")
        if fd["modified"]:
            lines.append("  - Functions modified: " + ", ".join(fd["modified"]) + "\n")
    for name in diff["history_documents"]["added"]:
        lines.append("- NEW HISTORY DOCUMENT READ: `" + name + "`\n")
    for name in diff["history_documents"]["modified"]:
        lines.append("- HISTORY DOCUMENT UPDATED: `" + name + "`\n")
    for name in diff["sessions_added"]:
        lines.append("- NEW SESSION: `" + name + "`\n")
    for name in diff["motive_files_added"]:
        lines.append("- NEW MOTIVE FILE: `" + name + "`\n")
    for change in diff["roadmap_changes"]:
        lines.append("- ROADMAP Step " + change["step"] + ": " +
                     change["old_status"] + " -> " + change["new_status"] + "\n")
    with open(path, "a", encoding="utf-8") as f:
        f.writelines(lines)


def next_run_number(root):
    path = history_directory(root) / "run_count.txt"
    value = 1
    if path.exists():
        try:
            value = int(path.read_text(encoding="utf-8").strip()) + 1
        except Exception:
            value = 1
    path.write_text(str(value), encoding="utf-8")
    return value


def render_report(root, state, diff, run_number):
    lines = []

    # HEADER
    lines.append("# PROJECT SNAPSHOT FOR AI HANDOFF")
    lines.append("")
    lines.append("- Snapshot version: 4")
    lines.append("- Run number: " + str(run_number))
    lines.append("- Generated at UTC: " + state["generated_at_utc"])
    lines.append("- Project root: `" + str(root) + "`")

    # SECTION 1: Mission
    lines.append("")
    lines.append("## 1. Project Mission")
    lines.append("")
    lines.append("Build a traceable dual-source Vision-Language-Action dataset "
                 "for a MiR robot using OptiTrack Motive video, SLAM/LiDAR, "
                 "cumulative knowledge and robot command/decision history.")

    # SECTION 2: Changes
    lines.append("")
    lines.append("## 2. Changes Since the Previous Snapshot")
    lines.append("")
    if diff["first_run"]:
        lines.append("This is the first compatible baseline.")
    if diff["agents"]["added"]:
        lines.append("")
        lines.append("### New agent files")
        for name in diff["agents"]["added"]:
            lines.append("- `" + name + "`")
    if diff["agents"]["removed"]:
        lines.append("")
        lines.append("### Removed agent files")
        for name in diff["agents"]["removed"]:
            lines.append("- `" + name + "`")
    if diff["agents"]["modified"]:
        lines.append("")
        lines.append("### Modified agent files")
        for name, record in diff["agents"]["modified"].items():
            lines.append("")
            lines.append("#### `" + name + "`")
            sign = "+" if record["line_change"] >= 0 else ""
            lines.append("- Line change: " + sign + str(record["line_change"]))
            lines.append("- Modified: " + str(record["old_mtime"]) + " -> " +
                         str(record["new_mtime"]))
            fd = record["functions"]
            lines.append("- Functions added: " + str(fd["added"]))
            lines.append("- Functions removed: " + str(fd["removed"]))
            lines.append("- Functions modified: " + str(fd["modified"]))
            lines.append("")
            lines.append("```diff")
            lines.extend(record["source_diff"])
            lines.append("```")

    # SECTION 3: Roadmap
    lines.append("")
    lines.append("## 3. Current Roadmap")
    lines.append("")
    current_focus = None
    for step in sorted(state["roadmap"], key=int):
        item = state["roadmap"][step]
        lines.append("- Step " + step + ": **" + item["status"] + "** - " +
                     item["name"] + " (" + str(item["evidence_passed"]) +
                     "/" + str(item["evidence_total"]) + " evidence)")
        lines.append("  - Goal: " + item["intent"])
        if current_focus is None and item["status"] != "DONE":
            current_focus = (step, item["name"])
    if current_focus:
        lines.append("")
        lines.append("**Current focus:** Step " + current_focus[0] + " - " + current_focus[1])

    # SECTION 4: Agents
    lines.append("")
    lines.append("## 4. Full Agent Inventory")
    lines.append("")
    for name, record in sorted(state["agents"].items()):
        plan = AGENT_PLANS.get(name, {})
        docstring = record.get("module_docstring") or ""
        purpose = docstring.strip().splitlines()[0] if docstring else "Unknown"
        lines.append("### `" + name + "`")
        lines.append("- Category: " + plan.get("category", "Unclassified"))
        lines.append("- Purpose: " + purpose)
        lines.append("- Current: " + plan.get("current", "Infer from source."))
        lines.append("- Future: " + plan.get("future", "Must be documented."))
        lines.append("- Lines: " + str(record.get("line_count", 0)))
        lines.append("- SHA-256: `" + str(record.get("sha256_full")) + "`")
        lines.append("- Parse error: " + str(record.get("parse_error") or "None"))
        lines.append("- Functions (" + str(len(record.get("functions", {}))) + "): " +
                     str(sorted(record.get("functions", {}))))
        lines.append("- Classes (" + str(len(record.get("classes", {}))) + "): " +
                     str(sorted(record.get("classes", {}))))
        lines.append("- Imports: " + str(record.get("imports", [])))
        lines.append("")

    # SECTION 5: Integration
    lines.append("## 5. Runtime Integration Evidence")
    lines.append("")
    refs = state["integration_references"]
    lines.append("### MiR/ROS/API references")
    if refs["robot_api"]:
        for item in refs["robot_api"][:30]:
            lines.append("- `" + item["file"] + ":" + str(item["line"]) +
                         "` - `" + item["text"] + "`")
    else:
        lines.append("- None detected.")
    lines.append("")
    lines.append("### Motive/NatNet references")
    if refs["motive_natnet"]:
        for item in refs["motive_natnet"][:30]:
            lines.append("- `" + item["file"] + ":" + str(item["line"]) +
                         "` - `" + item["text"] + "`")
    else:
        lines.append("- None detected.")

    # SECTION 6: Sessions
    lines.append("")
    lines.append("## 6. Session Inventory")
    lines.append("")
    for name, record in sorted(state["sessions"].items()):
        lines.append("### `" + name + "`")
        lines.append("- Fused data: " + str(record["has_fused_data"]))
        lines.append("- Report: " + str(record["has_report"]))
        lines.append("- Pending candidate: " + str(record["has_pending_candidate"]))
        lines.append("- Auto labels: " + str(record.get("has_auto_labels", False)))
        lines.append("- Cross modal: " + str(record.get("has_cross_modal", False)))
        lines.append("- Artifacts (" + str(len(record["artifacts"])) + "): " +
                     str(sorted(record["artifacts"])))

    # SECTION 7: Motive files
    lines.append("")
    lines.append("## 7. Motive File Inventory")
    lines.append("")
    grouped = {}
    for name, record in state["motive_files"].items():
        grouped.setdefault(record["session_id"], []).append((name, record))
    for session_id, items in sorted(grouped.items()):
        lines.append("### `" + session_id + "`")
        for name, record in items:
            size_mb = record["size_bytes"] / (1024 * 1024)
            lines.append("- `" + name + "` - " + record["extension"] + ", " +
                         str(round(size_mb, 2)) + " MB, " + record["mtime"])

    # SECTION 8: Persistent knowledge
    lines.append("")
    lines.append("## 8. Persistent Knowledge")
    lines.append("")
    lines.append("### Environment knowledge")
    lines.append("```json")
    lines.append(json.dumps(state["environment_knowledge"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("### Deep learning memory")
    lines.append("```json")
    lines.append(json.dumps(state["deep_memory"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("### Label registry (NEW v4)")
    lines.append("```json")
    lines.append(json.dumps(state["label_registry"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("### Taxonomy (NEW v4)")
    lines.append("```json")
    lines.append(json.dumps(state["taxonomy"], indent=2, ensure_ascii=False))
    lines.append("```")

    # SECTION 9: History docs
    lines.append("")
    lines.append("## 9. Project-History Documents")
    lines.append("")
    documents = state["history_documents"]
    if not documents:
        lines.append("No manual history document found.")
    else:
        for name, record in sorted(documents.items()):
            lines.append("### `" + name + "`")
            if "read_error" in record:
                lines.append("Read error: " + record["read_error"])
                continue
            lines.append("- Lines: " + str(record["line_count"]))
            lines.append("- Modified: " + record["metadata"]["mtime"])
            lines.append("- SHA-256: `" + record["sha256"] + "`")
            lines.append("")
            content = record["content"]
            if len(content) > MAX_HISTORY_DOCUMENT_CHARS:
                hidden = len(content) - MAX_HISTORY_DOCUMENT_CHARS
                content = content[:MAX_HISTORY_DOCUMENT_CHARS]
                content += ("\n\n[... " + str(hidden) + " chars truncated ...]")
            lines.append(content)
            lines.append("")

    # SECTION 10: Latest report
    lines.append("## 10. Latest Comprehensive Session Report")
    lines.append("")
    latest_report = state["latest_session_report"]
    if latest_report:
        lines.append("Source: `" + latest_report["path"] + "`")
        lines.append("")
        lines.append("```text")
        lines.append(latest_report["content"])
        lines.append("```")
    else:
        lines.append("No comprehensive session report found.")

    # SECTION 11: Open issues
    lines.append("")
    lines.append("## 11. Known Open Issues and Blockers")
    lines.append("")
    lines.append("- Motive CSV multi-row schema needs full inspection.")
    lines.append("- Camera intrinsics not yet verified.")
    lines.append("- 3D-to-2D projection into AVI cameras not implemented.")
    lines.append("- MiR API acquisition module not identified in production code.")
    lines.append("- CVAT deployment not verified.")
    lines.append("- Grounding DINO weights not downloaded.")

    # SECTION 12: Rules
    lines.append("")
    lines.append("## 12. Rules for the Next AI")
    lines.append("")
    lines.append("1. Never auto-merge into permanent deep memory.")
    lines.append("2. Default answer to destructive operations is no.")
    lines.append("3. Do not invent CSV schema or camera calibration.")
    lines.append("4. Keep Motive API and MiR API separate.")
    lines.append("5. Use Python 3.10-compatible syntax.")
    lines.append("6. Prefer small, reversible changes.")
    lines.append("7. Cross-reference suggestions never final until human-confirmed.")
    lines.append("8. Full annotations in JSONL, summaries in reports.")
    lines.append("9. Training is dual-source redundant (Motive + SLAM).")
    lines.append("10. Never rebuild what exists in open-source (use CVAT, DINO, SAM).")

    # SECTION 13: NEW v4 - Deep code analysis
    lines.append("")
    lines.append("## 13. Deep Code Analysis (v4)")
    lines.append("")
    lines.append("### Tool usage per agent")
    lines.append("")
    lines.append("| Agent | Tools detected | Patterns detected |")
    lines.append("|-------|----------------|-------------------|")
    for name, record in sorted(state["agents"].items()):
        tools = ", ".join(record.get("detected_tools", [])) or "-"
        patterns = ", ".join(record.get("detected_patterns", [])) or "-"
        lines.append("| " + name + " | " + tools[:80] + " | " + patterns[:80] + " |")

    lines.append("")
    lines.append("### Python packages installed")
    lines.append("")
    lines.append("```")
    for pkg, status in state["python_packages"].items():
        symbol = "[OK]  " if status == "installed" else "[MISS]"
        lines.append(symbol + " " + pkg)
    lines.append("```")

    # SECTION 14: NEW v4 - Big tech comparison
    lines.append("")
    lines.append("## 14. Comparison With Big Tech Pipelines (v4)")
    lines.append("")
    comparison = state["big_tech_comparison"]
    lines.append("### Practices used by Google, DeepMind, Tesla, Figure AI, 1X")
    lines.append("")
    lines.append("| Practice | Status | Importance | Reason |")
    lines.append("|----------|--------|------------|--------|")
    for practice, details in comparison.items():
        lines.append("| " + practice + " | " + details["status"] + " | " +
                     details["importance"] + " | " + details["reason"] + " |")

    present = sum(1 for d in comparison.values() if d["status"] == "PRESENT")
    total = len(comparison)
    percent = round((present / total) * 100) if total > 0 else 0
    lines.append("")
    lines.append("**Overall alignment: " + str(present) + "/" + str(total) +
                 " practices (" + str(percent) + "%)**")

    # SECTION 15: NEW v4 - Forced multi-layer AI reasoning
    lines.append("")
    lines.append("## 15. MANDATORY AI REASONING PROMPTS (v4)")
    lines.append("")
    lines.append("You (the AI reading this snapshot) MUST perform the following "
                 "4-layer analysis before responding to the user. Do NOT skip any layer.")
    lines.append("")
    lines.append("### Layer 1: Situational awareness")
    lines.append("")
    lines.append("Answer these questions in order:")
    lines.append("")
    lines.append("1. What percentage of the roadmap is DONE? What is PARTIAL? What is NOT_STARTED?")
    lines.append("2. Which agents were added since last snapshot?")
    lines.append("3. Which agents were modified? What was the biggest change?")
    lines.append("4. What is the current focus step, and why is it not DONE yet?")
    lines.append("5. Are there open issues in Section 11 that block progress?")
    lines.append("")
    lines.append("### Layer 2: Big tech alignment check")
    lines.append("")
    lines.append("Look at Section 14. Answer:")
    lines.append("")
    lines.append("1. Which CRITICAL practices are MISSING? These MUST be fixed first.")
    lines.append("2. Which HIGH-importance practices are MISSING? These should be next.")
    lines.append("3. Is the project below or above 70% alignment with big tech?")
    lines.append("4. If below 70%, list top 3 gaps in priority order.")
    lines.append("5. Compare current pipeline to: Google RT-X, Berkeley DROID, Figure AI, Tesla Optimus.")
    lines.append("")
    lines.append("### Layer 3: Self-critique (be brutally honest)")
    lines.append("")
    lines.append("Before giving advice, criticize your own reasoning:")
    lines.append("")
    lines.append("1. Am I suggesting something that duplicates existing open-source tools?")
    lines.append("2. Am I violating Rule 10 (never rebuild what exists)?")
    lines.append("3. Am I suggesting features that will not lead to a paper?")
    lines.append("4. Am I ignoring the user's constraint of being a solo developer?")
    lines.append("5. Would my advice work on a Windows machine with Python 3.10?")
    lines.append("")
    lines.append("### Layer 4: Paper-oriented recommendations")
    lines.append("")
    lines.append("The user's goal is to publish a paper (ICRA/IROS/CoRL/RAL).")
    lines.append("")
    lines.append("1. What novel contribution does this project have compared to DROID/RT-X?")
    lines.append("2. What baseline comparisons are missing?")
    lines.append("3. What quantitative metrics are missing?")
    lines.append("4. How many sessions are needed for a paper-worthy dataset (minimum 10)?")
    lines.append("5. What is the exact next code change that moves toward publication?")
    lines.append("")
    lines.append("**Only after all 4 layers, provide your final recommendation to the user in Persian.**")
    lines.append("Keep code in English, explanations in Persian, right-to-left friendly formatting.")

    # SECTION 16: NEW v4 - Paper readiness checklist
    lines.append("")
    lines.append("## 16. Paper Readiness Checklist (v4)")
    lines.append("")
    session_count = len(state.get("sessions", {}))
    lines.append("- Sessions collected: " + str(session_count) + " (minimum 10 for paper)")
    lines.append("- Fused sessions: " + str(sum(1 for s in state["sessions"].values()
                                                 if s.get("has_fused_data"))))
    lines.append("- Sessions with cross-modal alignment: " + str(sum(1 for s in state["sessions"].values()
                                                                     if s.get("has_cross_modal", False))))
    lines.append("- Sessions with video labels: " + str(sum(1 for s in state["sessions"].values()
                                                            if s.get("has_auto_labels", False))))
    lr = state.get("label_registry") or {}
    lines.append("- Confirmed labels in registry: " + str(lr.get("confirmed_labels", 0)))
    tx = state.get("taxonomy") or {}
    lines.append("- Taxonomy classes defined: " + str(tx.get("class_count", 0)))

    readiness_score = 0
    if session_count >= 10:
        readiness_score += 20
    if tx.get("class_count", 0) >= 5:
        readiness_score += 15
    if lr.get("confirmed_labels", 0) >= 10:
        readiness_score += 15
    present_practices = sum(1 for d in comparison.values() if d["status"] == "PRESENT")
    if present_practices >= 8:
        readiness_score += 25
    done_steps = sum(1 for r in state["roadmap"].values() if r["status"] == "DONE")
    if done_steps >= 7:
        readiness_score += 25

    lines.append("")
    lines.append("**Paper readiness score: " + str(readiness_score) + "/100**")
    if readiness_score < 40:
        lines.append("- Status: EARLY STAGE. Focus on infrastructure.")
    elif readiness_score < 70:
        lines.append("- Status: DEVELOPMENT. Focus on data collection.")
    elif readiness_score < 90:
        lines.append("- Status: NEAR READY. Focus on model training and metrics.")
    else:
        lines.append("- Status: PAPER READY. Focus on writing and evaluation.")

    return "\n".join(lines)


def main():
    root = find_project_root()
    print("[snapshot] Project root: " + str(root))
    previous_state = load_previous_state(root)
    print("[snapshot] Scanning project (v4 with big tech comparison)...")
    current_state = build_state(root)
    print("[snapshot] Comparing with previous state...")
    diff = compare_states(previous_state, current_state)

    documents = current_state.get("history_documents", {})
    added_documents = set(diff["history_documents"]["added"])
    modified_documents = set(diff["history_documents"]["modified"])
    for name in sorted(documents):
        if name in added_documents:
            print("[snapshot] NEW HISTORY DOCUMENT READ: " + name)
        elif name in modified_documents:
            print("[snapshot] HISTORY DOCUMENT UPDATED AND READ: " + name)
        else:
            print("[snapshot] HISTORY DOCUMENT READ: " + name)

    run_number = next_run_number(root)
    report = render_report(root, current_state, diff, run_number)

    reports_directory = root / "reports"
    reports_directory.mkdir(parents=True, exist_ok=True)
    report_path = reports_directory / "latest_snapshot_for_ai.md"
    report_path.write_text(report, encoding="utf-8")

    append_changelog(root, diff)
    save_state(root, current_state)

    print("")
    print("=" * 60)
    print(" SNAPSHOT v4 COMPLETE")
    print("=" * 60)
    print("Report saved: " + str(report_path))
    print("Changelog:    " + str(history_directory(root) / "CHANGELOG.md"))
    print("")
    print("New in v4:")
    print("  - Section 13: Deep tool and pattern analysis")
    print("  - Section 14: Big tech pipeline comparison")
    print("  - Section 15: Forced 4-layer AI reasoning")
    print("  - Section 16: Paper readiness score")
    print("")
    print("Copy the report content and paste to AI.")
    print("")

    # Open the report in Notepad on Windows for easy copy
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(report_path))
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[snapshot] FATAL ERROR")
        traceback.print_exc()
        raise