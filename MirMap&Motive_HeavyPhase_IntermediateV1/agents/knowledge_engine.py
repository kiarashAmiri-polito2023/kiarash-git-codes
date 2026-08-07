#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knowledge_engine.py — Cumulative Learning Brain (v2.2)
SAFE MODE: No auto-merge. Use analyze_session_safe() + apply_merge.py.
"""
import os, sys, copy, math, pickle, time, glob
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

try:
    from sklearn.cluster import DBSCAN
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

SAFETY_CRITICAL_M = 0.10
SAFETY_WARNING_M = 0.30
ROBOT_NAME_KEYWORDS = ("mir", "robot")
REFERENCE_BODY_NAMES = {"Global Coordinate", "ground"}
HUMAN_NAME_KEYWORDS = ("hat", "wrist", "hand", "head", "human")
STATIC_NAME_KEYWORDS = ("station", "warehouse", "table", "shelf")
STATIC_VARIANCE_THRESHOLD = 0.01
MOVING_VARIANCE_THRESHOLD = 0.10
LIDAR_CLUSTER_EPS_M = 0.3
LIDAR_CLUSTER_MIN_SAMPLES = 5
LIDAR_MOTIVE_MATCH_RADIUS_M = 0.5
SPATIAL_GRID_RESOLUTION_M = 0.5
TRAJECTORY_MIN_LENGTH = 5
PENDING_CANDIDATE_FILENAME = "pending_merge_candidate.pkl"
PENDING_CANDIDATE_SUMMARY = "pending_merge_candidate_summary.txt"
MAX_PHYSICAL_SPEED_MPS = 5.0  # v2.2: humans <5 m/s

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def safe_pickle_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)

def _empty_deep_memory():
    return {
        "schema_version": "deep_memory_v2",
        "created_at_utc": utc_now_iso(),
        "last_updated_utc": utc_now_iso(),
        "total_sessions_analyzed": 0,
        "sessions_analyzed_list": [],
        "object_tracks": {},
        "lidar_clusters": {"labeled_patterns": [], "unlabeled_patterns": [], "label_transfer_log": []},
        "spatial_priors": {"human_presence_grid": {}, "static_object_grid": {}, "high_risk_grid": {}, "dynamic_obstacle_grid": {}},
        "safety_events": [],
        "safety_statistics": {"total_critical": 0, "total_warning": 0, "worst_distance_ever_m": None, "worst_event": None},
        "interaction_priors": {"approach_speed_by_class": {}, "distance_by_class": {}, "encounter_direction_by_class": {}, "time_to_contact_by_class": {}},
        "trajectory_patterns": {"human_trajectories": [], "robot_trajectories": [], "repeated_paths": []},
        "temporal_patterns": {"human_activity_by_hour": {str(h): 0 for h in range(24)}, "session_durations": [], "events_timeline": []},
        "user_feedback_history": [], "unresolved_questions": [], "anomalies": [], "learned_insights": [], "classification_history": []
    }

def load_deep_memory(root_path):
    path = os.path.join(root_path, "persistent_knowledge", "deep_learning_memory.pkl")
    if not os.path.exists(path):
        return _empty_deep_memory()
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not isinstance(data, dict) or "object_tracks" not in data:
            return _empty_deep_memory()
        return data
    except Exception:
        return _empty_deep_memory()

def save_deep_memory(root_path, memory):
    pk_dir = os.path.join(root_path, "persistent_knowledge")
    os.makedirs(pk_dir, exist_ok=True)
    memory["last_updated_utc"] = utc_now_iso()
    pkl_path = os.path.join(pk_dir, "deep_learning_memory.pkl")
    safe_pickle_dump(memory, pkl_path)
    return pkl_path

def _is_robot(name):
    return any(k in name.lower() for k in ROBOT_NAME_KEYWORDS)

def _is_reference(name):
    return name in REFERENCE_BODY_NAMES

def _safety_zone(distance_m):
    if distance_m < SAFETY_CRITICAL_M: return "critical"
    elif distance_m < SAFETY_WARNING_M: return "warning"
    return "safe"

def _classify_by_name(name):
    nl = name.lower()
    if any(k in nl for k in HUMAN_NAME_KEYWORDS): return "human_marker", 0.7
    if any(k in nl for k in STATIC_NAME_KEYWORDS): return "static_infrastructure", 0.7
    return "unknown", 0.5

def _grid_key(x, y):
    return f"{int(x // SPATIAL_GRID_RESOLUTION_M)}_{int(y // SPATIAL_GRID_RESOLUTION_M)}"

def _safe_div(a, b, default=0.0):
    return a / b if b != 0 else default

def cluster_lidar_points(fused_objects):
    if not HAS_SKLEARN: return []
    scan_groups = defaultdict(list)
    for obs in fused_objects:
        if obs.get("source") != "slam_lidar": continue
        pos = obs.get("position_mir_frame_m")
        if pos is None: continue
        scan_groups[obs.get("object_name", "")].append({"position": pos, "distance": obs.get("distance_to_robot_edge_m", 999), "timestamp": obs.get("timestamp_utc", 0), "robot_pos": obs.get("robot_position_m", [0, 0])})
    all_clusters = []
    for scan_name, points in scan_groups.items():
        if len(points) < LIDAR_CLUSTER_MIN_SAMPLES: continue
        positions = np.array([p["position"] for p in points])
        try:
            clustering = DBSCAN(eps=LIDAR_CLUSTER_EPS_M, min_samples=LIDAR_CLUSTER_MIN_SAMPLES).fit(positions)
        except Exception: continue
        for label in set(clustering.labels_):
            if label == -1: continue
            mask = clustering.labels_ == label
            cp = positions[mask]
            centroid = cp.mean(axis=0).tolist()
            w, l = float(np.ptp(cp[:, 0])), float(np.ptp(cp[:, 1]))
            all_clusters.append({"scan_name": scan_name, "cluster_id": int(label), "centroid_m": centroid, "n_points": int(mask.sum()), "width_m": w, "length_m": l, "area_m2": w * l, "compactness": _safe_div(int(mask.sum()), w * l * 100), "min_distance_to_robot_m": min(p["distance"] for p, m in zip(points, mask) if m), "timestamp": points[0]["timestamp"], "robot_position_m": points[0]["robot_pos"], "label": None, "label_confidence": 0.0})
    return all_clusters

def transfer_labels_to_clusters(motive_features, lidar_clusters):
    transfers = []
    for cluster in lidar_clusters:
        best_match, best_dist = None, LIDAR_MOTIVE_MATCH_RADIUS_M
        for name, feat in motive_features.items():
            mp = feat.get("mean_position_m", [0, 0])
            d = math.hypot(mp[0] - cluster["centroid_m"][0], mp[1] - cluster["centroid_m"][1])
            if d < best_dist: best_dist, best_match = d, name
        if best_match:
            mc = motive_features[best_match].get("classification", "unknown")
            cluster["label"] = mc
            cluster["label_confidence"] = max(0.0, 1.0 - best_dist / LIDAR_MOTIVE_MATCH_RADIUS_M)
            transfers.append({"cluster_centroid": cluster["centroid_m"], "motive_object": best_match, "motive_class": mc, "distance_m": best_dist, "confidence": cluster["label_confidence"]})
    return transfers

def extract_session_features(fused_data):
    fused_objects = fused_data.get("fused_objects", [])
    groups = defaultdict(list)
    for obs in fused_objects:
        if obs.get("source") != "motive": continue
        name = obs.get("object_name", "")
        if _is_robot(name) or _is_reference(name): continue
        groups[name].append(obs)
    object_features, safety_events, trajectories = {}, [], {}
    for name, observations in groups.items():
        if len(observations) < 2: continue
        observations.sort(key=lambda o: o["timestamp_utc"])
        positions = np.array([o["position_mir_frame_m"] for o in observations])
        mean_pos = positions.mean(axis=0).tolist()
        pos_variance = float(np.var(np.linalg.norm(positions - positions.mean(axis=0), axis=1)))
        heights = [o["height_m"] for o in observations if o.get("height_m") is not None]
        mean_height = float(np.mean(heights)) if heights else None
        speeds, accelerations, jerks = [], [], []
        direction_changes, stop_go_count, prev_heading, was_stopped = 0, 0, None, True
        for i in range(1, len(observations)):
            dt = observations[i]["timestamp_utc"] - observations[i-1]["timestamp_utc"]
            if dt <= 0.001: continue
            dx = observations[i]["position_mir_frame_m"][0] - observations[i-1]["position_mir_frame_m"][0]
            dy = observations[i]["position_mir_frame_m"][1] - observations[i-1]["position_mir_frame_m"][1]
            speed = math.hypot(dx, dy) / dt
            if speed > MAX_PHYSICAL_SPEED_MPS:
                continue  # v2.2: skip tracking glitch
            speeds.append(speed)
            if len(speeds) >= 2:
                accel = (speeds[-1] - speeds[-2]) / dt
                accelerations.append(accel)
                if len(accelerations) >= 2: jerks.append((accelerations[-1] - accelerations[-2]) / dt)
            heading = math.atan2(dy, dx)
            if prev_heading is not None and abs((heading - prev_heading + math.pi) % (2 * math.pi) - math.pi) > math.radians(30): direction_changes += 1
            prev_heading = heading
            is_stopped = speed < 0.05
            if was_stopped and not is_stopped: stop_go_count += 1
            was_stopped = is_stopped
        mean_speed = float(np.mean(speeds)) if speeds else 0.0
        max_speed = float(np.max(speeds)) if speeds else 0.0
        mean_jerk = float(np.mean(np.abs(jerks))) if jerks else 0.0
        path_length = sum(np.linalg.norm(positions[i] - positions[i-1]) for i in range(1, len(positions)))
        time_critical = sum(observations[i]["timestamp_utc"] - observations[i-1]["timestamp_utc"] for i in range(1, len(observations)) if observations[i].get("distance_to_robot_edge_m", 999) < SAFETY_CRITICAL_M)
        time_warning = sum(observations[i]["timestamp_utc"] - observations[i-1]["timestamp_utc"] for i in range(1, len(observations)) if SAFETY_CRITICAL_M <= observations[i].get("distance_to_robot_edge_m", 999) < SAFETY_WARNING_M)
        angles = [o.get("relative_angle_deg") for o in observations if o.get("relative_angle_deg") is not None]
        front = sum(1 for a in angles if -45 <= a <= 45)
        side = sum(1 for a in angles if 45 < abs(a) <= 135)
        rear = sum(1 for a in angles if abs(a) > 135)
        approach_speeds = []
        for i in range(1, len(observations)):
            dt = observations[i]["timestamp_utc"] - observations[i-1]["timestamp_utc"]
            if dt > 0.001:
                _aspd = (observations[i].get('distance_to_robot_edge_m', 0)
                         - observations[i-1].get('distance_to_robot_edge_m', 0)) / dt
                if abs(_aspd) <= MAX_PHYSICAL_SPEED_MPS:
                    approach_speeds.append(_aspd)
        mean_approach = float(np.mean(approach_speeds)) if approach_speeds else 0.0
        name_class, name_conf = _classify_by_name(name)
        if pos_variance < STATIC_VARIANCE_THRESHOLD and mean_speed < 0.05: motion_class, motion_conf = "static", 0.8
        elif pos_variance > MOVING_VARIANCE_THRESHOLD or mean_speed > 0.3: motion_class, motion_conf = "moving", 0.7
        else: motion_class, motion_conf = "unknown", 0.4
        evidence = {"human_marker": 0.0, "static_infrastructure": 0.0, "likely_moving": 0.0, "likely_static": 0.0}
        if name_class == "human_marker": evidence["human_marker"] += name_conf
        elif name_class == "static_infrastructure": evidence["static_infrastructure"] += name_conf
        if motion_class == "static": evidence["static_infrastructure"] += motion_conf * 0.5; evidence["likely_static"] += motion_conf
        elif motion_class == "moving": evidence["human_marker"] += motion_conf * 0.3; evidence["likely_moving"] += motion_conf
        if mean_height and 1.5 <= mean_height <= 2.0: evidence["human_marker"] += 0.3
        if mean_speed > 0.5 and direction_changes > 3: evidence["human_marker"] += 0.4
        elif mean_speed < 0.05: evidence["static_infrastructure"] += 0.3
        if stop_go_count >= 3: evidence["human_marker"] += 0.2
        final_class = max(evidence, key=evidence.get)
        final_conf = min(1.0, evidence[final_class])
        if final_conf < 0.3: final_class, final_conf = "unknown", 0.3
        distances = [o.get("horizontal_distance_m", 999) for o in observations]
        edge_distances = [o.get("distance_to_robot_edge_m", 999) for o in observations]
        object_features[name] = {
            "object_name": name, "num_observations": len(observations), "mean_position_m": mean_pos,
            "position_variance_m2": pos_variance, "mean_height_m": mean_height, "mean_speed_mps": mean_speed,
            "max_speed_mps": max_speed, "speed_std_mps": float(np.std(speeds)) if len(speeds) > 1 else 0.0,
            "mean_acceleration_mps2": float(np.mean(np.abs(accelerations))) if accelerations else 0.0,
            "max_acceleration_mps2": float(np.max(np.abs(accelerations))) if accelerations else 0.0,
            "mean_jerk": mean_jerk, "direction_changes": direction_changes, "stop_go_count": stop_go_count,
            "path_length_m": float(path_length), "displacement_m": float(np.linalg.norm(positions[-1] - positions[0])),
            "path_straightness": _safe_div(float(np.linalg.norm(positions[-1] - positions[0])), float(path_length)),
            "min_distance_to_robot_m": min(distances) if distances else None,
            "min_edge_distance_m": min(edge_distances) if edge_distances else None,
            "mean_approach_speed_mps": mean_approach, "max_approach_speed_mps": float(np.min(approach_speeds)) if approach_speeds else 0.0,
            "min_time_to_contact_s": None, "time_in_critical_s": time_critical, "time_in_warning_s": time_warning,
            "time_in_safe_s": 0.0, "front_encounters": front, "side_encounters": side, "rear_encounters": rear,
            "classification": final_class, "confidence": final_conf, "name_hint_class": name_class,
            "motion_class": motion_class, "height_class": None, "speed_pattern": None, "evidence_scores": evidence
        }
        if len(positions) >= TRAJECTORY_MIN_LENGTH:
            trajectories[name] = {"positions": positions.tolist(), "classification": final_class, "speed_profile": speeds[:100]}
        for obs in observations:
            edge_d = obs.get("distance_to_robot_edge_m", 999)
            zone = _safety_zone(edge_d)
            if zone in ("critical", "warning"):
                safety_events.append({"object_name": name, "timestamp_utc": obs["timestamp_utc"], "distance_m": edge_d, "horizontal_distance_m": obs.get("horizontal_distance_m", 999), "zone": zone, "robot_position_m": obs.get("robot_position_m", [0, 0]), "object_position_m": obs.get("position_mir_frame_m", [0, 0]), "classification": final_class, "robot_speed": obs.get("robot_speed_mps", 0), "approach_speed": obs.get("approach_speed_mps", 0), "encounter_direction": obs.get("encounter_direction", "unknown")})
    lidar_clusters = cluster_lidar_points(fused_objects)
    label_transfers = transfer_labels_to_clusters(object_features, lidar_clusters)
    anomalies = []
    for n, f in object_features.items():
        if f["name_hint_class"] == "static_infrastructure" and f["max_speed_mps"] > 0.5:
            anomalies.append({"type": "unexpected_motion", "object_name": n, "description": f"'{n}' labeled static but moved at {f['max_speed_mps']:.2f} m/s", "severity": "medium"})
        if f["mean_jerk"] > 5.0:
            anomalies.append({"type": "sudden_movement", "object_name": n, "description": f"'{n}' sudden movement (jerk={f['mean_jerk']:.1f})", "severity": "high"})
        if f["min_edge_distance_m"] is not None and f["min_edge_distance_m"] == 0.0:
            anomalies.append({"type": "collision_detected", "object_name": n, "description": f"'{n}' INSIDE robot footprint", "severity": "critical"})
    return {"object_features": object_features, "safety_events": safety_events, "lidar_clusters": lidar_clusters, "label_transfers": label_transfers, "trajectories": trajectories, "anomalies": anomalies}

def update_memory_from_session(memory, session_name, session_results):
    if session_name in memory.get("sessions_analyzed_list", []): return memory
    of = session_results["object_features"]
    for name, feat in of.items():
        if name not in memory["object_tracks"]:
            memory["object_tracks"][name] = {
                "first_seen_session": session_name, "last_seen_session": session_name, "sessions_count": 1,
                "sessions_list": [session_name], "total_observations": feat["num_observations"],
                "classification": feat["classification"], "confidence": feat["confidence"],
                "name_hint_class": feat["name_hint_class"], "mean_position_m": feat["mean_position_m"],
                "position_variance_m2": feat["position_variance_m2"], "mean_height_m": feat["mean_height_m"],
                "mean_speed_mps": feat["mean_speed_mps"], "max_speed_mps": feat["max_speed_mps"],
                "speed_std_mps": feat.get("speed_std_mps", 0), "mean_acceleration_mps2": feat.get("mean_acceleration_mps2", 0),
                "max_acceleration_mps2": feat.get("max_acceleration_mps2", 0), "mean_jerk": feat.get("mean_jerk", 0),
                "path_length_total_m": feat["path_length_m"], "min_distance_ever_m": feat["min_distance_to_robot_m"],
                "total_time_critical_s": feat["time_in_critical_s"], "total_time_warning_s": feat["time_in_warning_s"],
                "total_front_encounters": feat["front_encounters"], "total_side_encounters": feat["side_encounters"],
                "total_rear_encounters": feat["rear_encounters"], "stop_go_total": feat["stop_go_count"],
                "direction_changes_total": feat["direction_changes"], "speed_history": [feat["mean_speed_mps"]],
                "position_history": [feat["mean_position_m"]],
                "confidence_history": [{"session": session_name, "confidence": feat["confidence"], "classification": feat["classification"]}],
                "evidence_scores_history": [feat["evidence_scores"]]
            }
            memory["learned_insights"].append(f"[{session_name}] NEW: '{name}' class='{feat['classification']}' conf={feat['confidence']:.2f}")
        else:
            t = memory["object_tracks"][name]
            n_old, n_new = t["total_observations"], feat["num_observations"]
            n_total = n_old + n_new
            for k in ["position_variance_m2", "mean_speed_mps", "speed_std_mps", "mean_acceleration_mps2", "mean_jerk"]:
                t[k] = (t.get(k, 0) * n_old + feat.get(k, 0) * n_new) / n_total
            for k in ["max_speed_mps", "max_acceleration_mps2"]:
                t[k] = max(t.get(k, 0), feat.get(k, 0))
            t["total_observations"] = n_total; t["sessions_count"] += 1; t["sessions_list"].append(session_name)
            t["last_seen_session"] = session_name
            t["path_length_total_m"] = t.get("path_length_total_m", 0) + feat["path_length_m"]
            t["stop_go_total"] = t.get("stop_go_total", 0) + feat["stop_go_count"]
            t["direction_changes_total"] = t.get("direction_changes_total", 0) + feat["direction_changes"]
            new_min = feat.get("min_distance_to_robot_m")
            if new_min is not None and (t.get("min_distance_ever_m") is None or new_min < t["min_distance_ever_m"]): t["min_distance_ever_m"] = new_min
            if feat.get("mean_height_m") is not None: t["mean_height_m"] = feat["mean_height_m"]
            t["total_time_critical_s"] = t.get("total_time_critical_s", 0) + feat["time_in_critical_s"]
            t["total_time_warning_s"] = t.get("total_time_warning_s", 0) + feat["time_in_warning_s"]
            t["total_front_encounters"] = t.get("total_front_encounters", 0) + feat["front_encounters"]
            t["total_side_encounters"] = t.get("total_side_encounters", 0) + feat["side_encounters"]
            t["total_rear_encounters"] = t.get("total_rear_encounters", 0) + feat["rear_encounters"]
            t.setdefault("speed_history", []).append(feat["mean_speed_mps"])
            t.setdefault("position_history", []).append(feat["mean_position_m"])
            t.setdefault("confidence_history", []).append({"session": session_name, "confidence": t["confidence"], "classification": t["classification"]})
            t.setdefault("evidence_scores_history", []).append(feat["evidence_scores"])
            old_class = t["classification"]
            if t["position_variance_m2"] < STATIC_VARIANCE_THRESHOLD and t["mean_speed_mps"] < 0.05 and t["sessions_count"] >= 3:
                t["classification"], t["confidence"] = "confirmed_static", min(1.0, t["confidence"] + 0.05)
            elif t["name_hint_class"] == "human_marker" and t["mean_speed_mps"] > 0.1 and t["sessions_count"] >= 2:
                t["classification"], t["confidence"] = "confirmed_human", min(1.0, t["confidence"] + 0.05)
            if t["classification"] != old_class:
                memory["learned_insights"].append(f"[{session_name}] RECLASSIFIED '{name}': '{old_class}' -> '{t['classification']}'")
    for evt in session_results["safety_events"]:
        evt["session"] = session_name
    memory["safety_events"].extend(session_results["safety_events"])
    ss = memory["safety_statistics"]
    nc = sum(1 for e in session_results["safety_events"] if e["zone"] == "critical")
    nw = sum(1 for e in session_results["safety_events"] if e["zone"] == "warning")
    ss["total_critical"] += nc; ss["total_warning"] += nw
    if session_results["safety_events"]:
        worst = min(session_results["safety_events"], key=lambda e: e["distance_m"])
        if ss["worst_distance_ever_m"] is None or worst["distance_m"] < ss["worst_distance_ever_m"]:
            ss["worst_distance_ever_m"] = worst["distance_m"]; ss["worst_event"] = worst
    if nc > 0: memory["learned_insights"].append(f"[{session_name}] SAFETY: {nc} CRITICAL events")
    if nw > 0: memory["learned_insights"].append(f"[{session_name}] SAFETY: {nw} WARNING events")
    lc = session_results["lidar_clusters"]
    if lc:
        for c in lc:
            if c["label"]: memory["lidar_clusters"]["labeled_patterns"].append({"centroid": c["centroid_m"], "n_points": c["n_points"], "label": c["label"], "confidence": c["label_confidence"], "session": session_name})
        memory["lidar_clusters"]["label_transfer_log"].extend(session_results["label_transfers"])
        unlabeled = sum(1 for c in lc if not c["label"])
        if session_results["label_transfers"]: memory["learned_insights"].append(f"[{session_name}] LIDAR: {len(session_results['label_transfers'])} label transfers")
        if unlabeled: memory["learned_insights"].append(f"[{session_name}] LIDAR: {unlabeled} unlabeled clusters")
    for a in session_results["anomalies"]:
        a["session"] = session_name
        memory["anomalies"].append(a)
        memory["learned_insights"].append(f"[{session_name}] ANOMALY [{a['severity']}]: {a['description']}")
    for name, feat in of.items():
        pos = feat["mean_position_m"]
        gk = _grid_key(pos[0], pos[1])
        if "human" in feat["classification"]: memory["spatial_priors"]["human_presence_grid"][gk] = memory["spatial_priors"]["human_presence_grid"].get(gk, 0) + feat["num_observations"]
        elif "static" in feat["classification"]: memory["spatial_priors"]["static_object_grid"][gk] = memory["spatial_priors"]["static_object_grid"].get(gk, 0) + 1
    memory["total_sessions_analyzed"] += 1
    memory["sessions_analyzed_list"].append(session_name)
    return memory

def _height_str(t):
    h = t.get('mean_height_m')
    val = f"{h:.2f}m" if h else "N/A"
    return f"    Height   : {val}"


def generate_report_section(memory):
    lines = ["=" * 60, " KNOWLEDGE ENGINE - Cumulative Brain Report", f" Sessions: {memory['total_sessions_analyzed']}", f" Updated : {memory['last_updated_utc']}", "=" * 60, "\n--- OBJECT KNOWLEDGE ---"]
    if not memory["object_tracks"]: lines.append("  No objects learned yet.")
    else:
        for name, t in sorted(memory["object_tracks"].items(), key=lambda x: -x[1].get("confidence", 0)):
            pos = t.get("mean_position_m", [0, 0])
            lines.extend([f"\n  [{name}]", f"    Class    : {t.get('classification', '?')}", f"    Conf     : {t.get('confidence', 0):.2f}", f"    Sessions : {t.get('sessions_count', 0)}", f"    Obs      : {t.get('total_observations', 0)}", f"    Position : ({pos[0]:.2f}, {pos[1]:.2f}) m", f"    Speed    : {t.get('mean_speed_mps', 0):.3f} m/s", _height_str(t), f"    Min dist : {t.get('min_distance_ever_m', 'N/A')}", f"    Crit time: {t.get('total_time_critical_s', 0):.1f}s", f"    Encounters: F={t.get('total_front_encounters', 0)} S={t.get('total_side_encounters', 0)} R={t.get('total_rear_encounters', 0)}"])
    ss = memory.get("safety_statistics", {})
    w = ss.get('worst_distance_ever_m')
    lines.extend([f"\n--- SAFETY ---", f"  Critical total : {ss.get('total_critical', 0)}", f"  Warning total  : {ss.get('total_warning', 0)}", f"  Closest ever   : {f'{w*100:.1f}cm' if w is not None else 'N/A'}"])
    lc = memory.get("lidar_clusters", {})
    lines.extend([f"\n--- LIDAR LEARNING ---", f"  Labeled patterns : {len(lc.get('labeled_patterns', []))}", f"  Label transfers  : {len(lc.get('label_transfer_log', []))}"])
    sp = memory.get("spatial_priors", {})
    lines.extend([f"\n--- SPATIAL KNOWLEDGE ---", f"  Human zones  : {len(sp.get('human_presence_grid', {}))}", f"  Risk zones   : {len(sp.get('high_risk_grid', {}))}"])
    anomalies = memory.get("anomalies", [])
    lines.append(f"\n--- ANOMALIES ({len(anomalies)}) ---")
    for a in anomalies[-5:]: lines.append(f"  [{a.get('severity', '?')}] {a.get('description', '')}")
    insights = memory.get("learned_insights", [])
    lines.append(f"\n--- INSIGHTS (last 15 of {len(insights)}) ---")
    for ins in insights[-15:]: lines.append(f"  - {ins}")
    open_qs = [q for q in memory.get("unresolved_questions", []) if not q.get("answered")]
    lines.append(f"\n--- QUESTIONS ({len(open_qs)}) ---")
    for q in open_qs: lines.append(f"  ? {q['question']}")
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)

def _simulate_merge_preview(current_memory, session_name, session_results):
    mc = copy.deepcopy(current_memory)
    before = {"total_sessions": mc.get("total_sessions_analyzed", 0), "total_objects": len(mc.get("object_tracks", {})), "known_object_names": set(mc.get("object_tracks", {}).keys()), "total_safety_events": len(mc.get("safety_events", [])), "total_anomalies": len(mc.get("anomalies", [])), "total_insights": len(mc.get("learned_insights", [])), "total_critical": mc.get("safety_statistics", {}).get("total_critical", 0), "total_warning": mc.get("safety_statistics", {}).get("total_warning", 0)}
    pm = update_memory_from_session(mc, session_name, session_results)
    after = {"total_sessions": pm.get("total_sessions_analyzed", 0), "total_objects": len(pm.get("object_tracks", {})), "known_object_names": set(pm.get("object_tracks", {}).keys()), "total_safety_events": len(pm.get("safety_events", [])), "total_anomalies": len(pm.get("anomalies", [])), "total_insights": len(pm.get("learned_insights", [])), "total_critical": pm.get("safety_statistics", {}).get("total_critical", 0), "total_warning": pm.get("safety_statistics", {}).get("total_warning", 0)}
    new_obj = after["known_object_names"] - before["known_object_names"]
    return pm, {"before": before, "after": after, "delta": {"new_objects_count": len(new_obj), "new_objects_names": sorted(list(new_obj)), "new_safety_events": after["total_safety_events"] - before["total_safety_events"], "new_anomalies": after["total_anomalies"] - before["total_anomalies"], "new_insights": after["total_insights"] - before["total_insights"], "new_critical_events": after["total_critical"] - before["total_critical"], "new_warning_events": after["total_warning"] - before["total_warning"]}}

def _write_candidate_summary(txt_path, session_name, session_results, diff):
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== PENDING MERGE CANDIDATE: {session_name} ===\n")
        f.write(f"Objects: {len(session_results['object_features'])}, Safety: {len(session_results['safety_events'])}, Anomalies: {len(session_results['anomalies'])}\n")
        b, a, d = diff["before"], diff["after"], diff["delta"]
        f.write(f"Sessions: {b['total_sessions']} -> {a['total_sessions']}\n")
        f.write(f"Objects: {b['total_objects']} -> {a['total_objects']}\n")
        f.write(f"New objects: {d['new_objects_names']}\n")

def analyze_session_safe(root_path, session_path):
    session_name = os.path.basename(session_path)
    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path): return None
    with open(fused_path, "rb") as f: fused_data = pickle.load(f)
    print(f"[knowledge_engine SAFE] Analyzing: {session_name}")
    session_results = extract_session_features(fused_data)
    print(f"[knowledge_engine SAFE] {len(session_results['object_features'])} objects, {len(session_results['safety_events'])} safety events, {len(session_results['anomalies'])} anomalies")
    current_memory = load_deep_memory(root_path)
    preview_memory, diff = _simulate_merge_preview(current_memory, session_name, session_results)
    candidate = {"schema_version": "merge_candidate_v1", "created_at_utc": utc_now_iso(), "session_name": session_name, "session_path": session_path, "session_results": session_results, "diff": diff, "already_in_memory": session_name in current_memory.get("sessions_analyzed_list", [])}
    safe_pickle_dump(candidate, os.path.join(session_path, PENDING_CANDIDATE_FILENAME))
    _write_candidate_summary(os.path.join(session_path, PENDING_CANDIDATE_SUMMARY), session_name, session_results, diff)
    report = generate_report_section(current_memory)
    report += "\n\nSAFE MODE: Merge candidate pending review. See pending_merge_candidate_summary.txt\n"
    with open(os.path.join(session_path, "knowledge_engine_report.txt"), "w", encoding="utf-8") as f: f.write(report)
    print(f"[knowledge_engine SAFE] Candidate saved. Deep memory NOT modified.")
    return report

def analyze_session(root_path, session_path):
    return analyze_session_safe(root_path, session_path)

def load_pending_candidate(session_path):
    p = os.path.join(session_path, PENDING_CANDIDATE_FILENAME)
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return pickle.load(f)

def clear_pending_candidate(session_path):
    for fn in [PENDING_CANDIDATE_FILENAME, PENDING_CANDIDATE_SUMMARY]:
        p = os.path.join(session_path, fn)
        if os.path.exists(p): os.remove(p)

def rebuild_all_sessions(root_path):
    sessions_dir = os.path.join(root_path, "sessions")
    paths = sorted(glob.glob(os.path.join(sessions_dir, "session_*")))
    if not paths: print("[knowledge_engine] No sessions."); return
    memory = _empty_deep_memory()
    save_deep_memory(root_path, memory)
    for sp in paths:
        sn = os.path.basename(sp)
        fp = os.path.join(sp, "fused_data.pkl")
        if not os.path.exists(fp): continue
        with open(fp, "rb") as f: fd = pickle.load(f)
        sr = extract_session_features(fd)
        memory = update_memory_from_session(memory, sn, sr)
        print(f"  Done {sn}: {len(sr['object_features'])} objects")
    save_deep_memory(root_path, memory)
    print(f"[knowledge_engine] Rebuild complete. {memory['total_sessions_analyzed']} sessions.")

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python knowledge_engine.py [--safe] <session_path> [root_path]"); sys.exit(1)
    if sys.argv[1] == "--safe":
        sp, rp = sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = analyze_session_safe(rp, sp)
    elif sys.argv[1] == "--rebuild":
        rp = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rebuild_all_sessions(rp)
    else:
        sp, rp = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = analyze_session(rp, sp)
    if 'r' in dir() and r: print(r)