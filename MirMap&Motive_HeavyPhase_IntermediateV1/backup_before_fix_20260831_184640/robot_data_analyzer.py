#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_data_analyzer.py - Analyzes MiR command data (v1.0)
Extracts action patterns for VLA training.
"""
import os, sys, pickle, math
from datetime import datetime, timezone
from collections import Counter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def analyze_robot_data(session_path):
    pkl = os.path.join(session_path, "mir_command_data.pkl")
    if not os.path.exists(pkl):
        return None
    with open(pkl, "rb") as f:
        data = pickle.load(f)
    
    result = {
        "session_path": session_path,
        "analyzed_at_utc": utc_now_iso(),
        "action_summary": {},
        "safety_summary": {},
        "movement_patterns": {},
        "state_summary": {}
    }
    
    cmd = data.get("cmd_vel_log", [])
    if cmd:
        speeds = [c["speed_mps"] for c in cmd]
        ang = [abs(c.get("angular_z_rps", 0)) for c in cmd]
        moving = sum(1 for s in speeds if s > 0.05)
        result["action_summary"] = {
            "total_commands": len(cmd),
            "avg_commanded_speed_mps": sum(speeds)/len(speeds),
            "max_commanded_speed_mps": max(speeds),
            "moving_commands_pct": round(100*moving/len(cmd), 1),
            "stopped_commands_pct": round(100*(len(cmd)-moving)/len(cmd), 1),
            "forward_commands": sum(1 for c in cmd if c.get("linear_x_mps",0) > 0.05),
            "backward_commands": sum(1 for c in cmd if c.get("linear_x_mps",0) < -0.05),
            "turning_commands": sum(1 for a in ang if a > 0.1),
            "max_angular_speed_rps": max(ang) if ang else 0
        }
    
    odom = data.get("odom_log", [])
    if odom:
        actual = [o["actual_speed_mps"] for o in odom]
        result["movement_patterns"] = {
            "avg_actual_speed_mps": sum(actual)/len(actual),
            "max_actual_speed_mps": max(actual),
            "odom_samples": len(odom)
        }
    
    events = data.get("safety_events", [])
    types = Counter(e["type"] for e in events)
    result["safety_summary"] = {
        "total_events": len(events),
        "by_type": dict(types),
        "sudden_stops": types.get("sudden_stop", 0),
        "manual_overrides": types.get("manual_override", 0)
    }
    
    rest = data.get("rest_state_log", [])
    if rest:
        states = Counter(s.get("state_text") for s in rest if s.get("state_text"))
        modes = Counter(s.get("mode_text") for s in rest if s.get("mode_text"))
        missions = Counter(s.get("mission_text") for s in rest if s.get("mission_text"))
        result["state_summary"] = {
            "state_distribution": dict(states),
            "mode_distribution": dict(modes),
            "mission_distribution": dict(missions),
            "rest_polls_total": len(rest)
        }
    
    return result


def generate_report_section(analysis):
    if not analysis:
        return "\n--- ROBOT COMMAND ANALYSIS ---\n  No robot data available.\n"
    lines = ["", "=" * 60, " ROBOT COMMAND & ACTION ANALYSIS", "=" * 60]
    a = analysis.get("action_summary", {})
    if a:
        lines.append("\n--- COMMANDED ACTIONS (from /cmd_vel) ---")
        lines.append(f"  Total commands       : {a.get('total_commands',0)}")
        lines.append(f"  Avg speed            : {a.get('avg_commanded_speed_mps',0):.3f} m/s")
        lines.append(f"  Max speed            : {a.get('max_commanded_speed_mps',0):.3f} m/s")
        lines.append(f"  Moving / Stopped     : {a.get('moving_commands_pct',0)}% / {a.get('stopped_commands_pct',0)}%")
        lines.append(f"  Forward / Backward   : {a.get('forward_commands',0)} / {a.get('backward_commands',0)}")
        lines.append(f"  Turning commands     : {a.get('turning_commands',0)}")
    m = analysis.get("movement_patterns", {})
    if m:
        lines.append("\n--- ACTUAL MOVEMENT (from /odom) ---")
        lines.append(f"  Avg actual speed     : {m.get('avg_actual_speed_mps',0):.3f} m/s")
        lines.append(f"  Max actual speed     : {m.get('max_actual_speed_mps',0):.3f} m/s")
    s = analysis.get("safety_summary", {})
    if s:
        lines.append("\n--- SAFETY EVENTS ---")
        lines.append(f"  Total events         : {s.get('total_events',0)}")
        lines.append(f"  Sudden stops         : {s.get('sudden_stops',0)}")
        lines.append(f"  Manual overrides     : {s.get('manual_overrides',0)}")
    st = analysis.get("state_summary", {})
    if st:
        lines.append("\n--- ROBOT STATE (REST API) ---")
        lines.append(f"  REST polls           : {st.get('rest_polls_total',0)}")
        for k, v in st.get("state_distribution", {}).items():
            lines.append(f"    State: {k} = {v}")
        for k, v in st.get("mode_distribution", {}).items():
            lines.append(f"    Mode : {k} = {v}")
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python robot_data_analyzer.py <session_path>")
        sys.exit(1)
    session = sys.argv[1]
    analysis = analyze_robot_data(session)
    if not analysis:
        print("No robot data found.")
        sys.exit(1)
    out_pkl = os.path.join(session, "robot_analysis.pkl")
    with open(out_pkl, "wb") as f:
        pickle.dump(analysis, f)
    report = generate_report_section(analysis)
    with open(os.path.join(session, "robot_analysis_report.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
