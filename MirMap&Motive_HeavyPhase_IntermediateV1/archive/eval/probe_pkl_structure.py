import pickle, glob, sys, os
sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
s7 = os.path.join(base, "sessions", "session_2026-08-27_17-54-20")

for pkl in glob.glob(os.path.join(s7, "**", "*.pkl"), recursive=True):
    print("\n=== FILE:", os.path.relpath(pkl, base))
    try:
        with open(pkl, "rb") as f:
            d = pickle.load(f)
        print("  type:", type(d).__name__)
        if isinstance(d, dict):
            for k, v in list(d.items())[:10]:
                size = len(v) if hasattr(v, "__len__") else v
                print(f"  key: {k!r:30} | {type(v).__name__:10} | len/val: {size}")
                if isinstance(v, list) and len(v) > 0:
                    print(f"        first item: {type(v[0]).__name__} -> {str(v[0])[:200]}")
    except Exception as e:
        print("  ERROR:", e)
