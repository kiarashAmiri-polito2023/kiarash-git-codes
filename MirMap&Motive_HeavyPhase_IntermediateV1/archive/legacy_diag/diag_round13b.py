import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
a18 = os.path.join(root, "agents", "A18_deep_agent_verifier.py")
a15 = os.path.join(root, "agents", "A15_referee_ai_loop.py")

print("=" * 70)
print("FULL SOURCE: A18_deep_agent_verifier.py")
print("=" * 70)
with open(a18, "r", encoding="utf-8-sig") as f:
    for i, line in enumerate(f, 1):
        print(str(i).rjust(4) + ": " + line.rstrip())

print("")
print("=" * 70)
print("A15 KEY FUNCTIONS: discover_free_models, call_ai, main, load_key")
print("=" * 70)
with open(a15, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

capture = False
target_funcs = ["def discover_free_models", "def call_ai", "def main", "def load_key"]
for i, line in enumerate(lines, 1):
    stripped = line.rstrip()
    is_new_def = stripped.strip().startswith("def ")
    if any(t in stripped for t in target_funcs):
        capture = True
    elif is_new_def and capture:
        capture = False
    if capture:
        print(str(i).rjust(4) + ": " + stripped)

print("")
print("=== BOM CHECK ===")
with open(a18, "rb") as f:
    raw = f.read(4)
    print("A18 first bytes: " + str(raw) + " | Has BOM: " + str(raw.startswith(b"\xef\xbb\xbf")))
with open(a15, "rb") as f:
    raw = f.read(4)
    print("A15 first bytes: " + str(raw) + " | Has BOM: " + str(raw.startswith(b"\xef\xbb\xbf")))

print("")
print("=== ROUND 13b DONE ===")
