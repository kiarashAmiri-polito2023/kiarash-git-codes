#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scene_object_detector.py — FIXED v2.0
Fixes BUG-B: YOLO was labeling humans as chairs and robots as persons.
Root causes: conf threshold too low (0.25), no class allowlist, no NMS tuning,
no geometric sanity checks, no robot-footprint exclusion zone.
"""

import os
import json
import hashlib
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

# Only these COCO classes are relevant in the MiR100 industrial lab
CLASS_ALLOWLIST = {
    "person", "chair", "backpack", "handbag", "bottle",
    "cup", "laptop", "cell phone", "book", "dining table"
}

# Remap COCO names to our semantic labels
CLASS_REMAP = {
    "dining table": "table",
    "cell phone": "phone",
    "couch": "obstacle_static",
    "tv": "monitor",
    "potted plant": "obstacle_static",
}

# Per-class confidence thresholds (higher = stricter)
CLASS_CONFIDENCE = {
    "person": 0.55,     # Must be confident — safety-critical class
    "chair": 0.60,
    "table": 0.55,
    "laptop": 0.50,
    "bottle": 0.50,
    "backpack": 0.50,
}
DEFAULT_CONFIDENCE = 0.60

# Geometric constraints
MIN_AREA_FRACTION = 0.005   # Box must cover >= 0.5% of frame
MAX_AREA_FRACTION = 0.50    # Box must cover <= 50% of frame
PERSON_MAX_WIDTH_HEIGHT_RATIO = 1.5  # Persons are taller than wide

# Robot exclusion zone (in pixel-normalized coordinates)
ROBOT_ZONE_X_MIN = 0.70    # Right side of frame where robot arm sits
ROBOT_ZONE_Y_MIN = 0.30

# ============================================================
# DISK CACHE CONFIGURATION (BUG-K FIX)
# ============================================================
DETECTOR_VERSION = "2.1"
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "audit_workspace", "cache", "detector"
)

def _frame_hash(frame_bgr):
    """Compute MD5 hash of frame bytes for cache key."""
    return hashlib.md5(frame_bgr.tobytes()).hexdigest()

def _cache_path(frame_hash):
    """Return full path to cache file for a given hash."""
    return os.path.join(CACHE_DIR, frame_hash + ".json")

def _load_cache(frame_bgr, conf_threshold):
    """Load cached detections if valid. Returns list or None."""
    try:
        fhash = _frame_hash(frame_bgr)
        cpath = _cache_path(fhash)
        if not os.path.exists(cpath):
            return None
        with open(cpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != DETECTOR_VERSION:
            return None
        if abs(data.get("conf", 0) - conf_threshold) > 0.01:
            return None
        return data.get("detections", None)
    except Exception:
        return None

def _save_cache(frame_bgr, conf_threshold, detections):
    """Save detections to disk cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        fhash = _frame_hash(frame_bgr)
        cpath = _cache_path(fhash)
        data = {
            "version": DETECTOR_VERSION,
            "conf": conf_threshold,
            "hash": fhash,
            "detections": detections,
        }
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug("Cache save failed: %s", e)




def detect_objects_safe(
    frame_bgr: np.ndarray,
    model,
    frame_id: int = -1,
    robot_pixel_zone: Optional[Tuple[float, float, float, float]] = None
) -> List[Dict]:
    """
    Run YOLO inference with safety-hardened post-processing.
    
    Args:
        frame_bgr: Input image (BGR, uint8)
        model: Loaded YOLO model instance
        frame_id: Frame number for logging
        robot_pixel_zone: (x_min_frac, y_min_frac, x_max_frac, y_max_frac)
                         normalized exclusion zone where robot arm is known to be
    
    Returns:
        List of filtered detection dicts
    """
    if frame_bgr is None or frame_bgr.size == 0:
        logger.warning("Frame %d: empty image, skipping detection", frame_id)
        return []

    # --- CACHE CHECK (BUG-K) ---
    cached = _load_cache(frame_bgr, 0.45)
    if cached is not None:
        logger.debug("Frame %d: cache hit, returning %d cached detections", frame_id, len(cached))
        return cached
    
    h, w = frame_bgr.shape[:2]
    frame_area = h * w
    
    # Run YOLO with hardened parameters
    try:
        results = model.predict(
            source=frame_bgr,
            conf=0.45,          # RAISED from 0.25 — kills most hallucinations
            iou=0.50,           # Standard NMS IoU
            imgsz=640,
            verbose=False,
            agnostic_nms=False, # Class-aware NMS (person ≠ chair)
            max_det=20,         # Cap maximum detections per frame
        )[0]
    except Exception as e:
        logger.error("Frame %d: YOLO inference failed: %s", frame_id, e)
        return []
    
    if results.boxes is None or len(results.boxes) == 0:
        return []
    
    # Extract raw detections
    xyxy_all = results.boxes.xyxy.cpu().numpy()
    conf_all = results.boxes.conf.cpu().numpy()
    cls_all = results.boxes.cls.cpu().numpy().astype(int)
    
    clean_detections = []
    rejected_count = 0
    
    for i, (xyxy, conf, cls_id) in enumerate(zip(xyxy_all, conf_all, cls_all)):
        x1, y1, x2, y2 = xyxy
        raw_name = results.names[int(cls_id)]
        
        # ---- FILTER 1: Class allowlist ----
        if raw_name not in CLASS_ALLOWLIST:
            rejected_count += 1
            continue
        
        label = CLASS_REMAP.get(raw_name, raw_name)
        
        # ---- FILTER 2: Per-class confidence threshold ----
        threshold = CLASS_CONFIDENCE.get(label, DEFAULT_CONFIDENCE)
        if float(conf) < threshold:
            rejected_count += 1
            continue
        
        # ---- FILTER 3: Geometric sanity (area) ----
        box_area = max(1, (x2 - x1) * (y2 - y1))
        area_frac = box_area / frame_area
        
        if area_frac < MIN_AREA_FRACTION or area_frac > MAX_AREA_FRACTION:
            rejected_count += 1
            continue
        
        # ---- FILTER 4: Person aspect ratio (persons are tall, not wide) ----
        if label == "person":
            box_w = x2 - x1
            box_h = y2 - y1
            if box_h > 0 and (box_w / box_h) > PERSON_MAX_WIDTH_HEIGHT_RATIO:
                logger.debug("Frame %d: Rejected 'person' with W/H=%.2f (likely robot/table)",
                           frame_id, box_w / box_h)
                rejected_count += 1
                continue
        
        # ---- FILTER 5: Robot exclusion zone ----
        if label == "person" and robot_pixel_zone is not None:
            rz = robot_pixel_zone
            cx = (x1 + x2) / 2.0 / w  # normalize to [0,1]
            cy = (y1 + y2) / 2.0 / h
            if rz[0] <= cx <= rz[2] and rz[1] <= cy <= rz[3]:
                logger.info("Frame %d: Demoted 'person' to 'robot_arm' in exclusion zone", frame_id)
                label = "robot_arm_static"
        
        clean_detections.append({
            "frame_id": frame_id,
            "class_name": label,
            "class_id": int(cls_id),
            "confidence": round(float(conf), 4),
            "xyxy": [round(float(v), 1) for v in [x1, y1, x2, y2]],
            "area_fraction": round(area_frac, 4),
        })
    
    logger.info(
        "Frame %d: %d detections kept, %d rejected (from %d raw)",
        frame_id, len(clean_detections), rejected_count, len(xyxy_all)
    )
    
    # --- CACHE SAVE (BUG-K) ---
    _save_cache(frame_bgr, 0.45, clean_detections)

    return clean_detections


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def extract_industrial_objects(image, model):
    """DEPRECATED: Use detect_objects_safe() instead."""
    logger.warning("DEPRECATED: extract_industrial_objects() called. Redirecting to detect_objects_safe().")
    return detect_objects_safe(image, model)
