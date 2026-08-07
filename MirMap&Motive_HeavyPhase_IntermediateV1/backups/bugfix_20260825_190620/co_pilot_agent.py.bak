#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent: co_pilot_agent.py  ("کمک خلبان") — v2

Purpose:
  Your personal assistant that runs AFTER a session (and after
  knowledge_engine has updated deep learning memory), reviews
  EVERYTHING, and writes a single, versioned, human-and-AI-readable
  report file.

What changed in v2:
  - NEW section: Knowledge Engine Brain Report
    Shows everything the cumulative brain has learned so far,
    including object classifications, safety events, insights,
    unresolved questions, and user feedback history.
  - NEW section: Session-vs-History comparison
    Shows what changed in THIS session compared to previous knowledge.
  - NEW section: Recommended Next Steps
    Suggests what to do next based on data quality and coverage.
  - Reads deep_learning_memory.pkl and includes its full snapshot.

Report sections:
  1. FLAGGED ISSUES (review these first)
  2. DETAILED INFO (SLAM, Motive, Fusion, Calibration health)
  3. PERSISTENT KNOWLEDGE (environment_knowledge.pkl summary)
  4. KNOWLEDGE ENGINE BRAIN REPORT (deep_learning_memory snapshot)
  5. THIS SESSION'S NEW DISCOVERIES (what changed this time)
  6. SAFETY ANALYSIS (critical/warning events this session)
  7. UNRESOLVED QUESTIONS (pending human feedback)
  8. RECOMMENDED NEXT STEPS
"""

import os
import sys
import glob
import pickle
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import session_manager

# Try to import knowledge_engine
try:
    from robot_data_analyzer import analyze_robot_data, generate_report_section as _robot_report
    HAS_ROBOT = True
except ImportError:
    HAS_ROBOT = False
try:
    from entity_registry import EntityRegistry
    HAS_ENTITY = True
except ImportError:
    HAS_ENTITY = False

# Try to import knowledge_engine for report generation
try:
    import knowledge_engine
    HAS_KNOWLEDGE_ENGINE = True
except ImportError:
    HAS_KNOWLEDGE_ENGINE = False


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def _next_report_version(reports_dir):
    existing = glob.glob(os.path.join(reports_dir, "copilot_report_v*.txt"))
    max_version = 0
    for path in existing:
        base = os.path.basename(path)
        try:
            version_part = base.split("_v")[1].split("_")[0]
            max_version = max(max_version, int(version_part))
        except (IndexError, ValueError):
            continue
    return max_version + 1


# ============================================================
# Health checks (same as v1 but cleaned up)
# ============================================================
def check_slam_health(slam_pkl_path):
    issues = []
    info = []
    if not os.path.exists(slam_pkl_path):
        return ["slam_data.pkl not found for this session."], info

    with open(slam_pkl_path, "rb") as f:
        map_db = pickle.load(f)

    robot_states = map_db.get("robot_states", [])
    obstacle_scans = map_db.get("obstacle_scans", [])

    info.append(f"robot_states count: {len(robot_states)}")
    info.append(f"obstacle_scans count: {len(obstacle_scans)}")

    if len(robot_states) < 2:
        issues.append("Fewer than 2 robot_states recorded — session may "
                       "have ended immediately or pose topic never published.")
        return issues, info

    timestamps = [s["timestamp_utc"] for s in robot_states]
    gaps = [t2 - t1 for t1, t2 in zip(timestamps, timestamps[1:])]
    max_gap = max(gaps) if gaps else 0.0
    mean_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
    info.append(f"robot_states timestamp gaps: "
                f"mean={mean_gap:.3f}s, max={max_gap:.3f}s")

    if max_gap > 2.0:
        issues.append(f"A gap of {max_gap:.1f}s was found in "
                       f"robot_states — possible ROS bridge disconnect.")

    if len(obstacle_scans) == 0:
        issues.append("No obstacle_scans recorded — check /f_scan and "
                       "/b_scan topics.")

    # Check if robot actually moved
    if len(robot_states) >= 2:
        first = robot_states[0]
        last = robot_states[-1]
        import math
        total_dist = math.hypot(last["x"] - first["x"],
                                last["y"] - first["y"])
        info.append(f"Robot total displacement: {total_dist:.2f}m")
        if total_dist < 0.1:
            issues.append("Robot barely moved (<0.1m) during this "
                          "session — data may not be useful for learning.")

    return issues, info


def check_motive_health(motive_pkl_path):
    issues = []
    info = []
    if not os.path.exists(motive_pkl_path):
        issues.append("motive_data.pkl not found for this session.")
        return issues, info

    with open(motive_pkl_path, "rb") as f:
        motive_data = pickle.load(f)

    rigid_bodies = motive_data.get("rigid_bodies", {})
    info.append(f"rigid bodies recorded: {list(rigid_bodies.keys())}")

    for name, body in rigid_bodies.items():
        samples = body.get("samples", [])
        if not samples:
            issues.append(f"Rigid body '{name}' has zero samples.")
            continue
        tracked_count = sum(1 for s in samples if s.get("tracked"))
        tracked_ratio = tracked_count / len(samples)
        info.append(f"  '{name}': {len(samples)} samples, "
                    f"{tracked_ratio * 100:.1f}% tracked")
        if tracked_ratio < 0.7:
            issues.append(f"Rigid body '{name}' was only tracked "
                          f"{tracked_ratio * 100:.1f}% — check visibility.")

        # Check zero-placeholder
        zero_count = sum(1 for s in samples
                         if s.get("looks_like_zero_placeholder", False))
        if zero_count > 0:
            info.append(f"  '{name}': {zero_count} zero-placeholder samples")
            if zero_count > len(samples) * 0.1:
                issues.append(f"Rigid body '{name}' has {zero_count} "
                              f"zero-placeholder samples (>{10}%) — "
                              f"possible tracking issue.")

    return issues, info


def check_fusion_quality(session_path):
    issues = []
    info = []
    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path):
        issues.append("fused_data.pkl not found — fusion agent may "
                       "not have run.")
        return issues, info

    with open(fused_path, "rb") as f:
        fusion_result = pickle.load(f)

    if fusion_result.get("warnings"):
        for w in fusion_result["warnings"]:
            issues.append(f"Fusion warning: {w}")

    stats = fusion_result.get("stats", {})
    for k, v in stats.items():
        info.append(f"{k}: {v}")

    skipped_gap = stats.get("motive_samples_skipped_time_gap", 0)
    matched = stats.get("motive_samples_matched", 0)
    if matched > 0 and skipped_gap > matched * 0.3:
        issues.append(f"{skipped_gap} Motive samples were skipped due "
                      f"to timestamp mismatch (>30% of matched count).")

    return issues, info


def check_calibration_sanity(calibration_pkl_path, max_age_days=30):
    issues = []
    info = []
    if not os.path.exists(calibration_pkl_path):
        issues.append("No calibration file found — fusion cannot be "
                       "trusted.")
        return issues, info

    with open(calibration_pkl_path, "rb") as f:
        calib = pickle.load(f)

    info.append(f"Calibration timestamp: "
                f"{calib.get('timestamp_utc', 'unknown')}")
    info.append(f"Calibration mean_error_mm: "
                f"{calib.get('mean_error_mm', 'unknown')}")

    validation = calib.get("validation", {})
    verdict = validation.get("verdict", "NOT_RUN")
    info.append(f"Calibration validation verdict: {verdict}")

    if verdict != "PASS":
        issues.append(f"Calibration verdict is '{verdict}', not PASS.")

    try:
        calib_time = datetime.fromisoformat(calib["timestamp_utc"])
        age_days = (datetime.now(tz=timezone.utc) - calib_time).days
        info.append(f"Calibration age: {age_days} days")
        if age_days > max_age_days:
            issues.append(f"Calibration is {age_days} days old "
                          f"(>{max_age_days}).")
    except Exception:
        pass

    return issues, info


def review_persistent_knowledge(knowledge):
    issues = []
    info = []
    info.append(f"Total known objects: {len(knowledge['objects'])}")
    info.append(f"Total sessions processed: "
                f"{knowledge['total_sessions_processed']}")

    for obj in knowledge["objects"]:
        pos = obj.get("estimated_position_m", [0, 0])
        line = (f"  [obj {obj['object_id']}] "
                f"pos=({pos[0]:.2f}, {pos[1]:.2f}) | "
                f"seen={obj['times_observed']}x | "
                f"class={obj['object_class']} | "
                f"confidence={obj['is_static_confidence']:.2f}")
        info.append(line)

        if (obj["times_observed"] >= 5
                and obj["object_class"] == "unknown"
                and obj.get("position_variance_m2", 0) > 0.05):
            issues.append(f"Object {obj['object_id']} has been observed "
                          f"{obj['times_observed']} times with high "
                          f"variance but is still 'unknown'.")

    return issues, info


# ============================================================
# NEW: Knowledge Engine brain snapshot
# ============================================================
def get_knowledge_engine_section(root_path, session_path):
    """
    Reads deep_learning_memory.pkl and generates the brain report
    section. Also reads session-level knowledge_engine_report.txt
    if available.
    """
    lines = []

    # Load deep memory
    dlm_path = os.path.join(root_path, "persistent_knowledge",
                            "deep_learning_memory.pkl")
    if not os.path.exists(dlm_path):
        lines.append("  Deep Learning Memory not yet created.")
        lines.append("  Run knowledge_engine.py to initialize.")
        return lines, []

    with open(dlm_path, "rb") as f:
        memory = pickle.load(f)

    issues = []

    # Use knowledge_engine's report generator if available
    if HAS_KNOWLEDGE_ENGINE:
        report_text = knowledge_engine.generate_report_section(memory)
        for line in report_text.split("\n"):
            lines.append(f"  {line}")
    else:
        # Fallback: manual summary
        lines.append(f"  Sessions analyzed: "
                     f"{memory.get('total_sessions_analyzed', 0)}")
        lines.append(f"  Objects tracked: "
                     f"{len(memory.get('object_tracks', {}))}")
        lines.append(f"  Safety events: "
                     f"{len(memory.get('safety_events', []))}")
        lines.append(f"  Learned insights: "
                     f"{len(memory.get('learned_insights', []))}")
        lines.append(f"  Unresolved questions: "
                     f"{len([q for q in memory.get('unresolved_questions', []) if not q.get('answered')])}")

    # Check for concerning patterns
    for name, track in memory.get("object_tracks", {}).items():
        if track.get("total_time_critical_s", 0) > 5.0:
            issues.append(
                f"Object '{name}' has spent "
                f"{track['total_time_critical_s']:.1f}s total in "
                f"CRITICAL zone (<10cm) across all sessions!")
        if track.get("confidence", 0) < 0.5 \
                and track.get("sessions_count", 0) >= 3:
            issues.append(
                f"Object '{name}' seen in "
                f"{track['sessions_count']} sessions but confidence "
                f"still low ({track['confidence']:.2f}).")

    return lines, issues


# ============================================================
# NEW: This session's discoveries
# ============================================================
def get_session_discoveries(session_path):
    """
    Reads the session-level knowledge_engine_report.txt to show
    what was newly discovered in THIS session.
    """
    lines = []
    report_path = os.path.join(session_path,
                               "knowledge_engine_report.txt")
    if not os.path.exists(report_path):
        lines.append("  Knowledge engine did not run for this session.")
        return lines

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract just the insights section
    in_insights = False
    for line in content.split("\n"):
        if "RECENT INSIGHTS" in line:
            in_insights = True
            continue
        if in_insights and line.strip().startswith("---"):
            break
        if in_insights and line.strip():
            lines.append(f"  {line.strip()}")

    if not lines:
        lines.append("  No new insights from this session.")

    return lines


# ============================================================
# NEW: Safety analysis for this session
# ============================================================
def get_session_safety(root_path, session_name):
    """Extract safety events from this specific session."""
    lines = []

    dlm_path = os.path.join(root_path, "persistent_knowledge",
                            "deep_learning_memory.pkl")
    if not os.path.exists(dlm_path):
        lines.append("  No safety data available yet.")
        return lines

    with open(dlm_path, "rb") as f:
        memory = pickle.load(f)

    session_events = [e for e in memory.get("safety_events", [])
                      if e.get("session") == session_name]

    if not session_events:
        lines.append("  No safety events in this session. All clear.")
        return lines

    critical = [e for e in session_events if e["zone"] == "critical"]
    warning = [e for e in session_events if e["zone"] == "warning"]

    lines.append(f"  Critical events (<10cm): {len(critical)}")
    lines.append(f"  Warning events (10-30cm): {len(warning)}")

    # Show worst events
    if critical:
        worst = min(critical, key=lambda e: e["distance_m"])
        lines.append(f"  Closest critical: {worst['object_name']} "
                     f"at {worst['distance_m']*100:.1f}cm")

    # Group by object
    obj_events = {}
    for e in session_events:
        name = e["object_name"]
        if name not in obj_events:
            obj_events[name] = {"critical": 0, "warning": 0}
        obj_events[name][e["zone"]] += 1

    lines.append("  Per-object breakdown:")
    for name, counts in obj_events.items():
        lines.append(f"    {name}: {counts['critical']} critical, "
                     f"{counts['warning']} warning")

    return lines


# ============================================================
# NEW: Recommended next steps
# ============================================================
def get_recommendations(root_path, all_issues):
    """Generate actionable recommendations based on current state."""
    lines = []

    dlm_path = os.path.join(root_path, "persistent_knowledge",
                            "deep_learning_memory.pkl")
    knowledge = session_manager.load_persistent_knowledge(root_path)

    n_sessions = knowledge.get("total_sessions_processed", 0)
    n_objects = len(knowledge.get("objects", []))

    has_dlm = os.path.exists(dlm_path)
    if has_dlm:
        with open(dlm_path, "rb") as f:
            memory = pickle.load(f)
        n_analyzed = memory.get("total_sessions_analyzed", 0)
        n_tracks = len(memory.get("object_tracks", {}))
        open_questions = len([q for q in
                              memory.get("unresolved_questions", [])
                              if not q.get("answered")])
    else:
        n_analyzed = 0
        n_tracks = 0
        open_questions = 0

    # Generate recommendations
    if n_sessions == 0:
        lines.append("  → Run your first session with launch_session.py")
    elif n_sessions < 5:
        lines.append(f"  → Run more sessions ({n_sessions}/5 minimum "
                     f"for reliable classification)")
    elif n_sessions >= 5 and n_sessions < 20:
        lines.append(f"  → Good progress ({n_sessions} sessions). "
                     f"Continue to strengthen confidence.")
    else:
        lines.append(f"  → Strong dataset ({n_sessions} sessions). "
                     f"Consider starting video annotation module.")

    if open_questions > 0:
        lines.append(f"  → {open_questions} questions need your input. "
                     f"Answer them to improve classification accuracy.")

    if n_tracks > 0 and has_dlm:
        uncertain = [name for name, t in
                     memory["object_tracks"].items()
                     if t.get("confidence", 0) < 0.7]
        if uncertain:
            lines.append(f"  → {len(uncertain)} objects still uncertain: "
                         f"{', '.join(uncertain[:3])}")

        confirmed = [name for name, t in
                     memory["object_tracks"].items()
                     if "confirmed" in t.get("classification", "")]
        if confirmed:
            lines.append(f"  → {len(confirmed)} objects confirmed: "
                         f"{', '.join(confirmed[:3])}")

    if all_issues:
        lines.append(f"  → Fix {len(all_issues)} flagged issues above "
                     f"before running more sessions.")

    if n_analyzed >= 10:
        lines.append("  → Consider starting video sync & annotation "
                     "module (Agent 5) for Qwen-VLA dataset.")

    if not lines:
        lines.append("  → System is healthy. Continue collecting data.")

    return lines


# ============================================================
# Main report generator
# ============================================================
def generate_report(root_path, session_path, calibration_pkl_path):
    reports_dir = os.path.join(root_path, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    version = _next_report_version(reports_dir)
    timestamp_tag = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    report_path = os.path.join(
        reports_dir,
        f"copilot_report_v{version:03d}_{timestamp_tag}.txt"
    )

    session_name = os.path.basename(session_path)
    all_issues = []
    all_info_sections = []

    slam_pkl_path = os.path.join(session_path, "slam_data.pkl")
    motive_pkl_path = os.path.join(session_path, "motive_data.pkl")

    # --- Section 1 & 2: Health checks ---
    issues, info = check_slam_health(slam_pkl_path)
    all_issues += [("SLAM Health", i) for i in issues]
    all_info_sections.append(("SLAM Health", info))

    issues, info = check_motive_health(motive_pkl_path)
    all_issues += [("Motive Health", i) for i in issues]
    all_info_sections.append(("Motive Health", info))

    issues, info = check_fusion_quality(session_path)
    all_issues += [("Fusion Quality", i) for i in issues]
    all_info_sections.append(("Fusion Quality", info))

    issues, info = check_calibration_sanity(calibration_pkl_path)
    all_issues += [("Calibration Sanity", i) for i in issues]
    all_info_sections.append(("Calibration Sanity", info))

    # --- Section 3: Persistent knowledge ---
    knowledge = session_manager.load_persistent_knowledge(root_path)
    issues, info = review_persistent_knowledge(knowledge)
    all_issues += [("Persistent Knowledge", i) for i in issues]
    all_info_sections.append(("Persistent Knowledge", info))

    # --- Section 4: Knowledge Engine brain report ---
    ke_lines, ke_issues = get_knowledge_engine_section(
        root_path, session_path)
    all_issues += [("Knowledge Engine", i) for i in ke_issues]

    # --- Section 5: This session's discoveries ---
    discovery_lines = get_session_discoveries(session_path)

    # --- Section 6: Safety analysis ---
    safety_lines = get_session_safety(root_path, session_name)

    # --- Section 7: Unresolved questions ---
    question_lines = []
    dlm_path = os.path.join(root_path, "persistent_knowledge",
                            "deep_learning_memory.pkl")
    if os.path.exists(dlm_path):
        with open(dlm_path, "rb") as f:
            mem = pickle.load(f)
        open_qs = [q for q in mem.get("unresolved_questions", [])
                   if not q.get("answered")]
        if open_qs:
            for q in open_qs:
                question_lines.append(f"  ? {q['question']}")
        else:
            question_lines.append("  No pending questions.")
    else:
        question_lines.append("  Knowledge engine not yet initialized.")

    # --- Section 8: Recommendations ---
    recommendation_lines = get_recommendations(root_path, all_issues)

    # ============================================================
    # Write the report
    # ============================================================
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f" CO-PILOT REPORT — version {version:03d}\n")
        f.write(f" Generated (UTC): {utc_now_iso()}\n")
        f.write(f" Session reviewed: {session_name}\n")
        f.write("=" * 70 + "\n\n")

        # Section 1: Issues
        f.write("--- 1. FLAGGED ISSUES (review these first) ---\n")
        if not all_issues:
            f.write("  No issues detected. Everything checked out "
                    "clean.\n")
        else:
            for section, issue in all_issues:
                f.write(f"  [{section}] {issue}\n")
        f.write("\n")

        # Section 2: Detailed info
        f.write("--- 2. DETAILED INFO (health checks) ---\n")
        for section, info_lines in all_info_sections:
            f.write(f"\n  ## {section} ##\n")
            for line in info_lines:
                f.write(f"    {line}\n")
        f.write("\n")

        # Section 3: Knowledge Engine Brain Report
        f.write("--- 3. KNOWLEDGE ENGINE — CUMULATIVE BRAIN "
                "REPORT ---\n")
        f.write("  (Everything the system has learned across ALL "
                "sessions)\n\n")
        for line in ke_lines:
            f.write(f"{line}\n")
        f.write("\n")

        # Section 4: This session's discoveries
        f.write("--- 4. THIS SESSION'S NEW DISCOVERIES ---\n")
        for line in discovery_lines:
            f.write(f"{line}\n")
        f.write("\n")

        # Section 5: Safety analysis
        f.write("--- 5. SAFETY ANALYSIS (this session) ---\n")
        for line in safety_lines:
            f.write(f"{line}\n")
        f.write("\n")

        # Section 6: Unresolved questions
        f.write("--- 6. UNRESOLVED QUESTIONS "
                "(need your input) ---\n")
        for line in question_lines:
            f.write(f"{line}\n")
        f.write("\n")

        # Section 7: Recommendations
        f.write("--- 7. RECOMMENDED NEXT STEPS ---\n")
        for line in recommendation_lines:
            f.write(f"{line}\n")
        f.write("\n")

        # Footer
        f.write("=" * 70 + "\n")
        f.write(" END OF REPORT\n")
        f.write(" This report includes the FULL cumulative brain "
                "snapshot.\n")
        f.write(" Paste it into your AI assistant for review.\n")
        f.write("=" * 70 + "\n")

    print(f"[co_pilot_agent] Report generated: {report_path}")
    if all_issues:
        print(f"[co_pilot_agent] {len(all_issues)} issue(s) flagged.")
    else:
        print("[co_pilot_agent] No issues flagged. Clean run.")

    return report_path


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python co_pilot_agent.py <session_path> "
              "<calibration_pkl_path> [root_path]")
        sys.exit(1)

    session_path_arg = sys.argv[1]
    calibration_path_arg = sys.argv[2]
    root_path_arg = (sys.argv[3] if len(sys.argv) > 3
                     else session_manager.bootstrap_project_root())

    generate_report(root_path_arg, session_path_arg,
                    calibration_path_arg)