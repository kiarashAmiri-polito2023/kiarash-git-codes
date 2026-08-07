import os, sys, io, re, ast

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
detector_path = os.path.join(ROOT, "agents", "scene_object_detector.py")
snapshot_path = os.path.join(ROOT, "agents", "project_snapshot.py")

print("=" * 70)
print("[1/3] STRUCTURAL: scene_object_detector.py & project_snapshot.py")
print("=" * 70)

for p, label in [(detector_path, "scene_object_detector"), (snapshot_path, "project_snapshot")]:
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        lines = content.splitlines()
        print(f"[{label}] Lines: {len(lines)} | Size: {os.path.getsize(p)}B")
        
        # Check AST functions
        try:
            tree = ast.parse(content)
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            print(f"  Classes ({len(classes)}): {classes}")
            print(f"  Functions ({len(funcs)}): {funcs}")
        except Exception as e:
            print(f"  AST parse error: {e}")
    else:
        print(f"[{label}] MISSING!")

print("\n" + "=" * 70)
print("[2/3] FUNCTIONAL: Cache inspection in scene_object_detector.py")
print("=" * 70)
if os.path.exists(detector_path):
    with open(detector_path, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    print("Has 'pickle' import:", "pickle" in src)
    print("Has 'cache' logic:", bool(re.search(r'cache|\.pkl|save_results|load_results', src, re.IGNORECASE)))
    print("YOLO confidence threshold check:")
    for line in src.splitlines():
        if "conf" in line or "model(" in line or "0.45" in line or "0.25" in line:
            print("  >", line.strip())

print("\n" + "=" * 70)
print("[3/3] BEHAVIORAL: Integration hooks in project_snapshot.py")
print("=" * 70)
if os.path.exists(snapshot_path):
    with open(snapshot_path, "r", encoding="utf-8-sig", errors="replace") as f:
        snap_src = f.read()
    print("Calls video_learning_agent:", "video_learning_agent" in snap_src)
    print("Calls scene_object_detector:", "scene_object_detector" in snap_src)
    print("Calls slam_to_bev:", "slam_to_bev" in snap_src)
    print("Writes MASTER_REPORT.md:", "MASTER_REPORT.md" in snap_src)

print("\n=== ROUND 16 DONE ===")
