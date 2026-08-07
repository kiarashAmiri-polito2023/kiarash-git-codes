#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/label_registry.py - Persistent Label Registry (v1)
"""

import os
import sys
import pickle
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

REGISTRY_FILENAME = "label_registry.pkl"
REGISTRY_SUMMARY_FILENAME = "label_registry_summary.txt"
PERSISTENT_DIR = "persistent_knowledge"
SCHEMA_VERSION = "label_registry_v1"

CLASS_HUMAN = "human"
CLASS_STATIC = "static_infrastructure"
CLASS_DYNAMIC = "dynamic_obstacle"
CLASS_ROBOT = "robot"
CLASS_UNKNOWN = "unknown"

VALID_CLASSES = {CLASS_HUMAN, CLASS_STATIC, CLASS_DYNAMIC, CLASS_ROBOT, CLASS_UNKNOWN}

SOURCE_MOTIVE = "motive"
SOURCE_SLAM = "slam"
SOURCE_MANUAL = "manual"
SOURCE_CROSS_REF = "cross_reference"

VALID_SOURCES = {SOURCE_MOTIVE, SOURCE_SLAM, SOURCE_MANUAL, SOURCE_CROSS_REF}


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def generate_label_id():
    raw = uuid.uuid4().hex[:12]
    return "LBL-" + raw.upper()


def safe_pickle_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def create_label_entry(canonical_name, object_class=CLASS_UNKNOWN,
                       source=SOURCE_MANUAL, motive_body_name=None,
                       slam_cluster_id=None, mean_position_m=None,
                       is_confirmed=False):
    if object_class not in VALID_CLASSES:
        raise ValueError("object_class must be one of " + str(VALID_CLASSES))
    if source not in VALID_SOURCES:
        raise ValueError("source must be one of " + str(VALID_SOURCES))

    now = utc_now_iso()
    entry = {
        "label_id": generate_label_id(),
        "canonical_name": canonical_name,
        "aliases": [],
        "object_class": object_class,
        "is_static": (object_class == CLASS_STATIC),
        "is_dynamic": (object_class in (CLASS_HUMAN, CLASS_DYNAMIC)),
        "mean_position_m": mean_position_m,
        "position_tolerance_m": 0.5,
        "motive_rigid_bodies": [],
        "slam_obstacle_ids": [],
        "source_modalities": [source],
        "first_seen_session": None,
        "last_seen_session": None,
        "total_observations": 0,
        "confirmed_matches": [],
        "rejected_matches": [],
        "conflict_history": [],
        "is_confirmed": is_confirmed,
        "confidence": 0.5 if not is_confirmed else 0.9,
        "created_at_utc": now,
        "last_updated_utc": now,
        "notes": "",
    }
    if motive_body_name:
        entry["motive_rigid_bodies"].append(motive_body_name)
        if SOURCE_MOTIVE not in entry["source_modalities"]:
            entry["source_modalities"].append(SOURCE_MOTIVE)
    if slam_cluster_id:
        entry["slam_obstacle_ids"].append(slam_cluster_id)
        if SOURCE_SLAM not in entry["source_modalities"]:
            entry["source_modalities"].append(SOURCE_SLAM)
    return entry


class LabelRegistry:

    def __init__(self, root_path):
        self.root_path = root_path
        self.persistent_dir = os.path.join(root_path, PERSISTENT_DIR)
        self.registry_path = os.path.join(self.persistent_dir, REGISTRY_FILENAME)
        self.summary_path = os.path.join(self.persistent_dir, REGISTRY_SUMMARY_FILENAME)
        os.makedirs(self.persistent_dir, exist_ok=True)
        self.labels = {}
        self.metadata = {
            "schema_version": SCHEMA_VERSION,
            "created_at_utc": utc_now_iso(),
            "last_updated_utc": utc_now_iso(),
            "total_labels": 0,
        }
        self._load()

    def _load(self):
        if not os.path.exists(self.registry_path):
            return
        try:
            with open(self.registry_path, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict) and "labels" in data:
                self.labels = data["labels"]
                self.metadata = data["metadata"]
        except Exception as e:
            print("[LabelRegistry] WARNING: " + str(e))

    def save(self):
        self.metadata["last_updated_utc"] = utc_now_iso()
        self.metadata["total_labels"] = len(self.labels)
        data = {"labels": self.labels, "metadata": self.metadata}
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "rb") as src:
                    with open(self.registry_path + ".backup", "wb") as dst:
                        dst.write(src.read())
            except Exception:
                pass
        safe_pickle_dump(data, self.registry_path)
        self._write_summary()
        return self.registry_path

    def _write_summary(self):
        lines = [
            "=" * 60,
            " LABEL REGISTRY SUMMARY",
            " Schema : " + self.metadata["schema_version"],
            " Updated: " + self.metadata["last_updated_utc"],
            " Total  : " + str(len(self.labels)) + " labels",
            "=" * 60, "",
        ]
        for label_id, entry in sorted(self.labels.items(),
                                       key=lambda x: x[1].get("canonical_name", "")):
            conf_str = "CONFIRMED" if entry["is_confirmed"] else "pending"
            lines.append("  [" + conf_str + "] " + entry["canonical_name"] +
                         "  (" + entry["object_class"] + ")")
            lines.append("    ID       : " + label_id)
            lines.append("    Position : " + str(entry.get("mean_position_m")))
            lines.append("    Motive   : " + str(entry.get("motive_rigid_bodies", [])))
            lines.append("    SLAM     : " + str(entry.get("slam_obstacle_ids", [])))
            lines.append("    Sources  : " + str(entry.get("source_modalities", [])))
            lines.append("    Obs      : " + str(entry.get("total_observations", 0)))
            lines.append("")
        with open(self.summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def add_label(self, canonical_name, object_class=CLASS_UNKNOWN,
                  source=SOURCE_MANUAL, motive_body_name=None,
                  slam_cluster_id=None, mean_position_m=None,
                  session_name=None, is_confirmed=False):
        for existing_id, existing in self.labels.items():
            if existing["canonical_name"].lower() == canonical_name.lower():
                raise ValueError("Label '" + canonical_name + "' exists as " + existing_id)
        entry = create_label_entry(canonical_name, object_class, source,
                                    motive_body_name, slam_cluster_id,
                                    mean_position_m, is_confirmed)
        if session_name:
            entry["first_seen_session"] = session_name
            entry["last_seen_session"] = session_name
        label_id = entry["label_id"]
        self.labels[label_id] = entry
        return label_id

    def get_label_by_name(self, canonical_name):
        target = canonical_name.lower()
        for label_id, entry in self.labels.items():
            if entry["canonical_name"].lower() == target:
                return label_id, entry
            for alias in entry.get("aliases", []):
                if alias.lower() == target:
                    return label_id, entry
        return None

    def get_label_by_motive_name(self, motive_body_name):
        target = motive_body_name.lower()
        for label_id, entry in self.labels.items():
            for mb in entry.get("motive_rigid_bodies", []):
                if mb.lower() == target:
                    return label_id, entry
        return None

    def update_label(self, label_id, session_name=None, new_observations=0,
                     new_position_m=None, motive_body_name=None, slam_cluster_id=None):
        if label_id not in self.labels:
            return False
        entry = self.labels[label_id]
        entry["last_updated_utc"] = utc_now_iso()
        if session_name:
            if entry["first_seen_session"] is None:
                entry["first_seen_session"] = session_name
            entry["last_seen_session"] = session_name
        entry["total_observations"] += new_observations
        if new_position_m is not None and len(new_position_m) >= 2:
            old_pos = entry.get("mean_position_m")
            if old_pos is None:
                entry["mean_position_m"] = list(new_position_m[:2])
            else:
                n = max(entry["total_observations"], 1)
                entry["mean_position_m"] = [
                    (old_pos[0] * (n - 1) + new_position_m[0]) / n,
                    (old_pos[1] * (n - 1) + new_position_m[1]) / n,
                ]
        if motive_body_name and motive_body_name not in entry["motive_rigid_bodies"]:
            entry["motive_rigid_bodies"].append(motive_body_name)
            if SOURCE_MOTIVE not in entry["source_modalities"]:
                entry["source_modalities"].append(SOURCE_MOTIVE)
        if slam_cluster_id and slam_cluster_id not in entry["slam_obstacle_ids"]:
            entry["slam_obstacle_ids"].append(slam_cluster_id)
            if SOURCE_SLAM not in entry["source_modalities"]:
                entry["source_modalities"].append(SOURCE_SLAM)
        return True

    def confirm_label(self, label_id):
        if label_id not in self.labels:
            return False
        self.labels[label_id]["is_confirmed"] = True
        self.labels[label_id]["confidence"] = max(self.labels[label_id]["confidence"], 0.9)
        return True

    def suggest_matches(self, source, source_id, position_m,
                        object_class=CLASS_UNKNOWN, max_distance_m=1.0):
        import math
        suggestions = []
        for label_id, entry in self.labels.items():
            if source == SOURCE_MOTIVE and source_id in entry.get("motive_rigid_bodies", []):
                continue
            if source == SOURCE_SLAM and source_id in entry.get("slam_obstacle_ids", []):
                continue
            entry_pos = entry.get("mean_position_m")
            if entry_pos is None or len(entry_pos) < 2:
                continue
            dist = math.hypot(position_m[0] - entry_pos[0], position_m[1] - entry_pos[1])
            if dist > max_distance_m:
                continue
            confidence = 0.0
            confidence += max(0.0, 1.0 - dist / max_distance_m) * 0.4
            if object_class != CLASS_UNKNOWN and entry["object_class"] == object_class:
                confidence += 0.3
            if entry["is_static"] and dist < 0.3:
                confidence += 0.2
            if entry["is_confirmed"]:
                confidence += 0.1
            confidence = min(1.0, confidence)
            suggestions.append({
                "label_id": label_id,
                "canonical_name": entry["canonical_name"],
                "object_class": entry["object_class"],
                "distance_m": round(dist, 3),
                "confidence": round(confidence, 3),
                "is_confirmed": entry["is_confirmed"],
            })
        suggestions.sort(key=lambda s: s["confidence"], reverse=True)
        return suggestions

    def list_all_labels(self):
        return [{
            "label_id": lid,
            "canonical_name": e["canonical_name"],
            "object_class": e["object_class"],
            "is_confirmed": e["is_confirmed"],
            "sources": e["source_modalities"],
            "observations": e["total_observations"],
        } for lid, e in self.labels.items()]


def main():
    if len(sys.argv) < 2:
        print("Usage: python label_registry.py <root_path> [command]")
        sys.exit(1)
    root_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "status"
    registry = LabelRegistry(root_path)
    if command == "status":
        labels = registry.list_all_labels()
        print("Total labels: " + str(len(labels)))
        for l in labels:
            status = "OK" if l["is_confirmed"] else "??"
            print("  [" + status + "] " + l["canonical_name"] + "  (" + l["object_class"] + ")")


if __name__ == "__main__":
    main()
