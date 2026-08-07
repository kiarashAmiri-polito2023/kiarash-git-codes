#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/auto_labeler.py - Auto-Labeling with Grounding DINO
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def create_cvat_xml(annotations, video_name, width, height):
    root = ET.Element("annotations")
    version = ET.SubElement(root, "version")
    version.text = "1.1"
    for ann in annotations:
        image = ET.SubElement(root, "image")
        image.set("id", str(ann["frame_id"]))
        image.set("name", "frame_" + str(ann["frame_id"]).zfill(6))
        image.set("width", str(width))
        image.set("height", str(height))
        box = ET.SubElement(image, "box")
        box.set("label", ann["label"])
        box.set("xtl", str(round(ann["bbox"][0], 2)))
        box.set("ytl", str(round(ann["bbox"][1], 2)))
        box.set("xbr", str(round(ann["bbox"][2], 2)))
        box.set("ybr", str(round(ann["bbox"][3], 2)))
        box.set("occluded", "0")
        box.set("source", "auto_grounding_dino")
    xml_str = ET.tostring(root, encoding="unicode")
    return minidom.parseString(xml_str).toprettyxml(indent="  ")


def run_grounding_dino(image, text_prompts, threshold=0.3):
    try:
        from groundingdino.util.inference import load_model, predict
        # Placeholder: needs model weights
        return []
    except ImportError:
        print("  [WARN] groundingdino not installed. Returning empty.")
        print("  Install: pip install groundingdino-py")
        return []


def auto_label_video(video_path, prompts, output_path, sample_rate=5):
    if not HAS_CV2:
        print("[ERROR] opencv-python required. pip install opencv-python")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[ERROR] Cannot open " + video_path)
        return

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("[AUTO] Video: " + str(total) + " frames, " + str(width) + "x" + str(height))

    all_ann = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % sample_rate == 0:
            dets = run_grounding_dino(frame, prompts.replace(".", " . "))
            for d in dets:
                all_ann.append({"frame_id": idx, "label": d["label"], "bbox": d["bbox"]})
        idx += 1
    cap.release()

    xml_content = create_cvat_xml(all_ann, os.path.basename(video_path), width, height)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print("[AUTO] Saved " + str(len(all_ann)) + " detections to " + output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--prompts", default="person.hat.wrist.robot")
    parser.add_argument("--output", default="auto_labels.xml")
    parser.add_argument("--sample-rate", type=int, default=5)
    args = parser.parse_args()
    auto_label_video(args.video, args.prompts, args.output, args.sample_rate)


if __name__ == "__main__":
    main()
