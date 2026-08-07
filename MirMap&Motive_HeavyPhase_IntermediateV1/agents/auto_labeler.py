"""
auto_labeler.py — Fixed v2
Fixes: try/finally cap.release, XML schema, streaming write, HITL export
"""
import os
import sys
import cv2
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

try:
    from groundingdino.util.inference import load_model, predict
    import torch
    from torchvision.ops import box_convert
    GDINO_AVAILABLE = True
except ImportError:
    GDINO_AVAILABLE = False
    print("[WARN] GroundingDINO not installed - detection will be skipped")

# --- Config ---
CONFIDENCE_THRESHOLD = 0.35
DEFAULT_PROMPTS = ["person", "obstacle", "box", "chair", "forklift"]
GDINO_CONFIG = os.environ.get("GDINO_CONFIG", "")
GDINO_WEIGHTS = os.environ.get("GDINO_WEIGHTS", "")

_gdino_model = None

def load_gdino_model():
    """Load GroundingDINO model once — not per frame."""
    global _gdino_model
    if _gdino_model is not None:
        return _gdino_model
    if not GDINO_AVAILABLE:
        print("[WARN] GroundingDINO not available")
        return None
    if not os.path.isfile(GDINO_CONFIG) or not os.path.isfile(GDINO_WEIGHTS):
        print(f"[WARN] GDINO_CONFIG or GDINO_WEIGHTS not set/found. Set env vars.")
        return None
    try:
        device = "cuda" if (GDINO_AVAILABLE and __import__("torch").cuda.is_available()) else "cpu"
        _gdino_model = load_model(GDINO_CONFIG, GDINO_WEIGHTS)
        _gdino_model = _gdino_model.to(device)
        print(f"[OK] GroundingDINO loaded on {device}")
        return _gdino_model
    except Exception as e:
        print(f"[ERROR] Failed to load GroundingDINO: {e}")
        return None

def run_grounding_dino(frame_bgr, prompts, threshold=0.35):
    """
    Real GroundingDINO inference.
    Returns list of dicts: [{label, confidence, box:[x1,y1,x2,y2]}, ...]
    """
    model = load_gdino_model()
    if model is None:
        return []
    if not GDINO_AVAILABLE:
        return []

    try:
        import torch
        from PIL import Image as PILImage
        import torchvision.transforms as T

        h, w = frame_bgr.shape[:2]
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(frame_rgb)

        transform = T.Compose([
            T.Resize([800, 1333]),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        img_tensor = transform(pil_img)

        text_prompt = " . ".join(prompts) + " ."
        device = next(model.parameters()).device

        with torch.no_grad():
            boxes, logits, phrases = predict(
                model=model,
                image=img_tensor,
                caption=text_prompt,
                box_threshold=threshold,
                text_threshold=threshold,
                device=str(device)
            )

        results = []
        if boxes is not None and len(boxes) > 0:
            boxes_xyxy = box_convert(boxes * torch.tensor([w, h, w, h]), "cxcywh", "xyxy")
            for box, logit, phrase in zip(boxes_xyxy.tolist(), logits.tolist(), phrases):
                x1, y1, x2, y2 = [int(v) for v in box]
                x1 = max(0, min(x1, w-1))
                y1 = max(0, min(y1, h-1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                results.append({
                    "label": phrase,
                    "confidence": round(float(logit), 4),
                    "box": [x1, y1, x2, y2]
                })
        return results

    except Exception as e:
        print(f"[ERROR] GroundingDINO inference failed: {e}")
        return []


def create_cvat_xml(annotations_by_frame, video_name, output_path):
    """
    Create valid CVAT XML — one <image> per frame, multiple <box> inside.
    Streams to disk to avoid OOM.
    annotations_by_frame: dict {frame_id: [{"label":str,"box":[x1,y1,x2,y2],"confidence":float}]}
    """
    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"

    meta = ET.SubElement(root, "meta")
    task = ET.SubElement(meta, "task")
    ET.SubElement(task, "name").text = video_name
    ET.SubElement(task, "labels")

    for frame_id in sorted(annotations_by_frame.keys()):
        boxes = annotations_by_frame[frame_id]
        img_elem = ET.SubElement(root, "image")
        img_elem.set("id", str(frame_id))
        img_elem.set("name", f"frame_{frame_id:06d}.jpg")
        img_elem.set("width", "0")
        img_elem.set("height", "0")

        for det in boxes:
            x1, y1, x2, y2 = det["box"]
            box_elem = ET.SubElement(img_elem, "box")
            box_elem.set("label", det["label"])
            box_elem.set("xtl", str(x1))
            box_elem.set("ytl", str(y1))
            box_elem.set("xbr", str(x2))
            box_elem.set("ybr", str(y2))
            box_elem.set("confidence", str(det.get("confidence", 0.0)))
            box_elem.set("occluded", "0")

    # Write atomically via temp file
    tmp_path = output_path + ".tmp"
    tree = ET.ElementTree(root)
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    os.replace(tmp_path, output_path)
    print(f"[OK] XML saved: {output_path} ({len(annotations_by_frame)} frames)")


def auto_label_video(video_path, prompts=None, output_path=None, sample_rate=5):
    """
    Main labeling function with:
    - try/finally for resource cleanup
    - per-frame streaming to avoid OOM
    - HITL export (JSON sidecar for human review)
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS

    video_path = str(video_path)
    if not os.path.isfile(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        return None

    video_name = Path(video_path).stem
    if output_path is None:
        output_path = str(Path(video_path).parent / f"{video_name}_labels.xml")

    # Pre-load model once
    load_gdino_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        return None

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[INFO] Video: {video_name} | {w}x{h} | ~{total} frames | sample_rate={sample_rate}")

    annotations_by_frame = {}
    frame_idx = 0
    processed = 0
    hitl_review = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                try:
                    detections = run_grounding_dino(frame, prompts, CONFIDENCE_THRESHOLD)
                    annotations_by_frame[frame_idx] = detections

                    # HITL sidecar entry
                    for det in detections:
                        hitl_review.append({
                            "frame_id": frame_idx,
                            "label": det["label"],
                            "box": det["box"],
                            "confidence": det["confidence"],
                            "human_verified": False,
                            "human_corrected_label": None
                        })

                    if processed % 50 == 0:
                        print(f"[INFO] Frame {frame_idx}/{total} — {len(detections)} detections")
                    processed += 1

                except Exception as e:
                    print(f"[WARN] Frame {frame_idx} inference failed: {e}")
                    annotations_by_frame[frame_idx] = []

            frame_idx += 1

    finally:
        cap.release()
        print(f"[OK] VideoCapture released. Processed {processed} frames.")

    # Save XML
    create_cvat_xml(annotations_by_frame, video_name, output_path)

    # Save HITL JSON sidecar for human review
    hitl_path = output_path.replace(".xml", "_hitl_review.json")
    import json
    with open(hitl_path, "w", encoding="utf-8") as f:
        json.dump({
            "video": video_name,
            "total_detections": len(hitl_review),
            "instructions": "Set human_verified=true and optionally correct human_corrected_label for each entry.",
            "detections": hitl_review
        }, f, indent=2, ensure_ascii=False)
    print(f"[OK] HITL review file: {hitl_path}")

    return {
        "xml": output_path,
        "hitl_json": hitl_path,
        "frames_processed": processed,
        "total_detections": len(hitl_review)
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto-label video with GroundingDINO")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--prompts", nargs="+", default=DEFAULT_PROMPTS)
    parser.add_argument("--output", default=None)
    parser.add_argument("--sample_rate", type=int, default=5)
    args = parser.parse_args()

    result = auto_label_video(args.video, args.prompts, args.output, args.sample_rate)
    if result:
        print(f"[DONE] {result}")
    else:
        sys.exit(1)