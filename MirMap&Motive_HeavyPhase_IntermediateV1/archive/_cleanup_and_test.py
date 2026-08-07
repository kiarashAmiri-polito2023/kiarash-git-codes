# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
AGENTS_DIR = PROJECT_ROOT / "agents"
ARCHIVE_DIR = PROJECT_ROOT / "archive"

ARCHIVE_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("  PHASE 2: CLEANUP + RENAME + TEST")
print("=" * 60)
print("")

# 1. ARCHIVE OBSOLETE AGENTS
print("[1/3] Archiving obsolete agents...")
obsolete = [
    "entity_surgery.py",
    "merge_entities.py",
]

# Also check root-level fix scripts
root_obsolete = [
    "fix_all.py",
    "fix_syntax_surgical.py",
]

archived = 0
for name in obsolete:
    src = AGENTS_DIR / name
    if src.exists():
        dst = ARCHIVE_DIR / name
        shutil.move(str(src), str(dst))
        print("  [ARCHIVED] agents/%s -> archive/%s" % (name, name))
        archived += 1
    else:
        print("  [SKIP] agents/%s not found" % name)

for name in root_obsolete:
    src = PROJECT_ROOT / name
    if src.exists():
        dst = ARCHIVE_DIR / name
        shutil.move(str(src), str(dst))
        print("  [ARCHIVED] %s -> archive/%s" % (name, name))
        archived += 1
    else:
        print("  [SKIP] %s not found" % name)

print("  Total archived: %d" % archived)
print("")

# 2. RENAME OLD SNAPSHOT
print("[2/3] Renaming old snapshot...")
old_snapshot = PROJECT_ROOT / "theises planer snapshout .py"
new_snapshot_name = "theises_planer_snapshot_v4_old.py"

if old_snapshot.exists():
    dst = ARCHIVE_DIR / new_snapshot_name
    shutil.move(str(old_snapshot), str(dst))
    print("  [RENAMED] 'theises planer snapshout .py' -> archive/%s" % new_snapshot_name)
else:
    # Try to find it with different spacing
    found = False
    for f in PROJECT_ROOT.glob("theises*"):
        if f.is_file() and f.suffix == ".py":
            dst = ARCHIVE_DIR / ("old_" + f.name.replace(" ", "_"))
            shutil.move(str(f), str(dst))
            print("  [RENAMED] '%s' -> archive/%s" % (f.name, dst.name))
            found = True
            break
    if not found:
        print("  [SKIP] Old snapshot not found in project root")
print("")

# 3. VERIFY NEW AGENT EXISTS
print("[3/3] Verifying new Master Agent...")
master = AGENTS_DIR / "project_snapshot.py"
if master.exists():
    size_kb = os.path.getsize(master) / 1024
    print("  [OK] project_snapshot.py v5 exists (%.1f KB)" % size_kb)
else:
    print("  [ERROR] project_snapshot.py not found!")

print("")
print("=" * 60)
print("  CLEANUP COMPLETE")
print("  Archive folder: %s" % ARCHIVE_DIR)
print("  Contents: %s" % os.listdir(ARCHIVE_DIR))
print("=" * 60)
