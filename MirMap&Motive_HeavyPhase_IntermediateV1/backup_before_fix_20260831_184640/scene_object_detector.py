"""
scene_object_detector.py v1.0
====================================================================
Politecnico di Torino - Reactive Collaborative Robotics Thesis
Operator: Kiarash Amiri (s322803) | Supervisor: Prof. Dario Antonelli

Scans all Motive dual-camera AVI recordings with YOLOv8-S.
Detects 18 industrial-relevant COCO classes at 1 FPS sampling.
Outputs per-session JSON + global intelligence report.
====================================================================
"""

import os
import re
import json
import cv2
from datetime import datetime
from ultralytics import YOLO

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
MOTIVE = os.path.join(ROOT, "motive sessions")
SESSIONS = os.path.join(ROOT, "sessions")
KNOWLEDGE = os.path.join(ROOT, "persistent_knowledge")

CLASSES = {
    "person", "chair", "dining table", "bench", "backpack", "handbag",
    "bottle", "cup", "laptop", "keyboard", "mouse", "book", "clock",
    "vase", "scissors", "suitcase", "cell phone", "tv"
}
CONF = 0.30
STRIDE = 30


def scan_video(path, model):
    if not os.path.exists(path):
        return None
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_out = []
    class_counts = {}
    idx = 0
    processed = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % STRIDE == 0:
            results = model(frame, verbose=False, conf=CONF)
            objs = []
            if results and results[0].boxes is not None:
                for b in results[0].boxes:
                    name = model.names[int(b.cls[0])]
                    if name in CLASSES:
                        c = float(b.conf[0])
                        xy = b.xyxy[0].tolist()
                        objs.append({
                            "class": name,
                            "conf": round(c, 3),
                            "bbox": [round(v, 1) for v in xy],
                            "center": [round((xy[0]+xy[2])/2, 1), round((xy[1]+xy[3])/2, 1)],
                            "area_pct": round((xy[2]-xy[0])*(xy[3]-xy[1])/(w*h)*100, 2)
                        })
                        class_counts[name] = class_counts.get(name, 0) + 1
            frames_out.append({
                "frame": idx,
                "time_s": round(idx/fps, 2),
                "objects": objs
            })
            processed += 1
        idx += 1
    cap.release()
    return {
        "file": os.path.basename(path),
        "resolution": f"{w}x{h}",
        "fps": fps,
        "total_frames": total,
        "analyzed": processed,
        "total_detections": sum(class_counts.values()),
        "classes": class_counts,
        "timeline": frames_out
    }


def main():
    os.makedirs(KNOWLEDGE, exist_ok=True)
    print("[1/3] Loading YOLOv8-S...")
    model = YOLO("yolov8s.pt")
    print(f"[OK] {len(model.names)} classes available, {len(CLASSES)} tracked.\n")

    avis = sorted([f for f in os.listdir(MOTIVE) if f.endswith(".avi")]) if os.path.exists(MOTIVE) else []
    pat = re.compile(r"(session_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
    smap = {}
    for a in avis:
        m = pat.search(a)
        if m:
            smap.setdefault(m.group(1), []).append(a)

    print(f"[2/3] Scanning {len(avis)} videos ({len(smap)} sessions)...\n")
    report = {
        "agent": "scene_object_detector",
        "version": "1.0",
        "model": "yolov8s",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "sessions": {}
    }

    for sname, sfiles in sorted(smap.items()):
        print(f"--- {sname} ({len(sfiles)} cams) ---")
        sdata = {"cameras": {}}
        for av in sfiles:
            cam = "cam1" if "Camera 1" in av else "cam_side"
            print(f"  [{cam}] {av} ...", end=" ", flush=True)
            res = scan_video(os.path.join(MOTIVE, av), model)
            if res:
                sdata["cameras"][cam] = res
                cls_str = ", ".join(f"{k}:{v}" for k, v in res["classes"].items())
                print(f"{res['total_detections']} detections | {cls_str}")
            else:
                print("SKIP")

        sdir = os.path.join(SESSIONS, sname)
        if os.path.exists(sdir):
            out = os.path.join(sdir, "yolo_detections.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(sdata, f, indent=2)

        merged = {}
        for cd in sdata["cameras"].values():
            for c, n in cd["classes"].items():
                merged[c] = merged.get(c, 0) + n
        report["sessions"][sname] = {"cams": len(sdata["cameras"]), "classes": merged}
        print()

    gout = os.path.join(KNOWLEDGE, "object_scene_intelligence.json")
    with open(gout, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("[3/3] DONE!")
    print("=" * 55)
    print(f"Global report: {gout}")
    print("=" * 55)
    for sn, sd in report["sessions"].items():
        cs = ", ".join(f"{c}({n})" for c, n in sd["classes"].items())
        print(f"  {sn}: {cs or 'empty'}")
    print("=" * 55)


if __name__ == "__main__":
    main()
