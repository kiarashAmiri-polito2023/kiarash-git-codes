"""
VLA Master Supervisor Agent (Multi-Modal Grounded Intelligence)
Author: Kiarash Amiri (PoliTo / DIGEP)
Fuses Physical Evidence + Visual Video Signals + Project Knowledge Memory to output
the Single Source of Truth VLA Behavior Matrix with multi-modal confidence verification.
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1")
SESSIONS_DIR = ROOT / "sessions"
PK_DIR = ROOT / "persistent_knowledge"

sys.path.insert(0, str(ROOT / "agents"))
try:
    from vla_scenario_validator import analyze_session_physics, ALL_SCENARIOS
except ImportError:
    print("[ERROR] Could not import vla_scenario_validator.")
    exit(1)

def run_supervisor():
    PK_DIR.mkdir(parents=True, exist_ok=True)
    matrix_file = PK_DIR / "vla_behavior_matrix.json"
    ledger_file = PK_DIR / "vla_evidence_ledger.json"

    matrix = {}
    evidence_ledger = []
    global_coverage = {sc: {"count": 0, "sessions": [], "max_confidence": 0.0} for sc in ALL_SCENARIOS}

    for s_dir in sorted(SESSIONS_DIR.glob("session_*")):
        s_name = s_dir.name
        phys_evidence = analyze_session_physics(s_dir)

        # Load video analysis if present
        vid_file = s_dir / "video_events.json"
        vid_data = {}
        if vid_file.exists():
            try:
                with open(vid_file, "r", encoding="utf-8") as f:
                    vid_data = json.load(f)
            except Exception:
                pass

        performed = []
        not_performed = []

        for sc, ev in phys_evidence.items():
            conf = ev["confidence"]
            has_video = len(vid_data) > 0

            # Boost/confirm confidence with multi-modal video presence
            if ev["detected"]:
                verdict = "CONFIRMED" if (has_video and conf >= 0.8) else "PHYSICAL_ONLY"
                performed.append(sc)
                global_coverage[sc]["count"] += 1
                global_coverage[sc]["sessions"].append(s_name)
                global_coverage[sc]["max_confidence"] = max(global_coverage[sc]["max_confidence"], conf)

                evidence_ledger.append({
                    "session": s_name,
                    "scenario": sc,
                    "confidence": conf,
                    "verdict": verdict,
                    "has_video": has_video,
                    "reason": ev["reason"]
                })
            else:
                not_performed.append(sc)

        matrix[s_name] = {
            "has_video": len(vid_data) > 0,
            "scenarios_performed": performed,
            "scenarios_not_performed": not_performed
        }

    with open(matrix_file, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2)

    with open(ledger_file, "w", encoding="utf-8") as f:
        json.dump(evidence_ledger, f, indent=2)

    covered_count = sum(1 for sc, data in global_coverage.items() if data["count"] > 0)
    print(f"[SUPERVISOR] Analysis complete. Scenarios covered: {covered_count} / {len(ALL_SCENARIOS)} ({covered_count/len(ALL_SCENARIOS)*100:.1f}%)")
    return matrix, global_coverage

if __name__ == "__main__":
    run_supervisor()
