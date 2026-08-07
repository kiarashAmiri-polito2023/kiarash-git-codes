#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_motive_pipeline.py — Diagnostic tool
Answers: does launch_session.py save CSV from MotiveConnector? 
What's the real structure of 'motive sessions' folder?
"""

import re
from pathlib import Path

MOTIVE_SESSIONS_PATH = (
    r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
    r"\motive sessions"
)


def find_launch_session_file():
    return list(Path(".").rglob("launch_session.py"))


def inspect_launch_session():
    print("=" * 70)
    print(" PART 1: Inspecting launch_session.py")
    print("=" * 70)
    candidates = find_launch_session_file()
    if not candidates:
        print("[WARN] launch_session.py not found. Run this from project root.")
        return
    path = candidates[0]
    print(f"Found: {path}\n")
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] could not read file: {e}")
        return

    patterns = {
        "MotiveConnector usage": r"MotiveConnector",
        "get_full_state calls": r"get_full_state\(",
        "get_all_full_states calls": r"get_all_full_states\(",
        "CSV writing (csv module)": r"import csv|csv\.writer|csv\.DictWriter",
        "start_recording calls": r"start_recording\(",
        "stop_recording calls": r"stop_recording\(",
        "'motive sessions' path references": r"motive sessions|motive_sessions",
        "get_latest_frame calls": r"get_latest_frame\(",
    }

    for label, pattern in patterns.items():
        count = len(re.findall(pattern, content))
        status = "FOUND    " if count > 0 else "NOT_FOUND"
        print(f"  [{status}] {label:40s} (occurrences: {count})")

    print("\n--- Context around CSV writing (if any) ---")
    for m in re.finditer(r"csv\.(writer|DictWriter)", content):
        start, end = max(0, m.start() - 300), min(len(content), m.end() + 500)
        print(content[start:end])
        print("-" * 40)

    print("\n--- Context around start_recording() call ---")
    for m in re.finditer(r"start_recording\(", content):
        start, end = max(0, m.start() - 300), min(len(content), m.end() + 300)
        print(content[start:end])
        print("-" * 40)


def inspect_motive_sessions_folder():
    print("\n" + "=" * 70)
    print(" PART 2: Inspecting 'motive sessions' folder structure")
    print("=" * 70)
    root = Path(MOTIVE_SESSIONS_PATH)
    if not root.exists():
        print(f"[ERROR] Path does not exist: {root}")
        return

    print(f"Root: {root}\n")
    subfolders = sorted([p for p in root.iterdir() if p.is_dir()])
    files_at_root = sorted([p for p in root.iterdir() if p.is_file()])

    print(f"Subfolders directly inside: {len(subfolders)}")
    print(f"Files directly inside root: {len(files_at_root)}")

    if files_at_root:
        print("\nFiles at root level (first 20):")
        for f in files_at_root[:20]:
            print(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

    if subfolders:
        print(f"\nInspecting up to 4 subfolders in detail:\n")
        for sub in subfolders[:4]:
            print(f"[FOLDER] {sub.name}")
            items = sorted(sub.rglob("*"))
            avi_files = [i for i in items if i.suffix.lower() == ".avi"]
            csv_files = [i for i in items if i.suffix.lower() == ".csv"]
            other = [i for i in items if i.is_file()
                     and i.suffix.lower() not in (".avi", ".csv")]

            print(f"   AVI files: {len(avi_files)}")
            for a in avi_files:
                print(f"     - {a.name}  ({a.stat().st_size / (1024*1024):.1f} MB)")

            print(f"   CSV files: {len(csv_files)}")
            for c in csv_files:
                print(f"     - {c.name}  ({c.stat().st_size / 1024:.1f} KB)")
                try:
                    with open(c, "r", encoding="utf-8-sig", errors="ignore") as f:
                        lines = [next(f) for _ in range(5)]
                    print("       First 5 lines:")
                    for line in lines:
                        print(f"         {line.rstrip()}")
                except StopIteration:
                    pass
                except Exception as e:
                    print(f"       [error reading] {e}")

            if other:
                print(f"   Other files ({len(other)}):")
                for o in other[:10]:
                    print(f"     - {o.name}")
            print()

    all_avi = list(root.rglob("*.avi"))
    all_csv = list(root.rglob("*.csv"))
    print(f"\nTOTAL across all subfolders: {len(all_avi)} AVI, {len(all_csv)} CSV")


def main():
    inspect_launch_session()
    inspect_motive_sessions_folder()
    print("\n" + "=" * 70)
    print(" DONE — copy this ENTIRE output back.")
    print("=" * 70)


if __name__ == "__main__":
    main()