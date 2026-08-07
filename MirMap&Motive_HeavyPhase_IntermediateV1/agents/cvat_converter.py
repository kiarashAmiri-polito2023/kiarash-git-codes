#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents/cvat_converter.py - CVAT Export to Project JSONL
"""

import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def parse_cvat_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    annotations = []
    for image in root.findall("image"):
        frame_id = int(image.get("id", 0))
        width = int(image.get("width", 0))
        height = int(image.get("height", 0))
        for box in image.findall("box"):
            xtl = float(box.get("xtl", 0))
            ytl = float(box.get("ytl", 0))
            xbr = float(box.get("xbr", 0))
            ybr = float(box.get("ybr", 0))
            annotations.append({
                "frame_id": frame_id,
                "label": box.get("label", "unknown"),
                "bbox_pixel": [xtl, ytl, xbr, ybr],
                "bbox_normalized": [xtl/width if width else 0, ytl/height if height else 0,
                                     xbr/width if width else 0, ybr/height if height else 0],
                "image_width": width, "image_height": height,
                "occluded": box.get("occluded", "0") == "1",
                "track_id": box.get("track_id", None),
            })
    return annotations


def convert_to_jsonl(annotations, session_id, camera_name, video_path, fps=30.0):
    results = []
    for ann in annotations:
        results.append({
            "session_id": session_id, "video_path": video_path,
            "camera_name": camera_name, "frame_index": ann["frame_id"],
            "video_timestamp_sec": round(ann["frame_id"] / fps, 4),
            "label": ann["label"], "registry_id": None,
            "bbox_pixel": ann["bbox_pixel"], "bbox_normalized": ann["bbox_normalized"],
            "world_coordinates_m": None, "coordinate_frame": "camera_pixel",
            "track_id": ann.get("track_id"), "occluded": ann["occluded"],
            "confidence": 1.0, "user_confirmed": True,
            "provenance": {"source": "cvat_export", "converted_at_utc": utc_now_iso()},
            "image_width": ann["image_width"], "image_height": ann["image_height"],
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--camera", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", default="motive_annotations.jsonl")
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()

    print("[CVAT] Parsing " + args.input)
    annotations = parse_cvat_xml(args.input)
    print("[CVAT] Found " + str(len(annotations)) + " annotations")

    entries = convert_to_jsonl(annotations, args.session, args.camera, args.video, args.fps)
    with open(args.output, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("[CVAT] Wrote " + args.output)


if __name__ == "__main__":
    main()
