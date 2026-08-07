import sys
import os
from pathlib import Path

print("=== ENV PROBE ===")
print("PYTHON_EXE:", sys.executable)
print("CWD:", Path.cwd().resolve())
print("")

# Check dataset
ds = Path("dataset")
print("DATASET_EXISTS:", ds.exists())
if ds.exists():
    print("  train.jsonl:", (ds / "train.jsonl").is_file())
    print("  val.jsonl:", (ds / "val.jsonl").is_file())
    print("  Files:", [f.name for f in sorted(ds.iterdir())[:10]])
print("")

# Check sessions/S7
s7 = Path("sessions/S7")
print("SESSIONS_S7_EXISTS:", s7.exists())
if s7.exists():
    print("  Top files:", [f.name for f in sorted(s7.iterdir())[:10]])
print("")

# Check key packages
for m in ["torch", "transformers", "peft", "bitsandbytes", "accelerate", "PIL"]:
    try:
        mod = __import__(m)
        ver = getattr(mod, "__version__", "UNKNOWN")
        print(f"OK  {m:15s} {ver}")
    except Exception as e:
        print(f"MISS {m:15s} (NOT FOUND)")
print("")

# Check GPU
try:
    import torch
    print("CUDA_AVAILABLE:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("DEVICE_COUNT:", torch.cuda.device_count())
        print("GPU_NAME:", torch.cuda.get_device_name(0))
        print("VRAM_TOTAL_GB:", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2))
    else:
        print("NO CUDA GPU DETECTED")
except Exception as e:
    print("TORCH_GPU_CHECK_FAIL:", e)

print("=== END ===")
