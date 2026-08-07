#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quality_gate.py — Flag Generator (v2)

Per Master Doc section 15.3:
  This agent is NO LONGER a "judge" that decides pass/fail.
  Instead, it ONLY generates flags (informational warnings)
  about potential issues in the session data.

  The flags are written to the session's comprehensive report,
  and later used by the AI Advisor and human reviewer to make
  the final merge/no-merge decision.

Responsibilities:
  - Flag data quality issues (zero-placeholder, untracked, etc.)
  - Flag statistical outliers (safety events, anomalies, etc.)
  - Flag duplicate/redundant data
  - Flag reference bugs (shared dicts)
  - Flag low-confidence classifications
  - Flag empty sessions (no Motive objects)
  - Flag suspicious speeds/positions
  - Calculate Learning Progress Score (section 15.4)

Output:
  - Writes a "QUALITY GATE FLAGS" section to the session's
    comprehensive report file.
  - Returns a dict of flags for programmatic use (e.g. by
    run_session_analysis.py).
"""

import os
import sys
import math
import pickle
import datetime
from datetime import timezone
import statistics
from collections import defaultdict

# Make sibling imports work
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from knowledge_engine import load_deep_memory


# ============================================================
# Constants
# ============================================================
ZERO_PLACEHOLDER_EPSILON_M = 0.05  # From spatial_temporal_fusion

# Statistical thresholds
SAFETY_EVENTS_OUTLIER_SIGMA = 3.0
ANOMALIES_OUTLIER_SIGMA = 3.0
LOW_CONFIDENCE_THRESHOLD = 0.5
LOW_CONFIDENCE_PERCENT_THRESHOLD = 30.0

# Speed thresholds
SUSPICIOUS_SPEED_MPS = 5.0  # 5 m/s = 18 km/h — unlikely for humans/robots

# Learning Progress Score weights
WEIGHT_NEW_OBJECTS = 0.4
WEIGHT_CONFIDENCE_IMPROVEMENT = 0.3
WEIGHT_VARIANCE_REDUCTION = 0.2
WEIGHT_UNKNOWN_REDUCTION = 0.1


# ============================================================
# Flag generation
# ============================================================
def _flag_zero_placeholder(fused_data_stats):
    """
    Flag if too many Motive samples were zero-placeholder.
    """
    total = (fused_data_stats.get("motive_samples_matched", 0) +
             fused_data_stats.get("motive_samples_skipped_untracked", 0) +
             fused_data_stats.get("motive_samples_skipped_time_gap", 0) +
             fused_data_stats.get("motive_samples_skipped_zero_placeholder", 0))

    if total == 0:
        return None

    zero_count = fused_data_stats.get(
        "motive_samples_skipped_zero_placeholder", 0)
    zero_pct = 100.0 * zero_count / total

    if zero_pct > 20.0:
        return {
            "type": "data_quality",
            "severity": "warning",
            "description": (
                f"High zero-placeholder rate: {zero_pct:.1f}% "
                f"({zero_count}/{total}) of Motive samples were "
                f"skipped as zero-placeholder. This may indicate "
                f"tracking glitches or calibration issues."),
            "suggested_action": (
                "Review Motive tracking quality. Check if "
                f"epsilon={ZERO_PLACEHOLDER_EPSILON_M}m is "
                f"appropriate."),
        }
    return None


def _flag_duplicate_positions(fused_objects):
    """
    Flag if two different objects have the same position.
    """
    pos_map = defaultdict(list)
    for obs in fused_objects:
        if obs.get("source") != "motive":
            continue
        pos = tuple(obs.get("position_mir_frame_m", [0, 0]))
        pos_map[pos].append(obs["object_name"])

    flags = []
    for pos, names in pos_map.items():
        if len(names) > 1:
            flags.append({
                "type": "data_quality",
                "severity": "critical",
                "description": (
                    f"Duplicate position detected: {names} all at "
                    f"position {pos}. This may indicate a tracking "
                    f"error or mislabeling."),
                "suggested_action": (
                    "Review Motive rigid body definitions. Check "
                    f"if multiple markers are assigned the same name."),
            })
    return flags if flags else None


def _flag_reference_bug(fused_objects):
    """
    Flag if two objects share the same Python dict (reference bug).
    """
    seen_ids = {}
    flags = []
    for obs in fused_objects:
        if obs.get("source") != "motive":
            continue
        obj_id = id(obs)
        if obj_id in seen_ids:
            flags.append({
                "type": "data_quality",
                "severity": "critical",
                "description": (
                    f"Reference bug detected: object '{obs['object_name']}' "
                    f"shares the same Python dict as '{seen_ids[obj_id]}'. "
                    f"This is a serious data corruption issue."),
                "suggested_action": (
                    "Check the code that generates fused_data.pkl. "
                    f"This should never happen."),
            })
        else:
            seen_ids[obj_id] = obs["object_name"]
    return flags if flags else None


def _flag_low_confidence(session_results):
    """
    Flag if too many objects have low classification confidence.
    """
    object_features = session_results.get("object_features", {})
    if not object_features:
        return None

    low_conf = [name for name, feat in object_features.items()
                if feat.get("confidence", 1.0) < LOW_CONFIDENCE_THRESHOLD]
    low_pct = 100.0 * len(low_conf) / len(object_features)

    if low_pct > LOW_CONFIDENCE_PERCENT_THRESHOLD:
        return {
            "type": "classification",
            "severity": "warning",
            "description": (
                f"Low confidence rate: {low_pct:.1f}% "
                f"({len(low_conf)}/{len(object_features)}) of objects "
                f"have confidence < {LOW_CONFIDENCE_THRESHOLD}. "
                f"Classification may be unreliable."),
            "suggested_action": (
                "Review object names and tracking quality. "
                f"Consider manual labeling for uncertain objects."),
        }
    return None


def _flag_statistical_outliers(session_results, memory):
    """
    Flag if this session's safety events or anomalies are
    statistical outliers compared to historical baseline.
    """
    flags = []

    # Safety events
    safety_events = session_results.get("safety_events", [])
    n_safety = len(safety_events)
    n_critical = sum(1 for e in safety_events if e["zone"] == "critical")
    n_warning = sum(1 for e in safety_events if e["zone"] == "warning")

    historical_safety = memory.get("safety_statistics", {})
    historical_critical = historical_safety.get("total_critical", 0)
    historical_warning = historical_safety.get("total_warning", 0)
    historical_sessions = memory.get("total_sessions_analyzed", 1)

    avg_critical = historical_critical / historical_sessions
    avg_warning = historical_warning / historical_sessions

    if historical_sessions >= 3:  # Only flag if we have enough history
        if n_critical > avg_critical + SAFETY_EVENTS_OUTLIER_SIGMA * math.sqrt(avg_critical):
            flags.append({
                "type": "statistical_outlier",
                "severity": "warning",
                "description": (
                    f"Unusually high critical safety events: {n_critical} "
                    f"(historical avg: {avg_critical:.1f}, "
                    f"3σ threshold: {avg_critical + SAFETY_EVENTS_OUTLIER_SIGMA * math.sqrt(avg_critical):.1f})."),
                "suggested_action": (
                    "Review this session for real safety incidents. "
                    f"Check if sensor noise or calibration drift occurred."),
            })

        if n_warning > avg_warning + SAFETY_EVENTS_OUTLIER_SIGMA * math.sqrt(avg_warning):
            flags.append({
                "type": "statistical_outlier",
                "severity": "info",
                "description": (
                    f"Unusually high warning safety events: {n_warning} "
                    f"(historical avg: {avg_warning:.1f}, "
                    f"3σ threshold: {avg_warning + SAFETY_EVENTS_OUTLIER_SIGMA * math.sqrt(avg_warning):.1f})."),
                "suggested_action": (
                    "Review this session for potential safety trends."),
            })

    # Anomalies
    anomalies = session_results.get("anomalies", [])
    n_anomalies = len(anomalies)

    historical_anomalies = len(memory.get("anomalies", []))
    avg_anomalies = historical_anomalies / historical_sessions

    if historical_sessions >= 3:
        if n_anomalies > avg_anomalies + ANOMALIES_OUTLIER_SIGMA * math.sqrt(avg_anomalies):
            flags.append({
                "type": "statistical_outlier",
                "severity": "warning",
                "description": (
                    f"Unusually high anomalies: {n_anomalies} "
                    f"(historical avg: {avg_anomalies:.1f}, "
                    f"3σ threshold: {avg_anomalies + ANOMALIES_OUTLIER_SIGMA * math.sqrt(avg_anomalies):.1f})."),
                "suggested_action": (
                    "Review anomaly list below. Check for sensor "
                    f"malfunctions or environmental changes."),
            })

    return flags if flags else None


def _flag_empty_session(session_results):
    """
    Flag if no Motive objects were detected (empty session).
    """
    object_features = session_results.get("object_features", {})
    if not object_features:
        return {
            "type": "data_quality",
            "severity": "warning",
            "description": (
                "No Motive objects detected in this session. "
                f"This may indicate Motive was not running, or "
                f"all objects were filtered out."),
            "suggested_action": (
                "Verify Motive was recording during this session. "
                f"Check if all objects were untracked or zero-placeholder."),
        }
    return None


def _flag_excessive_anomalies(session_results):
    """
    Flag if too many anomalies were detected.
    """
    anomalies = session_results.get("anomalies", [])
    if len(anomalies) > 5:
        return {
            "type": "data_quality",
            "severity": "warning",
            "description": (
                f"High number of anomalies: {len(anomalies)}. "
                f"This may indicate tracking issues or "
                f"environmental instability."),
            "suggested_action": (
                "Review anomaly list below. Check for sensor "
                f"noise or calibration drift."),
        }
    return None


def _flag_suspicious_speed(session_results):
    """
    Flag if any object has suspiciously high speed.
    """
    object_features = session_results.get("object_features", {})
    flags = []
    for name, feat in object_features.items():
        max_speed = feat.get("max_speed_mps", 0.0)
        if max_speed > SUSPICIOUS_SPEED_MPS:
            flags.append({
                "type": "data_quality",
                "severity": "warning",
                "description": (
                    f"Suspiciously high speed: '{name}' reached "
                    f"{max_speed:.2f} m/s (>{SUSPICIOUS_SPEED_MPS} m/s). "
                    f"This is unlikely for humans or static objects."),
                "suggested_action": (
                    "Review tracking quality for this object. "
                    f"Check if it's a sensor glitch."),
            })
    return flags if flags else None


def _flag_learning_stagnation(session_results, memory):
    """
    Flag if this session didn't contribute new knowledge.
    """
    object_features = session_results.get("object_features", {})
    known_objects = set(memory.get("object_tracks", {}).keys())
    new_objects = [name for name in object_features
                   if name not in known_objects]

    if not new_objects and len(object_features) > 0:
        return {
            "type": "learning_progress",
            "severity": "info",
            "description": (
                f"No new objects learned: all {len(object_features)} "
                f"objects were already known. This session may not "
                f"have added new knowledge."),
            "suggested_action": (
                "Consider varying the environment or adding new "
                f"objects to improve learning."),
        }
    return None


# ============================================================
# Learning Progress Score (section 15.4)
# ============================================================
def _calculate_learning_progress(session_results, memory):
    """
    Calculates a score (0-100) indicating how much this session
    contributed to learning. Higher = more valuable.

    Components:
      - % successful label transfer (should increase over time)
      - Reduction in confidence variance between sessions
      - Reduction in "unknown" classifications
      - Number of new patterns discovered
    """
    if memory.get("total_sessions_analyzed", 0) < 2:
        return 100.0  # First few sessions always get max score

    # Component 1: New objects
    object_features = session_results.get("object_features", {})
    known_objects = set(memory.get("object_tracks", {}).keys())
    new_objects = [name for name in object_features
                   if name not in known_objects]
    new_objects_score = min(1.0, len(new_objects) / 5.0)  # Cap at 5 new objects

    # Component 2: Confidence improvement
    confidences = []
    for name, feat in object_features.items():
        if name in known_objects:
            track = memory["object_tracks"][name]
            old_conf = track.get("confidence", 0.5)
            new_conf = feat.get("confidence", 0.5)
            confidences.append(new_conf - old_conf)

    avg_conf_improvement = statistics.mean(confidences) if confidences else 0.0
    conf_score = min(1.0, max(0.0, avg_conf_improvement * 2.0))  # Cap at 0.5 improvement

    # Component 3: Variance reduction
    variances = []
    for name, feat in object_features.items():
        if name in known_objects:
            track = memory["object_tracks"][name]
            old_var = track.get("position_variance_m2", 0.1)
            new_var = feat.get("position_variance_m2", 0.1)
            variances.append(old_var - new_var)

    avg_var_reduction = statistics.mean(variances) if variances else 0.0
    var_score = min(1.0, max(0.0, avg_var_reduction * 10.0))  # Cap at 0.1 m² reduction

    # Component 4: Unknown reduction
    unknown_before = sum(1 for track in memory["object_tracks"].values()
                         if track.get("classification") == "unknown")
    unknown_after = sum(1 for feat in object_features.values()
                        if feat.get("classification") == "unknown")
    unknown_reduction = max(0.0, unknown_before - unknown_after)
    unknown_score = min(1.0, unknown_reduction / 5.0)  # Cap at 5 unknowns resolved

    # Weighted sum
    score = (
        WEIGHT_NEW_OBJECTS * new_objects_score +
        WEIGHT_CONFIDENCE_IMPROVEMENT * conf_score +
        WEIGHT_VARIANCE_REDUCTION * var_score +
        WEIGHT_UNKNOWN_REDUCTION * unknown_score
    ) * 100.0

    return min(100.0, max(0.0, score))


# ============================================================
# Main entry point
# ============================================================
def run_quality_gate(root_path, session_path):
    """
    Runs all flag checks and writes results to the session's
    comprehensive report file.

    Returns:
      - dict of all flags (for programmatic use)
      - learning progress score
    """
    # Load candidate
    candidate_path = os.path.join(
        session_path, "pending_merge_candidate.pkl")
    if not os.path.exists(candidate_path):
        print(f"[quality_gate] No candidate found in {session_path}")
        return None, 0.0

    with open(candidate_path, "rb") as f:
        candidate = pickle.load(f)

    session_results = candidate.get("session_results", {})
    fused_data_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_data_path):
        print(f"[quality_gate] No fused_data.pkl found")
        return None, 0.0

    with open(fused_data_path, "rb") as f:
        fused_data = pickle.load(f)

    fused_stats = fused_data.get("stats", {})
    fused_objects = fused_data.get("fused_objects", [])

    # Load historical memory for comparison
    memory = load_deep_memory(root_path)

    # Generate all flags
    all_flags = []

    # Data quality flags
    if flag := _flag_zero_placeholder(fused_stats):
        all_flags.append(flag)
    if flags := _flag_duplicate_positions(fused_objects):
        all_flags.extend(flags)
    if flags := _flag_reference_bug(fused_objects):
        all_flags.extend(flags)
    if flag := _flag_low_confidence(session_results):
        all_flags.append(flag)
    if flag := _flag_empty_session(session_results):
        all_flags.append(flag)
    if flag := _flag_excessive_anomalies(session_results):
        all_flags.append(flag)
    if flags := _flag_suspicious_speed(session_results):
        all_flags.extend(flags)
    if flags := _flag_statistical_outliers(session_results, memory):
        all_flags.extend(flags)
    if flag := _flag_learning_stagnation(session_results, memory):
        all_flags.append(flag)

    # Calculate learning progress score
    learning_score = _calculate_learning_progress(
        session_results, memory)

    # Write to comprehensive report
    report_path = os.path.join(
        session_path, "session_comprehensive_report.txt")

    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + "=" * 60 + "\n")
        f.write(" QUALITY GATE FLAGS\n")
        f.write("=" * 60 + "\n")
        f.write(f"Generated at (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
        f.write(f"Learning Progress Score: {learning_score:.1f}/100.0\n")
        f.write(f"  (Higher = this session contributed more to learning)\n\n")

        if not all_flags:
            f.write("No flags raised. This session appears clean.\n")
        else:
            f.write(f"Flags raised: {len(all_flags)}\n\n")
            for i, flag in enumerate(all_flags, 1):
                f.write(f"  {i}. [{flag['severity'].upper()}] {flag['description']}\n")
                f.write(f"     Suggested action: {flag['suggested_action']}\n\n")

        # Include anomaly details if any
        anomalies = session_results.get("anomalies", [])
        if anomalies:
            f.write("\n--- ANOMALY DETAILS ---\n")
            for anom in anomalies:
                f.write(f"  [{anom['severity']}] {anom['description']}\n")

    print(f"[quality_gate] Wrote {len(all_flags)} flags to {report_path}")
    print(f"[quality_gate] Learning Progress Score: {learning_score:.1f}/100.0")

    return all_flags, learning_score
