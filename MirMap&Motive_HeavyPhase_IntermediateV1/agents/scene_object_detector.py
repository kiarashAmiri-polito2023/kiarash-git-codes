"""
scene_object_detector.py - Fixed v2
Fixes: timestamp, cache eviction, safe-state, pipeline compatible
"""
import os, sys, json, time, hashlib
from pathlib import Path

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[WARN] ultralytics not installed")

MODEL_PATH = os.environ.get("YOLO_MODEL", "yolov8n.pt")
CACHE_DIR = Path(os.environ.get("DETECT_CACHE", "detection_cache"))
CACHE_MAX_FILES = 500
CACHE_TTL_SEC = 3600
CONF_THRESHOLD = 0.45
MAX_DETECT = 20
CLASS_ALLOWLIST = {"person", "chair", "box", "forklift", "obstacle"}
CLASS_REMAP = {"person": "human", "box": "obstacle_box"}
_model = None

def get_model():
    global _model
    if _model is not None:
        return _model
    if not YOLO_AVAILABLE:
        return None
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = YOLO(MODEL_PATH)
        _model.to(device)
        print(f"[OK] YOLO loaded on {device}")
        return _model
    except Exception as e:
        print(f"[ERROR] YOLO load failed: {e}")
        return None

def _evict_cache():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    now = time.time()
    for f in files:
        if (now - f.stat().st_mtime) > CACHE_TTL_SEC:
            f.unlink(missing_ok=True)
    files = sorted(CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    while len(files) > CACHE_MAX_FILES:
        files[0].unlink(missing_ok=True)
        files = files[1:]

def _cache_key(frame_bgr) -> str:
    h, w = frame_bgr.shape[:2]
    sample = frame_bgr[::16, ::16].tobytes()
    return hashlib.md5(f"{h}_{w}_{len(sample)}_".encode() + sample).hexdigest()

def detect_objects_safe(frame_bgr, timestamp: float = None) -> dict:
    if timestamp is None:
        timestamp = time.time()
    result_template = {"timestamp": timestamp, "detections": [], "human_detected": False, "safe_state": "UNKNOWN", "source": "none"}
    model = get_model()
    if model is None:
        result_template["safe_state"] = "NO_MODEL"
        return result_template
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(frame_bgr)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < CACHE_TTL_SEC:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cached["timestamp"] = timestamp
            cached["source"] = "cache"
            return cached
        except Exception:
            cache_file.unlink(missing_ok=True)
    try:
        h, w = frame_bgr.shape[:2]
        results = model.predict(frame_bgr, conf=CONF_THRESHOLD, max_det=MAX_DETECT, verbose=False)
        detections = []
        human_detected = False
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label_raw = model.names.get(cls_id, "unknown")
                if CLASS_ALLOWLIST and label_raw not in CLASS_ALLOWLIST:
                    continue
                label = CLASS_REMAP.get(label_raw, label_raw)
                conf = round(float(box.conf[0]), 4)
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                det = {"label": label, "label_raw": label_raw, "confidence": conf, "box": [x1, y1, x2, y2], "box_norm": [round(x1/w,4), round(y1/h,4), round(x2/w,4), round(y2/h,4)], "timestamp": timestamp}
                detections.append(det)
                if label in ("human", "person"):
                    human_detected = True
        safe_state = "HUMAN_DETECTED" if human_detected else "CLEAR"
        output = {"timestamp": timestamp, "detections": detections, "human_detected": human_detected, "safe_state": safe_state, "source": "inference"}
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(output), encoding="utf-8")
        tmp.replace(cache_file)
        _evict_cache()
        return output
    except Exception as e:
        print(f"[ERROR] Detection failed: {e}")
        result_template["safe_state"] = "ERROR"
        return result_template

if __name__ == "__main__":
    import cv2
    test_frame = cv2.imread(sys.argv[1]) if len(sys.argv) > 1 else None
    if test_frame is None:
        import numpy as np
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    r = detect_objects_safe(test_frame)
    print(json.dumps(r, indent=2))