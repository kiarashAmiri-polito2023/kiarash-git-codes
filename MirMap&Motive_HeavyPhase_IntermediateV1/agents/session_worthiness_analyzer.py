import os, sys, pickle, json, math
from datetime import datetime, timezone

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_pkl(path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None

def analyze_session_worthiness(session_path, session_name):
    result = {
        "session": session_name,
        "path": session_path,
        "timestamp": utc_now_iso(),
        "dimensions": {},
        "score": 0,
        "grade": "F",
        "recommendations": [],
        "critical_issues": [],
        "paper_ready": False
    }
    
    if not os.path.exists(session_path):
        return result
    
    files = os.listdir(session_path)
    
    # 1. Modality Completeness (25 pts)
    has_motive = "motive_data.pkl" in files
    has_slam = "slam_data.pkl" in files
    has_robot = any("robot" in f.lower() or "cmd" in f.lower() for f in files)
    has_video = any(".avi" in f.lower() for f in files)
    has_fusion = "fused_data.pkl" in files
    has_report = "session_comprehensive_report.txt" in files
    
    modality_score = sum([has_motive, has_slam, has_robot, has_video]) * 5
    if has_fusion and has_report:
        modality_score += 5
    modality_score = min(modality_score, 25)
    
    result["dimensions"]["modality"] = {
        "score": modality_score, "max": 25,
        "motive": has_motive, "slam": has_slam,
        "robot": has_robot, "video": has_video
    }
    
    if not has_slam and has_fusion:
        result["critical_issues"].append("Fusion exists but SLAM missing (LIDAR disconnected)")
    if not has_robot:
        result["critical_issues"].append("No robot command data (/cmd_vel, /odom empty)")
    
    # 2. Data Quality (20 pts)
    quality_score = 20
    quality_issues = []
    fused = load_pkl(os.path.join(session_path, "fused_data.pkl"))
    if fused:
        obs = fused.get("fused_observations", [])
        if len(obs) < 100:
            quality_score -= 10
            quality_issues.append("Too few observations")
    else:
        quality_score = 5
        quality_issues.append("No fused data")
    
    result["dimensions"]["quality"] = {
        "score": quality_score, "max": 20, "issues": quality_issues
    }
    
    # 3. Behavioral Richness (20 pts)
    behavior_score = 0
    if fused:
        safety = fused.get("safety_zone_breakdown", {})
        critical = safety.get("critical", 0)
        warning = safety.get("warning", 0)
        safe = safety.get("safe", 0)
        total = critical + warning + safe
        if total > 0:
            ratio = (critical + warning) / total
            if ratio > 0.1:
                behavior_score += 10
            elif ratio > 0.02:
                behavior_score += 5
            if critical > 5:
                behavior_score += 5
            dirs = fused.get("encounter_directions", {})
            if len(dirs) >= 2:
                behavior_score += 5
    behavior_score = min(behavior_score, 20)
    result["dimensions"]["behavior"] = {"score": behavior_score, "max": 20}
    
    # 4. Safety Density (15 pts)
    safety_score = 0
    kr = os.path.join(session_path, "knowledge_engine_report.txt")
    if os.path.exists(kr):
        with open(kr, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "Critical total" in content:
            try:
                line = [l for l in content.split("\n") if "Critical total" in l][0]
                n = int("".join(c for c in line.split(":")[-1] if c.isdigit()))
                safety_score += 8 if n > 10 else (4 if n > 0 else 0)
            except: pass
        if "Warning total" in content:
            try:
                line = [l for l in content.split("\n") if "Warning total" in l][0]
                n = int("".join(c for c in line.split(":")[-1] if c.isdigit()))
                safety_score += 7 if n > 20 else (3 if n > 0 else 0)
            except: pass
    safety_score = min(safety_score, 15)
    result["dimensions"]["safety"] = {"score": safety_score, "max": 15}
    
    # 5. Cross-Modal (10 pts)
    cross_score = 0
    if "cross_modal_matches.jsonl" in files:
        cross_score += 5
        try:
            with open(os.path.join(session_path, "cross_modal_matches.jsonl"), "r") as f:
                matches = [json.loads(l) for l in f if l.strip()]
            if len(matches) > 0:
                cross_score += 5
        except: pass
    elif has_motive and has_slam:
        result["recommendations"].append("Run cross_modal_aligner")
    result["dimensions"]["cross_modal"] = {"score": cross_score, "max": 10}
    
    # 6. Novelty (10 pts)
    novelty_score = 0
    if os.path.exists(kr):
        with open(kr, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "NEW object" in content:
            novelty_score += min(content.count("NEW object") * 3, 6)
        if "Human zones" in content:
            novelty_score += 2
        if "Label transfers" in content:
            novelty_score += 2
    novelty_score = min(novelty_score, 10)
    result["dimensions"]["novelty"] = {"score": novelty_score, "max": 10}
    
    total = modality_score + quality_score + behavior_score + safety_score + cross_score + novelty_score
    result["score"] = total
    
    if total >= 80:
        result["grade"] = "A"; result["paper_ready"] = True
    elif total >= 65:
        result["grade"] = "B"; result["paper_ready"] = True
    elif total >= 50:
        result["grade"] = "C"
    elif total >= 30:
        result["grade"] = "D"
    
    return result

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sessions_dir = os.path.join(root, "sessions")
    
    if not os.path.exists(sessions_dir):
        print("ERROR: sessions directory not found")
        return
    
    dirs = sorted([d for d in os.listdir(sessions_dir)
                   if d.startswith("session_") and os.path.isdir(os.path.join(sessions_dir, d))])
    
    results = []
    for name in dirs:
        path = os.path.join(sessions_dir, name)
        r = analyze_session_worthiness(path, name)
        results.append(r)
    
    lines = ["=" * 70, " DATASET HEALTH & SESSION WORTHINESS REPORT", f" Generated: {utc_now_iso()}", "=" * 70]
    paper_ready = sum(1 for r in results if r["paper_ready"])
    avg = sum(r["score"] for r in results) / max(len(results), 1)
    lines.append(f"\nTotal Sessions Analyzed: {len(results)}")
    lines.append(f"Paper-Ready Sessions: {paper_ready} / {len(results)}")
    lines.append(f"Average Worthiness Score: {avg:.1f} / 100")
    lines.append(f"Target for ICRA/IROS: 10 sessions with score >= 65")
    lines.append(f"Gap: {max(0, 10 - paper_ready)} more quality sessions needed")
    lines.append("\n" + "-" * 70)
    lines.append(" SESSION BREAKDOWN & EVALUATION")
    lines.append("-" * 70)
    
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        status = "PAPER-READY (VALID)" if r["paper_ready"] else "UNQUALIFIED (RE-RECORD NEEDED)"
        lines.append(f"\n[{r['grade']}] {r['session']} -> Score: {r['score']}/100 ({status})")
        for dim, data in r["dimensions"].items():
            bar_len = int(data["score"] / data["max"] * 20)
            bar = "#" * bar_len + "." * (20 - bar_len)
            lines.append(f"    {dim:<12}: [{bar}] {data['score']}/{data['max']}")
        for issue in r["critical_issues"]:
            lines.append(f"    [!] {issue}")
    
    report = "\n".join(lines)
    print(report)
    
    report_path = os.path.join(sessions_dir, "dataset_health_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    json_path = os.path.join(sessions_dir, "session_worthiness.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

if __name__ == "__main__":
    main()