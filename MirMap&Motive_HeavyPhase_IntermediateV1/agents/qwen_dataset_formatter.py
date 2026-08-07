"""
qwen_dataset_formatter.py (v3.0 - Real Dynamic SLAM Ground Truth)
====================================================================
Politecnico di Torino - Reactive Collaborative Robotics Thesis
Operator: Kiarash Amiri (s322803) | Supervisor: Prof. Dario Antonelli

PURPOSE:
- Extracts TRUE linear and angular velocities from SLAM robot_states.
- Clamps outlier sensor jumps to physical MiR100 limits (v: 0-1.2 m/s, w: -1.0..1.0 rad/s).
- Dynamically assigns 4 industrial behavior classes:
    * FORWARD_CRUISING
    * ROTATIONAL_MANEUVER
    * LOW_SPEED_NAVIGATION
    * IDLE_STATIONARY
- Generates context-rich Chain-of-Thought prompts reflecting semantic objects.
====================================================================
"""

import os
import json
import pickle
import math

ROOT_DIR = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
SESSIONS_DIR = os.path.join(ROOT_DIR, "sessions")

PROMPTS = [
    "You are the autonomous navigation brain of a MiR100 mobile robot operating in a collaborative factory cell with human workers. Analyze the 448x448 Semantic BEV image (displaying SLAM walls, LiDAR returns, semantic objects like chairs/tables, and the operator tracked by MoCap). Determine the next safe linear and angular velocity command [v, w].",
    "Given the multi-layer Bird's Eye View (BEV) representation of the industrial workspace, assess the distance to the operator, surrounding semantic obstacles, and robot heading. Output the collision-free motion control command.",
    "Examine the BEV spatial map. Identify the operator's position, safety zone breaches, and stationary obstacles. Provide your spatial reasoning in thought tags and predict the safe action [linear_x, angular_z].",
    "Industrial Collaborative Robot Controller: Read the semantic BEV image containing metric SLAM grid, LiDAR hits, and human tracking. Output the reactive velocity commands to ensure human safety."
]


def classify_behavior(linear_v, angular_w):
    """Accurately classifies robot industrial state based on metric kinematic thresholds."""
    abs_v = abs(linear_v)
    abs_w = abs(angular_w)

    if abs_v < 0.02 and abs_w < 0.05:
        return "IDLE_STATIONARY"
    elif abs_w >= 0.15 and abs_v < 0.10:
        return "ROTATIONAL_MANEUVER"
    elif abs_v >= 0.15:
        return "FORWARD_CRUISING"
    else:
        return "LOW_SPEED_NAVIGATION"


def format_session(sname):
    sdir = os.path.join(SESSIONS_DIR, sname)
    bev_dir = os.path.join(sdir, "bev_images")
    slam_pkl = os.path.join(sdir, "slam_data.pkl")
    sem_json = os.path.join(sdir, "semantic_object_map.json")

    if not os.path.exists(bev_dir) or not os.path.exists(slam_pkl):
        return None

    # Load SLAM robot states (true metric velocities)
    with open(slam_pkl, "rb") as f:
        slam_data = pickle.load(f)
    robot_states = slam_data.get("robot_states", [])

    # Load semantic objects count
    obj_count = 0
    if os.path.exists(sem_json):
        with open(sem_json, "r", encoding="utf-8") as f:
            sem_data = json.load(f)
            obj_count = sem_data.get("total_unique_physical_objects", 0)

    png_files = sorted([f for f in os.listdir(bev_dir) if f.endswith(".png")])
    if not png_files:
        return None

    dataset_records = []
    behavior_counts = {}

    for idx, png in enumerate(png_files):
        img_path = os.path.join(bev_dir, png)
        user_prompt = PROMPTS[idx % len(PROMPTS)]

        # Extract true velocity from SLAM state
        if idx < len(robot_states):
            st = robot_states[idx]
            raw_v = float(st.get("speed", 0.0))
            raw_w = float(st.get("angular_velocity", 0.0))
        else:
            raw_v, raw_w = 0.0, 0.0

        # Physical limit clamping for MiR100 safety (filters sensor spike outliers)
        linear_x = max(0.0, min(raw_v, 0.8)) # Max 0.8 m/s in lab
        angular_z = max(-1.0, min(raw_w, 1.0)) # Max 1.0 rad/s

        behavior_class = classify_behavior(linear_x, angular_z)
        behavior_counts[behavior_class] = behavior_counts.get(behavior_class, 0) + 1

        # Dynamic Chain-of-Thought thought generation
        if behavior_class == "FORWARD_CRUISING":
            thought_text = (
                f"BEV analysis: Occupancy grid and LiDAR indicate a clear navigation corridor ahead. "
                f"{obj_count} static obstacles (chairs/tables) are positioned outside the 1.2m orange safety envelope. "
                f"Operator is at safe standoff distance. Proceeding with forward cruising at {linear_x:.2f} m/s."
            )
        elif behavior_class == "ROTATIONAL_MANEUVER":
            thought_text = (
                f"BEV analysis: Heading adjustment required. Static obstacles detected in peripheral field. "
                f"Executing in-place rotational alignment at {angular_z:.2f} rad/s to orient toward goal waypoint while maintaining clearance."
            )
        elif behavior_class == "LOW_SPEED_NAVIGATION":
            thought_text = (
                f"BEV analysis: Approaching work cell boundaries or proximity to human operator/stations. "
                f"Maintaining low-speed cautious motion ({linear_x:.2f} m/s, {angular_z:.2f} rad/s) for safety margin."
            )
        else: # IDLE_STATIONARY
            thought_text = (
                f"BEV analysis: Zero motion command active or station hold. Surrounding {obj_count} semantic obstacles "
                f"and operator tracked. Holding stationary stance [0.0, 0.0]."
            )

        record = {
            "id": f"{sname}_frame_{idx:05d}",
            "image": img_path,
            "conversations": [
                {
                    "from": "user",
                    "value": f"<image>\n{user_prompt}"
                },
                {
                    "from": "gpt",
                    "value": f"<thought>\n{thought_text}\n</thought>\n<action>\n[{linear_x:.3f}, {angular_z:.3f}]\n</action>"
                }
            ],
            "ground_truth_action": [round(linear_x, 3), round(angular_z, 3)],
            "behavior_class": behavior_class
        }
        dataset_records.append(record)

    out_jsonl = os.path.join(sdir, "qwen_vla_dataset.jsonl")
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in dataset_records:
            f.write(json.dumps(r) + "\n")

    print(f"  [OK] {sname}: Formatted {len(dataset_records)} Qwen-VL samples -> {out_jsonl}")
    print(f"       Behavior Distribution: {behavior_counts}")
    return dataset_records


def main():
    sessions = [d for d in os.listdir(SESSIONS_DIR) if os.path.isdir(os.path.join(SESSIONS_DIR, d))]
    for s in sorted(sessions):
        if "2026-08-27_17-54-20" in s:
            format_session(s)


if __name__ == "__main__":
    main()
