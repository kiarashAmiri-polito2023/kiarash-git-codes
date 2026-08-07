#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_merge.py — Human-Approved Merge Executor

Per Master Doc section 15.2:
  The user (with optional AI advice) makes the final decision
  whether a session's merge candidate should be permanently
  merged into deep_learning_memory.pkl.

Key rules (all confirmed in Master Doc):
  - DEFAULT = NO MERGE. Empty input, Enter, or anything except
    the exact word "yes" (case-insensitive) means: do NOT merge.
  - Always creates a timestamped backup of deep_memory BEFORE
    merging (for rollback).
  - Refuses to double-merge a session that's already in memory
    (unless user restores an older backup first).
  - Removes the candidate files after successful merge so they
    can't accidentally be re-applied.
  - Logs every merge action to merge_history.log for traceability.

Usage:
    python agents/apply_merge.py <session_path>

Optional flags:
    --root <path>    Project root path (default: parent of agents/)
    --force-yes      Skip the interactive prompt (STILL creates a
                     backup first). Use with extreme caution — this
                     bypasses the human-in-the-loop safety rule.
    --show-only      Just display the preview, do nothing else.
    --list-backups   Show all available backups and exit.
"""

import os
import sys
import shutil
import argparse
from datetime import datetime, timezone


# ============================================================
# Path resolution — makes sibling imports work regardless of
# where the script is called from
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(SCRIPT_DIR)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


# ============================================================
# Timestamp helpers
# ============================================================
def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def timestamp_tag():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ============================================================
# Deep memory path helpers
# ============================================================
def deep_memory_path(root_path):
    return os.path.join(
        root_path, "persistent_knowledge",
        "deep_learning_memory.pkl")


def deep_memory_summary_path(root_path):
    return os.path.join(
        root_path, "persistent_knowledge",
        "deep_learning_memory_summary.txt")


def backup_dir(root_path):
    return os.path.join(
        root_path, "persistent_knowledge", "backups")


# ============================================================
# Backup management
# ============================================================
def create_backup(root_path):
    """
    Creates a timestamped backup of the current deep_memory
    (pkl + summary) before any merge. Returns the backup folder
    path, or None if there's nothing to back up yet (first merge).
    """
    dm_path = deep_memory_path(root_path)
    if not os.path.exists(dm_path):
        print("[apply_merge] No existing deep_memory to backup "
              "(first merge ever). Skipping backup.")
        return None

    bdir = backup_dir(root_path)
    os.makedirs(bdir, exist_ok=True)

    tag = timestamp_tag()
    backup_subdir = os.path.join(bdir, f"backup_{tag}")
    os.makedirs(backup_subdir, exist_ok=True)

    shutil.copy2(dm_path, os.path.join(
        backup_subdir, "deep_learning_memory.pkl"))

    sm_path = deep_memory_summary_path(root_path)
    if os.path.exists(sm_path):
        shutil.copy2(sm_path, os.path.join(
            backup_subdir,
            "deep_learning_memory_summary.txt"))

    with open(os.path.join(backup_subdir, "backup_info.txt"),
              "w", encoding="utf-8") as f:
        f.write(f"Backup created at (UTC): {utc_now_iso()}\n")
        f.write(f"Source: {dm_path}\n")

    print(f"[apply_merge] Backup created: {backup_subdir}")
    return backup_subdir


def list_all_backups(root_path):
    """Lists all backups in reverse chronological order."""
    bdir = backup_dir(root_path)
    if not os.path.isdir(bdir):
        print("[apply_merge] No backups directory exists yet.")
        return

    entries = sorted(
        [d for d in os.listdir(bdir)
         if d.startswith("backup_") and
         os.path.isdir(os.path.join(bdir, d))],
        reverse=True,
    )

    if not entries:
        print("[apply_merge] No backups found.")
        return

    print(f"[apply_merge] Backups found in {bdir}:")
    for e in entries:
        full = os.path.join(bdir, e)
        info_file = os.path.join(full, "backup_info.txt")
        info_line = ""
        if os.path.exists(info_file):
            try:
                with open(info_file, "r",
                          encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    info_line = f"  ({first_line})"
            except Exception:
                pass
        print(f"  - {e}{info_line}")


# ============================================================
# Preview display
# ============================================================
def print_preview_summary(session_path):
    """
    Prints the pending_merge_candidate_summary.txt so the user
    can review before confirming.
    """
    summary_path = os.path.join(
        session_path, "pending_merge_candidate_summary.txt")
    if not os.path.exists(summary_path):
        print("[apply_merge] No candidate summary file found "
              "in this session.")
        return False

    print()
    print("#" * 70)
    with open(summary_path, "r", encoding="utf-8") as f:
        print(f.read())
    print("#" * 70)
    print()
    return True


# ============================================================
# Main merge execution
# ============================================================
def apply_merge(session_path, root_path, force_yes=False,
                show_only=False):
    """
    Full merge workflow with all safety guards.

    Returns:
        0 = success (either merged or user said no)
        1 = error (no candidate found, path issues, etc.)
        2 = refused (already merged, needs rollback first)
    """
    # Import here so any import errors surface with a helpful
    # message rather than at module-load time
    try:
        from knowledge_engine import (
            load_deep_memory,
            save_deep_memory,
            update_memory_from_session,
            load_pending_candidate,
            clear_pending_candidate,
        )
    except ImportError as e:
        print(f"[apply_merge] ERROR: cannot import "
              f"knowledge_engine: {e}")
        print(f"  Make sure knowledge_engine.py is in the same "
              f"folder as apply_merge.py ({SCRIPT_DIR}).")
        return 1

    session_name = os.path.basename(
        session_path.rstrip("/\\"))

    # Load candidate
    candidate = load_pending_candidate(session_path)
    if candidate is None:
        print(f"[apply_merge] ERROR: no pending candidate found "
              f"in:")
        print(f"  {session_path}")
        print("  Did you run knowledge_engine in --safe mode "
              "first?")
        print("  Example:")
        print(f"    python agents/knowledge_engine.py --safe "
              f"\"{session_path}\"")
        return 1

    print(f"[apply_merge] Session       : {session_name}")
    print(f"[apply_merge] Candidate age : "
          f"{candidate.get('created_at_utc', 'unknown')}")
    print(f"[apply_merge] Root path     : {root_path}")

    # Early warning: session already merged?
    if candidate.get("already_in_memory", False):
        print()
        print("[apply_merge] WARNING: this session already "
              "exists in deep_memory.")
        print("[apply_merge] Merging again would create "
              "duplicate data. Refusing.")
        print("[apply_merge] If you really need to re-apply, "
              "first restore an older backup:")
        print(f"    python agents/apply_merge.py --list-backups "
              f"--root \"{root_path}\"")
        return 2

    # Show preview
    print_preview_summary(session_path)

    if show_only:
        print("[apply_merge] --show-only mode: nothing merged.")
        return 0

    # Ask for confirmation - DEFAULT IS NO (Master Doc rule)
    if not force_yes:
        print()
        print("=" * 70)
        print(" FINAL DECISION")
        print("=" * 70)
        print(" Merge this session into permanent deep memory?")
        print(" Type exactly 'yes' (case-insensitive) to confirm.")
        print(" Anything else (including Enter) = NO MERGE.")
        print("=" * 70)
        try:
            answer = input(" Your answer: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[apply_merge] Input cancelled. NO MERGE "
                  "performed.")
            return 0

        if answer != "yes":
            print(f"[apply_merge] You answered: '{answer}' "
                  f"(not 'yes').")
            print("[apply_merge] NO MERGE performed. Candidate "
                  "kept for later review.")
            return 0
    else:
        print("[apply_merge] --force-yes flag set. Proceeding "
              "without prompt.")

    # === From here on: user has explicitly approved ===

    # Create backup FIRST (before touching anything)
    backup_path = create_backup(root_path)

    # Load current memory
    current_memory = load_deep_memory(root_path)

    # Second-line guard: re-check right before write, in case
    # something changed between --safe and --apply
    if session_name in current_memory.get(
            "sessions_analyzed_list", []):
        print(f"[apply_merge] WARNING: session '{session_name}' "
              f"is already in deep_memory (second check).")
        print("[apply_merge] Refusing to double-merge. "
              "Backup was still created for safety.")
        # Clear the stale candidate to avoid confusion
        clear_pending_candidate(session_path)
        return 2

    # Apply the merge
    print("[apply_merge] Applying merge to deep_memory...")
    new_memory = update_memory_from_session(
        current_memory,
        candidate["session_name"],
        candidate["session_results"],
    )

    save_deep_memory(root_path, new_memory)

    # Log the action for traceability
    log_dir = os.path.join(root_path, "persistent_knowledge")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "merge_history.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{utc_now_iso()}] MERGED session="
                f"{session_name}")
        if backup_path:
            f.write(f" backup="
                    f"{os.path.basename(backup_path)}")
        f.write("\n")

    # Clear the candidate so it can't be re-applied
    clear_pending_candidate(session_path)

    print()
    print("[apply_merge] SUCCESS.")
    print(f"  Sessions in memory : "
          f"{new_memory['total_sessions_analyzed']}")
    print(f"  Objects tracked    : "
          f"{len(new_memory['object_tracks'])}")
    if backup_path:
        print(f"  Rollback backup    : {backup_path}")
    print(f"  Merge log          : {log_path}")
    print()
    return 0


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Human-approved merge executor for "
                    "deep_learning_memory (Master Doc "
                    "section 15).")
    parser.add_argument(
        "session_path", nargs="?",
        help="Path to the session folder containing "
             "pending_merge_candidate.pkl. Not required with "
             "--list-backups.")
    parser.add_argument(
        "--root", default=DEFAULT_ROOT,
        help=f"Project root path (default: {DEFAULT_ROOT})")
    parser.add_argument(
        "--force-yes", action="store_true",
        help="Skip prompt. Still creates backup. Use carefully.")
    parser.add_argument(
        "--show-only", action="store_true",
        help="Only display the preview, do not merge.")
    parser.add_argument(
        "--list-backups", action="store_true",
        help="List all available deep_memory backups and exit.")
    args = parser.parse_args()

    # Handle --list-backups mode
    if args.list_backups:
        if not os.path.isdir(args.root):
            print(f"[apply_merge] ERROR: root path does not "
                  f"exist: {args.root}")
            sys.exit(1)
        list_all_backups(args.root)
        sys.exit(0)

    # Normal mode requires session_path
    if not args.session_path:
        print("[apply_merge] ERROR: session_path is required "
              "(unless using --list-backups).")
        parser.print_help()
        sys.exit(1)

    if not os.path.isdir(args.session_path):
        print(f"[apply_merge] ERROR: session path does not "
              f"exist: {args.session_path}")
        sys.exit(1)

    if not os.path.isdir(args.root):
        print(f"[apply_merge] ERROR: root path does not exist: "
              f"{args.root}")
        sys.exit(1)

    code = apply_merge(
        args.session_path, args.root,
        force_yes=args.force_yes,
        show_only=args.show_only,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()