#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_quality_agent.py - Industry-Grade Video Quality Agent (v2.0)

Checks 15 VLA-critical quality factors based on standards from:
- Google DeepMind (RT-2, RT-X, Open X-Embodiment)
- Physical Intelligence (pi-0, pi-0.5)
- Tesla Optimus, Figure AI, 1X Technologies
- NVIDIA GR00T, UC Berkeley DROID, Stanford ALOHA
- Meta Ego4D, HuggingFace LeRobot

Output: VIDEO_QA_REPORT_FOR_AI.txt (Desktop)
"""
import os, sys, cv2, csv, glob, json, math
import numpy as np
from datetime import datetime, timezone
from collections import Counter

VERSION = "2.0"

# ============ INDUSTRY STANDARDS (from real papers) ============
MIN_FPS = 20                          # Berkeley DROID minimum
IDEAL_FPS = 30                        # Google RT-X standard
MAX_FPS_JITTER_PCT = 5.0              # Tesla standard
MIN_RESOLUTION_HEIGHT = 480           # Physical Intelligence pi-0
IDEAL_RESOLUTION_HEIGHT = 720         # Modern VLA standard
MAX_MOTION_BLUR_PCT = 15.0            # Figure AI standard
MAX_FROZEN_FRAMES_PCT = 2.0           # NVIDIA GR00T
MIN_BRIGHTNESS = 40                   # HDR standard
MAX_BRIGHTNESS = 220
MIN_CONTRAST = 25                     # Berkeley
MIN_SHARPNESS = 40                    # Focus threshold
MAX_OCCLUSION_PCT = 60.0              # Stanford ALOHA
MIN_SCENE_DIVERSITY = 0.15            # Meta Ego4D score
MAX_SYNC_DRIFT_FRAMES = 3             # Google RT-X strict
MAX_OVERLAY_TEXT_REGIONS = 2          # NVIDIA GR00T data leakage

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def find_project_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)

def list_video_sessions(motive_dir):
    if not os.path.isdir(motive_dir):
        return {}
    all_files = os.listdir(motive_dir)
    sessions = {}
    for f in all_files:
        if not f.endswith(".avi"):
            continue
        parts = f.split("-Camera")
        if len(parts) < 2:
            continue
        sid = parts[0]
        cam = "Camera" + parts[1].replace(".avi", "").strip()
        sessions.setdefault(sid, []).append((cam, f))
    result = {}
    for sid, cams in sessions.items():
        csv_name = sid + ".csv"
        csv_path = os.path.join(motive_dir, csv_name) if csv_name in all_files else None
        result[sid] = {"cameras": cams, "csv": csv_path}
    return result

def count_csv_frames(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        return 0
    n = 0
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 7:
                    parts = line.split(",")
                    if parts and parts[0].strip().isdigit():
                        n += 1
    except Exception:
        pass
    return n

# ============ CHECK 5: Ghost Overlay Detection ============
def detect_ghost_overlay(gray):
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    small_blobs, large_blobs = 0, 0
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        if area < 5:
            continue
        if 5 <= area <= 200 and 0.5 <= (w / max(h, 1)) <= 2.0:
            small_blobs += 1
        elif area > 500:
            large_blobs += 1
    edges = cv2.Canny(gray, 100, 200)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=30, maxLineGap=10)
    line_count = len(lines) if lines is not None else 0
    return small_blobs, large_blobs, line_count

# ============ CHECK 8: Motion Blur ============
def measure_motion_blur(gray):
    """Higher return = sharper. Below MIN_SHARPNESS = blurry."""
    return cv2.Laplacian(gray, cv2.CV_64F).var()

# ============ CHECK 7: Dynamic Range (HDR) ============
def measure_dynamic_range(gray):
    p5, p95 = np.percentile(gray, [5, 95])
    return float(p95 - p5)

# ============ CHECK 10: Scene Diversity (Meta Ego4D) ============
def compute_scene_diversity(histograms):
    if len(histograms) < 2:
        return 0.0
    diffs = []
    for i in range(1, len(histograms)):
        d = cv2.compareHist(histograms[i-1], histograms[i], cv2.HISTCMP_BHATTACHARYYA)
        diffs.append(d)
    return float(np.mean(diffs))

# ============ CHECK 11: Data Leakage (Text/UI/Watermark) ============
def detect_text_overlay_regions(gray):
    """Detect UI/timestamp/watermark regions using MSER."""
    try:
        mser = cv2.MSER_create()
        regions, _ = mser.detectRegions(gray)
        text_like = 0
        for region in regions:
            if len(region) < 10 or len(region) > 500:
                continue
            x, y, w, h = cv2.boundingRect(region)
            if h > 5 and w > 5 and 0.2 < h/max(w, 1) < 3.0:
                text_like += 1
        return text_like
    except Exception:
        return 0

# ============ CHECK 12: Occlusion Ratio (Stanford ALOHA) ============
def estimate_foreground_ratio(gray):
    """Estimate what % of frame is dominated by close objects."""
    edges = cv2.Canny(gray, 50, 150)
    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    foreground_pct = (np.sum(thresh > 0) / thresh.size) * 100
    edge_density = (np.sum(edges > 0) / edges.size) * 100
    return foreground_pct, edge_density

# ============ CHECK 13: Temporal Consistency ============
def measure_temporal_jitter(prev_gray, gray):
    if prev_gray is None:
        return 0.0
    diff = cv2.absdiff(gray, prev_gray)
    return float(np.mean(diff))

# ============ MAIN ANALYSIS ============
def analyze_video(video_path, csv_frames, out_dir):
    result = {
        "file": os.path.basename(video_path),
        "path": video_path,
        "opened": False,
        "checks": {},
        "issues": [],
        "warnings": [],
        "info": [],
        "metrics": {},
        "vla_score": 0,
        "verdict": "UNKNOWN"
    }
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        result["issues"].append("Cannot open video file")
        result["verdict"] = "FAILED_TO_OPEN"
        return result
    
    result["opened"] = True
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    duration = total / fps if fps > 0 else 0
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    bitrate_mbps = (file_size_mb * 8) / duration if duration > 0 else 0
    
    result["metrics"] = {
        "total_frames": total,
        "fps": round(fps, 2),
        "width": w,
        "height": h,
        "duration_s": round(duration, 2),
        "codec": codec,
        "file_size_mb": round(file_size_mb, 2),
        "bitrate_mbps": round(bitrate_mbps, 2)
    }
    
    # ==== CHECK 1: Frame Sync (Google RT-X) ====
    if csv_frames > 0:
        diff = total - csv_frames
        result["metrics"]["csv_frames"] = csv_frames
        result["metrics"]["sync_diff_frames"] = diff
        if abs(diff) == 0:
            result["checks"]["frame_sync"] = "PASS"
        elif abs(diff) <= MAX_SYNC_DRIFT_FRAMES:
            result["checks"]["frame_sync"] = "WARN"
            result["warnings"].append(f"[CHECK 1/Google RT-X] Minor sync drift: video={total} csv={csv_frames} (diff={diff})")
        else:
            result["checks"]["frame_sync"] = "FAIL"
            result["issues"].append(f"[CHECK 1/Google RT-X] MAJOR sync mismatch: video={total} csv={csv_frames} (diff={diff}). VLA training requires perfectly aligned frames.")
    else:
        result["checks"]["frame_sync"] = "SKIP"
    
    # ==== CHECK 3: Codec & Bitrate (LeRobot) ====
    if bitrate_mbps < 2.0:
        result["checks"]["codec_bitrate"] = "FAIL"
        result["issues"].append(f"[CHECK 3/LeRobot] Bitrate too low ({bitrate_mbps:.1f} Mbps). Compression artifacts will degrade VLA training. Standard: >5 Mbps.")
    elif bitrate_mbps < 5.0:
        result["checks"]["codec_bitrate"] = "WARN"
        result["warnings"].append(f"[CHECK 3/LeRobot] Low bitrate ({bitrate_mbps:.1f} Mbps). Consider higher quality export.")
    else:
        result["checks"]["codec_bitrate"] = "PASS"
    
    # ==== CHECK 4: Resolution (Physical Intelligence) ====
    if h < MIN_RESOLUTION_HEIGHT:
        result["checks"]["resolution"] = "FAIL"
        result["issues"].append(f"[CHECK 4/Physical Intelligence] Resolution too low ({w}x{h}). VLA models need >={MIN_RESOLUTION_HEIGHT}p.")
    elif h < IDEAL_RESOLUTION_HEIGHT:
        result["checks"]["resolution"] = "WARN"
    else:
        result["checks"]["resolution"] = "PASS"
    
    # ==== CHECK 2: FPS (Berkeley DROID) ====
    if fps < MIN_FPS:
        result["checks"]["fps"] = "FAIL"
        result["issues"].append(f"[CHECK 2/Berkeley DROID] FPS too low ({fps:.1f}). Minimum for VLA action learning is {MIN_FPS} FPS.")
    elif fps < IDEAL_FPS:
        result["checks"]["fps"] = "WARN"
    else:
        result["checks"]["fps"] = "PASS"
    
    # ==== Deep frame analysis ====
    n_samples = min(200, total)
    sample_idx = set(np.linspace(0, total - 1, n_samples, dtype=int).tolist())
    keyframe_idx = [0, total // 8, total // 4, total // 2, (3 * total) // 4, (7 * total) // 8, total - 1]
    keyframe_idx = [k for k in keyframe_idx if 0 <= k < total]
    
    brightness_list, contrast_list, sharpness_list, dynamic_range_list = [], [], [], []
    small_blobs_hist, large_blobs_hist, line_hist = [], [], []
    text_regions_hist = []
    foreground_hist, edge_hist = [], []
    temporal_jitter_hist = []
    histograms = []
    frozen_count = 0
    ir_mode_count = 0
    prev_gray = None
    
    cam_tag = os.path.basename(video_path).split("-Camera")[-1].replace(".avi", "").strip().replace(" ", "_").replace("(", "").replace(")", "")
    
    frame_i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_i in keyframe_idx:
            out_img = os.path.join(out_dir, f"{cam_tag}_frame_{frame_i:05d}.jpg")
            cv2.imwrite(out_img, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        if frame_i in sample_idx:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            mean_b = float(np.mean(gray))
            std_c = float(np.std(gray))
            brightness_list.append(mean_b)
            contrast_list.append(std_c)
            
            sharpness_list.append(measure_motion_blur(gray))
            dynamic_range_list.append(measure_dynamic_range(gray))
            
            non_zero_pct = (np.count_nonzero(gray > 30) / gray.size) * 100
            if non_zero_pct < 3.0 and mean_b < 15:
                ir_mode_count += 1
            
            small_b, large_b, lines = detect_ghost_overlay(gray)
            small_blobs_hist.append(small_b)
            large_blobs_hist.append(large_b)
            line_hist.append(lines)
            
            text_regions_hist.append(detect_text_overlay_regions(gray))
            
            fg, ed = estimate_foreground_ratio(gray)
            foreground_hist.append(fg)
            edge_hist.append(ed)
            
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            histograms.append(hist)
            
            jitter = measure_temporal_jitter(prev_gray, gray)
            temporal_jitter_hist.append(jitter)
            
            if prev_gray is not None:
                diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
                if diff < 0.3:
                    frozen_count += 1
            prev_gray = gray
        
        frame_i += 1
    cap.release()
    
    if not brightness_list:
        result["issues"].append("No frames could be analyzed")
        result["verdict"] = "CORRUPT"
        return result
    
    # Aggregate all metrics
    n = len(brightness_list)
    avg_b = float(np.mean(brightness_list))
    avg_c = float(np.mean(contrast_list))
    avg_s = float(np.mean(sharpness_list))
    avg_dr = float(np.mean(dynamic_range_list))
    avg_sb = float(np.mean(small_blobs_hist))
    max_sb = int(np.max(small_blobs_hist))
    avg_lines = float(np.mean(line_hist))
    avg_text = float(np.mean(text_regions_hist))
    avg_fg = float(np.mean(foreground_hist))
    avg_ed = float(np.mean(edge_hist))
    scene_div = compute_scene_diversity(histograms)
    avg_jitter = float(np.mean(temporal_jitter_hist))
    blurry_pct = (sum(1 for s in sharpness_list if s < MIN_SHARPNESS) / n) * 100
    frozen_pct = (frozen_count / n) * 100
    ir_pct = (ir_mode_count / n) * 100
    
    result["metrics"].update({
        "avg_brightness": round(avg_b, 1),
        "avg_contrast": round(avg_c, 1),
        "avg_sharpness": round(avg_s, 1),
        "avg_dynamic_range": round(avg_dr, 1),
        "blurry_frames_pct": round(blurry_pct, 1),
        "frozen_frames_pct": round(frozen_pct, 1),
        "ir_mode_pct": round(ir_pct, 1),
        "avg_bright_blobs_per_frame": round(avg_sb, 1),
        "max_bright_blobs": max_sb,
        "avg_edge_lines_per_frame": round(avg_lines, 1),
        "avg_text_regions_per_frame": round(avg_text, 1),
        "avg_foreground_pct": round(avg_fg, 1),
        "avg_edge_density_pct": round(avg_ed, 1),
        "scene_diversity_score": round(scene_div, 3),
        "avg_temporal_jitter": round(avg_jitter, 2),
        "samples_analyzed": n
    })
    
    # ==== CHECK 6: IR Mode ====
    is_ir = ir_pct > 30.0
    if is_ir:
        result["checks"]["ir_mode"] = "FAIL"
        result["issues"].append(f"[CHECK 6/Motive] CAMERA IN IR TRACKING MODE ({ir_pct:.0f}% of samples). Fix in Motive: right-click camera view > Camera Settings > Video Type = 'MJPEG Grayscale' or 'Reference'.")
    else:
        result["checks"]["ir_mode"] = "PASS"
    
    # ==== CHECK 5: Ghost Overlay ====
    strong_ghost = avg_sb > 30 and avg_lines > 40
    ghost_suspected = (avg_sb > 15 or max_sb > 25) and avg_lines > 20
    if strong_ghost:
        result["checks"]["ghost_overlay"] = "FAIL"
        result["issues"].append(f"[CHECK 5/NVIDIA GR00T] STRONG GHOST RIGID BODY OVERLAY: avg {avg_sb:.0f} bright blobs + {avg_lines:.0f} edge lines per frame. Fix in Motive: View > Perspective View pane > Visual Aids > DISABLE all of: Rigid Body Shape, Bones, Skeleton, Marker Labels, Axes. Then re-export.")
    elif ghost_suspected:
        result["checks"]["ghost_overlay"] = "WARN"
        result["warnings"].append(f"[CHECK 5/NVIDIA GR00T] Possible ghost overlay: {avg_sb:.0f} blobs, {avg_lines:.0f} lines/frame. Inspect keyframes visually.")
    else:
        result["checks"]["ghost_overlay"] = "PASS"
    
    # ==== CHECK 7: Dynamic Range / HDR ====
    if avg_dr < 80:
        result["checks"]["dynamic_range"] = "FAIL"
        result["issues"].append(f"[CHECK 7/Tesla] Poor dynamic range ({avg_dr:.0f}). Scene lacks HDR. Increase lab lighting variation.")
    elif avg_dr < 120:
        result["checks"]["dynamic_range"] = "WARN"
    else:
        result["checks"]["dynamic_range"] = "PASS"
    
    # ==== CHECK 8: Motion Blur (Figure AI) ====
    if blurry_pct > MAX_MOTION_BLUR_PCT:
        result["checks"]["motion_blur"] = "FAIL"
        result["issues"].append(f"[CHECK 8/Figure AI] Excessive motion blur ({blurry_pct:.1f}% of frames blurry). Max allowed: {MAX_MOTION_BLUR_PCT}%. Slow down movements or increase shutter speed.")
    elif blurry_pct > 8:
        result["checks"]["motion_blur"] = "WARN"
        result["warnings"].append(f"[CHECK 8/Figure AI] Notable motion blur: {blurry_pct:.1f}% frames.")
    else:
        result["checks"]["motion_blur"] = "PASS"
    
    # ==== CHECK 9: Focus (Berkeley DROID) ====
    if avg_s < MIN_SHARPNESS:
        result["checks"]["focus"] = "FAIL"
        result["issues"].append(f"[CHECK 9/Berkeley DROID] Poor focus (sharpness={avg_s:.1f}). Camera may be out of focus.")
    else:
        result["checks"]["focus"] = "PASS"
    
    # ==== CHECK 10: Scene Diversity (Meta Ego4D) ====
    if scene_div < MIN_SCENE_DIVERSITY:
        result["checks"]["scene_diversity"] = "WARN"
        result["warnings"].append(f"[CHECK 10/Meta Ego4D] Low scene diversity ({scene_div:.3f}). Video is too static. VLA needs varied action/motion. Move around more, vary robot paths.")
    else:
        result["checks"]["scene_diversity"] = "PASS"
    
    # ==== CHECK 11: Data Leakage (NVIDIA GR00T) ====
    if avg_text > MAX_OVERLAY_TEXT_REGIONS * 5:
        result["checks"]["data_leakage"] = "FAIL"
        result["issues"].append(f"[CHECK 11/NVIDIA GR00T] Suspected text/UI overlay ({avg_text:.0f} text-like regions per frame). Timestamps, watermarks or UI in frame will leak into VLA training.")
    elif avg_text > MAX_OVERLAY_TEXT_REGIONS:
        result["checks"]["data_leakage"] = "WARN"
    else:
        result["checks"]["data_leakage"] = "PASS"
    
    # ==== CHECK 12: Occlusion (Stanford ALOHA) ====
    if avg_fg > MAX_OCCLUSION_PCT:
        result["checks"]["occlusion"] = "WARN"
        result["warnings"].append(f"[CHECK 12/Stanford ALOHA] High foreground coverage ({avg_fg:.0f}%). Objects may be blocking too much view.")
    else:
        result["checks"]["occlusion"] = "PASS"
    
    # ==== CHECK 13: Temporal Consistency ====
    if avg_jitter > 50:
        result["checks"]["temporal_consistency"] = "WARN"
        result["warnings"].append(f"[CHECK 13/Berkeley] High temporal jitter ({avg_jitter:.1f}). Camera may be shaking.")
    else:
        result["checks"]["temporal_consistency"] = "PASS"
    
    # ==== CHECK 14: Foreground/Background Balance ====
    if avg_ed < 3.0:
        result["checks"]["scene_richness"] = "WARN"
        result["warnings"].append(f"[CHECK 14/1X] Scene lacks visual richness (edge density={avg_ed:.1f}%). VLA needs varied visual features.")
    else:
        result["checks"]["scene_richness"] = "PASS"
    
    # Frozen frames
    if frozen_pct > MAX_FROZEN_FRAMES_PCT:
        result["warnings"].append(f"[Frame Health] {frozen_pct:.1f}% frozen frames detected.")
    
    # Brightness
    if avg_b < MIN_BRIGHTNESS and not is_ir:
        result["issues"].append(f"[Exposure] Video too dark: {avg_b:.1f}/255.")
    elif avg_b > MAX_BRIGHTNESS:
        result["warnings"].append(f"[Exposure] Video overexposed: {avg_b:.1f}/255.")
    
    # ==== CHECK 15: FINAL VLA SCORE (weighted) ====
    weights = {
        "frame_sync": 15, "ghost_overlay": 15, "ir_mode": 15,
        "resolution": 8, "fps": 8, "codec_bitrate": 5,
        "dynamic_range": 6, "motion_blur": 8, "focus": 8,
        "scene_diversity": 4, "data_leakage": 4, "occlusion": 2,
        "temporal_consistency": 1, "scene_richness": 1
    }
    score = 0
    max_score = 0
    for check, weight in weights.items():
        status = result["checks"].get(check, "SKIP")
        max_score += weight
        if status == "PASS":
            score += weight
        elif status == "WARN":
            score += weight * 0.5
        elif status == "SKIP":
            max_score -= weight
    
    vla_score = int((score / max_score) * 100) if max_score > 0 else 0
    result["vla_score"] = vla_score
    
    # Final verdict
    critical_fails = ["frame_sync", "ghost_overlay", "ir_mode", "resolution"]
    has_critical = any(result["checks"].get(c) == "FAIL" for c in critical_fails)
    
    if has_critical or vla_score < 40:
        result["verdict"] = "NOT_SUITABLE_FOR_VLA"
    elif vla_score < 60:
        result["verdict"] = "POOR_QUALITY"
    elif vla_score < 80:
        result["verdict"] = "USABLE_WITH_WARNINGS"
    elif vla_score < 92:
        result["verdict"] = "GOOD"
    else:
        result["verdict"] = "EXCELLENT"
    
    return result

def write_report(sessions_analyzed, out_txt, out_dir):
    lines = []
    lines.append("=" * 80)
    lines.append(f" VLA VIDEO QUALITY AUDIT REPORT v{VERSION} - INDUSTRY GRADE")
    lines.append("=" * 80)
    lines.append(f"Generated (UTC): {utc_now_iso()}")
    lines.append(f"Sessions inspected: {len(sessions_analyzed)}")
    lines.append(f"Keyframes folder: {out_dir}")
    lines.append("")
    lines.append("STANDARDS APPLIED:")
    lines.append("  - Google DeepMind (RT-2, RT-X, Open X-Embodiment)")
    lines.append("  - Physical Intelligence (pi-0, pi-0.5)")
    lines.append("  - Tesla Optimus, Figure AI, 1X Technologies")
    lines.append("  - NVIDIA GR00T, UC Berkeley DROID, Stanford ALOHA")
    lines.append("  - Meta Ego4D, HuggingFace LeRobot")
    lines.append("")
    lines.append("VERDICT SCALE:")
    lines.append("  EXCELLENT (92-100)    = Ready for VLA training")
    lines.append("  GOOD (80-91)          = Ready with minor caveats")
    lines.append("  USABLE_WITH_WARNINGS  = Can use but not ideal (60-79)")
    lines.append("  POOR_QUALITY          = Fix issues before use (40-59)")
    lines.append("  NOT_SUITABLE_FOR_VLA  = Must re-record or fix Motive settings")
    lines.append("")
    lines.append("=" * 80)
    
    for sid, videos in sessions_analyzed.items():
        lines.append(f"\n### SESSION: {sid}")
        lines.append("=" * 80)
        for vresult in videos:
            lines.append(f"\n>>> VIDEO: {vresult['file']}")
            lines.append(f"    VERDICT   : {vresult['verdict']}")
            lines.append(f"    VLA SCORE : {vresult['vla_score']}/100")
            lines.append("")
            
            m = vresult['metrics']
            lines.append("    -- TECHNICAL METRICS --")
            lines.append(f"    Resolution : {m.get('width')}x{m.get('height')} | FPS: {m.get('fps')} | Codec: {m.get('codec')}")
            lines.append(f"    Frames     : {m.get('total_frames')} | Duration: {m.get('duration_s')}s | Bitrate: {m.get('bitrate_mbps')} Mbps")
            if 'csv_frames' in m:
                lines.append(f"    CSV sync   : video={m.get('total_frames')} vs csv={m.get('csv_frames')} (drift={m.get('sync_diff_frames')})")
            lines.append("")
            lines.append("    -- VISUAL QUALITY --")
            lines.append(f"    Brightness      : {m.get('avg_brightness')}/255")
            lines.append(f"    Contrast        : {m.get('avg_contrast')}")
            lines.append(f"    Sharpness       : {m.get('avg_sharpness')}")
            lines.append(f"    Dynamic Range   : {m.get('avg_dynamic_range')}")
            lines.append(f"    Blurry frames   : {m.get('blurry_frames_pct')}%")
            lines.append(f"    Frozen frames   : {m.get('frozen_frames_pct')}%")
            lines.append(f"    IR-mode samples : {m.get('ir_mode_pct')}%")
            lines.append("")
            lines.append("    -- VLA-SPECIFIC FEATURES --")
            lines.append(f"    Bright blobs/frame  : avg={m.get('avg_bright_blobs_per_frame')} max={m.get('max_bright_blobs')} (ghost markers?)")
            lines.append(f"    Edge lines/frame    : {m.get('avg_edge_lines_per_frame')} (skeleton overlays?)")
            lines.append(f"    Text regions/frame  : {m.get('avg_text_regions_per_frame')} (data leakage?)")
            lines.append(f"    Foreground coverage : {m.get('avg_foreground_pct')}%")
            lines.append(f"    Scene diversity     : {m.get('scene_diversity_score')} (Meta Ego4D score)")
            lines.append(f"    Temporal jitter     : {m.get('avg_temporal_jitter')}")
            lines.append("")
            
            lines.append("    -- 15-POINT CHECK RESULTS --")
            check_names = {
                "frame_sync": "1. Frame Sync (Google RT-X)",
                "fps": "2. FPS Standard (Berkeley DROID)",
                "codec_bitrate": "3. Codec/Bitrate (LeRobot)",
                "resolution": "4. Resolution (Physical Intelligence)",
                "ghost_overlay": "5. Ghost Overlay (NVIDIA GR00T)",
                "ir_mode": "6. IR Mode Check (Motive)",
                "dynamic_range": "7. Dynamic Range (Tesla)",
                "motion_blur": "8. Motion Blur (Figure AI)",
                "focus": "9. Focus Quality (Berkeley)",
                "scene_diversity": "10. Scene Diversity (Meta Ego4D)",
                "data_leakage": "11. Data Leakage (NVIDIA GR00T)",
                "occlusion": "12. Occlusion Ratio (Stanford ALOHA)",
                "temporal_consistency": "13. Temporal Consistency (Berkeley)",
                "scene_richness": "14. Scene Richness (1X)"
            }
            for key, label in check_names.items():
                status = vresult['checks'].get(key, "SKIP")
                icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(status, "[?]")
                lines.append(f"      {icon} {label}")
            
            if vresult['issues']:
                lines.append("")
                lines.append("    -- CRITICAL ISSUES (must fix) --")
                for iss in vresult['issues']:
                    lines.append(f"      [X] {iss}")
            if vresult['warnings']:
                lines.append("")
                lines.append("    -- WARNINGS (should review) --")
                for w in vresult['warnings']:
                    lines.append(f"      [!] {w}")
            if vresult['info']:
                lines.append("")
                lines.append("    -- INFO --")
                for i in vresult['info']:
                    lines.append(f"      [i] {i}")
    
    lines.append("\n" + "=" * 80)
    lines.append(" AI ACTION ITEMS")
    lines.append("=" * 80)
    lines.append(" 1. Read the VERDICT and VLA SCORE for each video above.")
    lines.append(" 2. For any FAIL check, follow the fix instructions in the issue text.")
    lines.append(" 3. If Ghost Overlay = FAIL, adjust Motive Visual Aids and re-export.")
    lines.append(" 4. If IR Mode = FAIL, switch Motive camera to Reference/Grayscale mode.")
    lines.append(" 5. If Frame Sync = FAIL, check Motive export settings for frame count.")
    lines.append(" 6. Visually inspect keyframes in the folder above to confirm findings.")
    lines.append("=" * 80)
    lines.append(f" End of report. Paste this entire file to your AI.")
    lines.append("=" * 80)
    
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    root = find_project_root()
    motive_dir = os.path.join(root, "motive sessions")
    reports_dir = os.path.join(root, "reports")
    out_dir = os.path.join(reports_dir, f"video_qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = out_dir
    report_txt = os.path.join(desktop, "VIDEO_QA_REPORT_FOR_AI.txt")
    
    print("\n" + "=" * 72)
    print(f" VIDEO QA AGENT v{VERSION} - INDUSTRY GRADE (15-point audit)")
    print("=" * 72)
    print(f" Standards: Google RT-X, Physical Intelligence, Tesla, Figure,")
    print(f"            NVIDIA GR00T, Berkeley DROID, Stanford ALOHA, Meta")
    print("=" * 72)
    print(f"Project root: {root}")
    print(f"Scanning: {motive_dir}\n")
    
    sessions = list_video_sessions(motive_dir)
    if not sessions:
        print("[ERROR] No video sessions found.")
        input("\nPress Enter to exit...")
        return
    
    session_ids = sorted(sessions.keys())
    print(f"Found {len(session_ids)} session(s):\n")
    for i, sid in enumerate(session_ids, 1):
        info = sessions[sid]
        cam_count = len(info["cameras"])
        csv_ok = "CSV OK" if info["csv"] else "NO CSV"
        print(f"  [{i}] {sid}  ({cam_count} cams, {csv_ok})")
        for cam, fn in info["cameras"]:
            size_mb = os.path.getsize(os.path.join(motive_dir, fn)) / (1024 * 1024)
            print(f"       - {cam}: {size_mb:.1f} MB")
    
    print("\nOptions:")
    print("  Numbers separated by comma (e.g. 1,2)")
    print("  'all' to check everything")
    print("  'q' to quit")
    choice = input("\nYour choice: ").strip().lower()
    
    if choice == "q":
        return
    
    if choice == "all":
        selected = session_ids
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [session_ids[i] for i in indices if 0 <= i < len(session_ids)]
        except Exception:
            print("[ERROR] Invalid input.")
            input("\nPress Enter to exit...")
            return
    
    if not selected:
        print("[ERROR] No valid session selected.")
        input("\nPress Enter to exit...")
        return
    
    print(f"\nAnalyzing {len(selected)} session(s) with 15-point audit...\n")
    all_results = {}
    for sid in selected:
        info = sessions[sid]
        csv_frames = count_csv_frames(info["csv"])
        print(f"\n>>> Session: {sid} (CSV frames: {csv_frames})")
        session_results = []
        for cam, fn in info["cameras"]:
            vpath = os.path.join(motive_dir, fn)
            print(f"    Analyzing {cam} (deep 15-point scan)...", end=" ", flush=True)
            r = analyze_video(vpath, csv_frames, out_dir)
            session_results.append(r)
            print(f"[{r['verdict']}] score={r['vla_score']}/100")
        all_results[sid] = session_results
    
    write_report(all_results, report_txt, out_dir)
    
    print("\n" + "=" * 72)
    print(" AUDIT COMPLETE")
    print("=" * 72)
    print(f"\n[REPORT] -> {report_txt}")
    print(f"[FRAMES] -> {out_dir}")
    print("\nNext steps:")
    print("  1. Open VIDEO_QA_REPORT_FOR_AI.txt from your Desktop")
    print("  2. Copy the ENTIRE content and paste it to your AI")
    print("  3. Also open the keyframes folder and inspect the images")
    print("=" * 72)
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
