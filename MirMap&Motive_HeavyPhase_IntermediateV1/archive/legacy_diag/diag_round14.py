import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
a15 = os.path.join(root, "agents", "A15_referee_ai_loop.py")

with open(a15, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

print("=" * 70)
print("A15 LINES 1-68 (HEADER, IMPORTS, CONSTANTS)")
print("=" * 70)
for i in range(0, 68):
    if i < len(lines):
        print(str(i+1).rjust(4) + ": " + lines[i].rstrip())

print("")
print("=" * 70)
print("A15 LINES 129-208 (PERSONAS + HELPER FUNCTIONS)")
print("=" * 70)
for i in range(128, 208):
    if i < len(lines):
        print(str(i+1).rjust(4) + ": " + lines[i].rstrip())

print("")
print("=== ROUND 14 DONE ===")
