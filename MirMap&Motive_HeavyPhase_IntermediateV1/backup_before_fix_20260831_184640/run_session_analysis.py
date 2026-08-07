#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_session_analysis.py — Orchestrator for Full Session Workflow

Runs the entire analysis pipeline for a single session with one command:

  python agents/run_session_analysis.py <session_path> [calibration_path]

Steps performed:
  1. Runs spatial_temporal_fusion.py (if fused_data.pkl doesn't exist)
  2. Runs knowledge_engine.py --safe (creates pending merge candidate)
  3. Runs quality_gate.py (generates flags and learning score)
  4. Generates MERGE REVIEW PACKAGE in the session's comprehensive report
  5. Prints instructions for next steps

Output:
  - All intermediate files (fused_data.pkl, candidate files, etc.)
  - A single comprehensive report file with ALL agent outputs:
      sessions/<session>/session_comprehensive_report.txt
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime, timezone


# ============================================================
# Path resolution
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(SCRIPT_DIR)

# Make sure we can import quality_gate
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


# ============================================================
# Timestamp helpers
# ============================================================
def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


# ============================================================
# Agent runners
# ============================================================
def run_fusion(session_path, calibration_path):
    """Runs spatial_temporal_fusion.py if needed."""
    fused_path = os.path.join(session_path, "fused_data.pkl")
    if os.path.exists(fused_path):
        print(f"[run_session_analysis] fused_data.pkl already exists - skipping fusion")
        return True

    print(f"[run_session_analysis] Running fusion...")
    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "spatial_temporal_fusion.py"),
        session_path,
        calibration_path,
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"[FUSION STDERR] {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[run_session_analysis] Fusion failed: {e}")
        print(f"[FUSION STDOUT] {e.stdout}")
        print(f"[FUSION STDERR] {e.stderr}")
        return False


def run_knowledge_engine_safe(session_path, root_path):
    """Runs knowledge_engine.py in safe mode."""
    print(f"[run_session_analysis] Running knowledge_engine in SAFE mode...")
    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "knowledge_engine.py"),
        "--safe",
        session_path,
        root_path,
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"[KNOWLEDGE STDERR] {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[run_session_analysis] Knowledge engine failed: {e}")
        print(f"[KNOWLEDGE STDOUT] {e.stdout}")
        print(f"[KNOWLEDGE STDERR] {e.stderr}")
        return False


def run_quality_gate(session_path, root_path):
    """Runs quality_gate.py."""
    print(f"[run_session_analysis] Running quality gate...")
    try:
        from quality_gate import run_quality_gate as qg_run
        flags, learning_score = qg_run(root_path, session_path)
        return flags, learning_score
    except Exception as e:
        print(f"[run_session_analysis] Quality gate failed: {e}")
        return None, 0.0


# ============================================================
# Report generation
# ============================================================
def generate_merge_review_package(session_path, root_path, flags, learning_score):
    """
    Generates the MERGE REVIEW PACKAGE section in the comprehensive report.
    This is the section the user copies and sends to AI for advice.
    """
    report_path = os.path.join(session_path, "session_comprehensive_report.txt")

    # Load candidate for diff info
    candidate_path = os.path.join(session_path, "pending_merge_candidate.pkl")
    if not os.path.exists(candidate_path):
        print(f"[run_session_analysis] No candidate found - cannot generate review package")
        return False

    import pickle
    with open(candidate_path, "rb") as f:
        candidate = pickle.load(f)

    diff = candidate.get("diff", {})
    session_results = candidate.get("session_results", {})

    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + "=" * 70 + "\n")
        f.write(" MERGE REVIEW PACKAGE\n")
        f.write("=" * 70 + "\n")
        f.write("This section is designed to be copied and sent to AI for analysis.\n")
        f.write("The AI will advise whether to merge this session into permanent memory.\n\n")

        f.write("--- SESSION METADATA ---\n")
        f.write(f"Session name      : {os.path.basename(session_path)}\n")
        f.write(f"Analysis time (UTC): {utc_now_iso()}\n")
        f.write(f"Root path        : {root_path}\n\n")

        f.write("--- LEARNING PROGRESS SCORE ---\n")
        f.write(f"Score: {learning_score:.1f}/100.0\n")
        f.write("Interpretation:\n")
        f.write("  80-100: Excellent — this session added significant new knowledge\n")
        f.write("  50-79 : Good — some new knowledge, but mostly confirmation\n")
        f.write("  20-49 : Fair — minimal new knowledge, mostly redundant\n")
        f.write("   0-19 : Poor — no new knowledge, may be duplicate or low-quality\n\n")

        f.write("--- IMPACT PREVIEW (BEFORE / AFTER MERGE) ---\n")
        b = diff.get("before", {})
        a = diff.get("after", {})
        f.write(f"Total sessions       : {b.get('total_sessions', 0):>4}  ->  {a.get('total_sessions', 0)}\n")
        f.write(f"Total known objects  : {b.get('total_objects', 0):>4}  ->  {a.get('total_objects', 0)}\n")
        f.write(f"Total safety events  : {b.get('total_safety_events', 0):>4}  ->  {a.get('total_safety_events', 0)}\n")
        f.write(f"Total anomalies      : {b.get('total_anomalies', 0):>4}  ->  {a.get('total_anomalies', 0)}\n")
        f.write(f"Total critical events: {b.get('total_critical', 0):>4}  ->  {a.get('total_critical', 0)}\n")
        f.write(f"Total warning events : {b.get('total_warning', 0):>4}  ->  {a.get('total_warning', 0)}\n\n")

        d = diff.get("delta", {})
        f.write("--- WHAT MERGE WOULD ADD ---\n")
        f.write(f"+ {d.get('new_objects_count', 0)} new object(s)\n")
        if d.get("new_objects_names"):
            for nm in d.get("new_objects_names", [])[:10]:
                f.write(f"    - {nm}\n")
            if len(d.get("new_objects_names", [])) > 10:
                f.write(f"    ... and {len(d.get('new_objects_names', [])) - 10} more\n")
        f.write(f"+ {d.get('new_safety_events', 0)} safety event(s)\n")
        f.write(f"+ {d.get('new_critical_events', 0)} critical event(s)\n")
        f.write(f"+ {d.get('new_warning_events', 0)} warning event(s)\n")
        f.write(f"+ {d.get('new_anomalies', 0)} anomaly(ies)\n")
        f.write(f"+ {d.get('new_insights', 0)} insight(s)\n\n")

        f.write("--- QUALITY GATE FLAGS ---\n")
        if not flags:
            f.write("No flags raised. This session appears clean.\n")
        else:
            f.write(f"Flags raised: {len(flags)}\n")
            for i, flag in enumerate(flags, 1):
                f.write(f"{i}. [{flag['severity'].upper()}] {flag['description']}\n")
                f.write(f"   Suggested action: {flag['suggested_action']}\n")
        f.write("\n")

        f.write("--- AI ADVISOR PROMPT ---\n")
        f.write("Based on the above information, should this session be merged into permanent memory?\n")
        f.write("Answer with a clear 'yes' or 'no', followed by your reasoning.\n")
        f.write("If you recommend 'no', suggest what should be fixed before merging.\n")
        f.write("If you see any red flags in the quality gate section, highlight them.\n\n")

        f.write("--- NEXT STEPS ---\n")
        f.write("1. Review this package carefully\n")
        f.write("2. (Optional) Send the entire MERGE REVIEW PACKAGE section to AI for analysis\n")
        f.write("3. Run: python agents/apply_merge.py \"<session_path>\"\n")
        f.write("4. Answer yes/no when prompted\n")
        f.write("=" * 70 + "\n")

    print(f"[run_session_analysis] MERGE REVIEW PACKAGE written to {report_path}")
    return True


def initialize_comprehensive_report(session_path):
    """Creates the comprehensive report file with header."""
    report_path = os.path.join(session_path, "session_comprehensive_report.txt")

    # Clear existing file if it exists
    if os.path.exists(report_path):
        os.remove(report_path)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(" SESSION COMPREHENSIVE REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Session: {os.path.basename(session_path)}\n")
        f.write(f"Generated at (UTC): {utc_now_iso()}\n")
        f.write("=" * 80 + "\n\n")

    return report_path


def append_agent_output(session_path, agent_name, output):
    """Appends an agent's output to the comprehensive report."""
    report_path = os.path.join(session_path, "session_comprehensive_report.txt")

    with open(report_path, "a", encoding="utf-8") as f:
        f.write(f"--- {agent_name.upper()} OUTPUT ---\n")
        f.write(output)
        f.write("\n\n")

    return True


# ============================================================
# Main workflow
# ============================================================
def run_full_analysis(session_path, calibration_path=None, root_path=None):
    """
    Runs the complete analysis workflow for a session.
    """
    if not os.path.isdir(session_path):
        print(f"[run_session_analysis] ERROR: session path does not exist: {session_path}")
        return False

    if root_path is None:
        root_path = DEFAULT_ROOT

    print(f"[run_session_analysis] Starting full analysis for: {session_path}")
    print(f"[run_session_analysis] Root path: {root_path}")

    # Initialize comprehensive report
    report_path = initialize_comprehensive_report(session_path)

    # Step 1: Fusion
    if not run_fusion(session_path, calibration_path):
        print(f"[run_session_analysis] Fusion failed - aborting")
        return False

    # Read fusion output
    fusion_report_path = os.path.join(session_path, "fused_data_summary.txt")
    if os.path.exists(fusion_report_path):
        with open(fusion_report_path, "r", encoding="utf-8") as f:
            fusion_output = f.read()
        append_agent_output(session_path, "spatial_temporal_fusion", fusion_output)

    # Step 2: Knowledge Engine (SAFE mode)
    if not run_knowledge_engine_safe(session_path, root_path):
        print(f"[run_session_analysis] Knowledge engine failed - aborting")
        return False

    # Read knowledge engine output
    ke_report_path = os.path.join(session_path, "knowledge_engine_report.txt")
    if os.path.exists(ke_report_path):
        with open(ke_report_path, "r", encoding="utf-8") as f:
            ke_output = f.read()
        append_agent_output(session_path, "knowledge_engine", ke_output)

    # Step 3: Quality Gate
    flags, learning_score = run_quality_gate(session_path, root_path)
    if flags is None:
        print(f"[run_session_analysis] Quality gate failed - continuing anyway")

    # Step 4: Generate MERGE REVIEW PACKAGE
    if not generate_merge_review_package(session_path, root_path, flags, learning_score):
        print(f"[run_session_analysis] Failed to generate merge review package")

    print(f"[run_session_analysis] Analysis complete!")
    print(f"[run_session_analysis] Comprehensive report: {report_path}")
    print(f"[run_session_analysis] Next step: Review the MERGE REVIEW PACKAGE section")
    print(f"[run_session_analysis] Then run: python agents/apply_merge.py \"{session_path}\"")

    return True


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Orchestrator for full session analysis workflow")
    parser.add_argument(
        "session_path",
        help="Path to the session folder to analyze")
    parser.add_argument(
        "--calibration", default=None,
        help="Path to calibration .pkl file (default: look in calibration/)")
    parser.add_argument(
        "--root", default=DEFAULT_ROOT,
        help=f"Project root path (default: {DEFAULT_ROOT})")
    args = parser.parse_args()

    # Auto-detect calibration path if not provided
    calibration_path = args.calibration
    if calibration_path is None:
        calib_dir = os.path.join(args.root, "calibration")
        calib_files = sorted(
            [f for f in os.listdir(calib_dir)
             if f.endswith(".pkl") and "calibration" in f],
            reverse=True)
        if calib_files:
            calibration_path = os.path.join(calib_dir, calib_files[0])
            print(f"[run_session_analysis] Using calibration: {calibration_path}")
        else:
            print(f"[run_session_analysis] ERROR: no calibration file found in {calib_dir}")
            sys.exit(1)

    if not run_full_analysis(args.session_path, calibration_path, args.root):
        print(f"[run_session_analysis] Analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()