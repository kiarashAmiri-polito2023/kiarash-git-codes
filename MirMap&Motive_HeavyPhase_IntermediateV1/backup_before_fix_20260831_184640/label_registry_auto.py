#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/label_registry_auto.py - Auto-Activation Module
"""

import os
import sys
import json
import pickle

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from label_registry import (LabelRegistry, CLASS_HUMAN, CLASS_STATIC,
                             CLASS_DYNAMIC, CLASS_UNKNOWN,
                             SOURCE_MOTIVE, SOURCE_SLAM)


def load_taxonomy(root_path):
    tax_path = os.path.join(root_path, "persistent_knowledge", "taxonomy.json")
    if not os.path.exists(tax_path):
        return None
    with open(tax_path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_by_taxonomy(name, taxonomy):
    if taxonomy is None:
        return CLASS_UNKNOWN
    name_lower = name.lower()
    for class_name, class_info in taxonomy.get("classes", {}).items():
        for kw in class_info.get("motive_keywords", []):
            if kw in name_lower:
                return class_name
    return CLASS_UNKNOWN


def run_auto_registry(root_path, session_path, auto_yes=False):
    print("\n" + "=" * 60)
    print(" LABEL REGISTRY - AUTO CHECK")
    print("=" * 60)

    registry = LabelRegistry(root_path)
    existing_names = set()
    for entry in registry.labels.values():
        existing_names.add(entry["canonical_name"].lower())

    fused_path = os.path.join(session_path, "fused_data.pkl")
    if not os.path.exists(fused_path):
        print("  No fused_data.pkl. Skipping.")
        return {"activated": False, "new_labels": 0}

    with open(fused_path, "rb") as f:
        fused = pickle.load(f)

    motive_names = set()
    for obs in fused.get("fused_objects", []):
        if obs.get("source") == "motive":
            name = obs.get("object_name", "")
            if name:
                motive_names.add(name)

    new_names = [n for n in motive_names if n.lower() not in existing_names]

    if not new_names:
        print("  All objects already in registry.")
        print("=" * 60 + "\n")
        return {"activated": False, "new_labels": 0}

    print("  New objects found: " + str(len(new_names)))
    for n in new_names:
        print("    - " + n)

    if not auto_yes:
        ans = input("\n  Import to registry? (yes/no) [yes]: ").strip().lower()
        if ans and not ans.startswith("y"):
            print("  Skipped.")
            return {"activated": False, "new_labels": 0}

    taxonomy = load_taxonomy(root_path)
    positions = {}
    for obs in fused.get("fused_objects", []):
        if obs.get("source") != "motive":
            continue
        name = obs.get("object_name", "")
        pos = obs.get("position_mir_frame_m")
        if name and pos:
            positions.setdefault(name, []).append(pos)

    session_name = os.path.basename(session_path)
    created = 0
    for name in new_names:
        obj_class = classify_by_taxonomy(name, taxonomy)
        mean_pos = None
        if name in positions and positions[name]:
            xs = [p[0] for p in positions[name]]
            ys = [p[1] for p in positions[name]]
            mean_pos = [sum(xs) / len(xs), sum(ys) / len(ys)]
        try:
            label_id = registry.add_label(
                canonical_name=name, object_class=obj_class,
                source=SOURCE_MOTIVE, motive_body_name=name,
                mean_position_m=mean_pos, session_name=session_name,
                is_confirmed=False)
            created += 1
            print("    + " + name + " -> " + obj_class + " (" + label_id + ")")
        except ValueError as e:
            print("    ! " + name + ": " + str(e))

    registry.save()
    print("\n  Done. " + str(created) + " new labels.")
    print("=" * 60 + "\n")
    return {"activated": True, "new_labels": created}


def main():
    if len(sys.argv) < 3:
        print("Usage: python label_registry_auto.py <root_path> <session_path>")
        sys.exit(1)
    run_auto_registry(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
