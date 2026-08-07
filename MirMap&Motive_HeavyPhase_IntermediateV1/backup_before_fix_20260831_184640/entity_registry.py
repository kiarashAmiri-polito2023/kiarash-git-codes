#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entity_registry.py - Master Entity Registry (v1.0)

Groups multiple markers/clusters into ONE real-world entity.
Based on Google RT-X, Physical Intelligence, NVIDIA GR00T architecture.

Example:
  entity "person_kiarash" contains:
    - motive markers: [kia hat 002, kiarash_leftwrist, kiarash_RightWrist]
    - slam clusters : [cluster_289, cluster_310]
    - video bboxes  : [obj_1_cam_1, obj_1_cam_4]
"""
import os, sys, pickle, uuid, json, math
from datetime import datetime, timezone

def utc_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def safe_pickle_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


class EntityRegistry:
    """
    Master registry: real-world entities, not individual markers.
    """
    def __init__(self, root_path):
        self.root_path = root_path
        self.pk_dir = os.path.join(root_path, "persistent_knowledge")
        os.makedirs(self.pk_dir, exist_ok=True)
        self.path = os.path.join(self.pk_dir, "entity_registry.pkl")
        self.entities = {}  # entity_id -> entity dict
        self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    data = pickle.load(f)
                self.entities = data.get("entities", {})
            except Exception:
                self.entities = {}
    
    def save(self):
        data = {
            "schema_version": "entity_registry_v1",
            "last_updated_utc": utc_now_iso(),
            "total_entities": len(self.entities),
            "entities": self.entities
        }
        safe_pickle_dump(data, self.path)
        # Also save readable summary
        txt = self.path.replace(".pkl", "_summary.txt")
        with open(txt, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n ENTITY REGISTRY\n" + "=" * 60 + "\n")
            f.write(f"Total: {len(self.entities)}\n\n")
            for eid, e in self.entities.items():
                confirmed = "[CONFIRMED]" if e.get("user_confirmed") else "[PENDING]"
                f.write(f"{confirmed} {eid}\n")
                f.write(f"  Name  : {e.get('canonical_name', '?')}\n")
                f.write(f"  Type  : {e.get('entity_type', '?')}\n")
                f.write(f"  Class : {e.get('classification', '?')}\n")
                f.write(f"  Dynamic: {e.get('is_dynamic', '?')}\n")
                f.write(f"  Motive markers: {e.get('motive_markers', [])}\n")
                f.write(f"  SLAM clusters : {e.get('slam_clusters', [])}\n")
                f.write(f"  Video bboxes  : {len(e.get('video_bboxes', []))}\n")
                f.write(f"  Sessions      : {e.get('sessions_seen', [])}\n\n")
    
    def create_entity(self, canonical_name, entity_type="unknown", motive_markers=None,
                      classification=None, is_dynamic=False, confidence=0.5):
        eid = f"ENT-{uuid.uuid4().hex[:10].upper()}"
        self.entities[eid] = {
            "entity_id": eid,
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "classification": classification or entity_type,
            "is_dynamic": is_dynamic,
            "confidence": confidence,
            "aliases": [canonical_name],
            "motive_markers": list(motive_markers or []),
            "slam_clusters": [],
            "video_bboxes": [],
            "sessions_seen": [],
            "first_seen_utc": utc_now_iso(),
            "last_seen_utc": utc_now_iso(),
            "total_observations": 0,
            "user_confirmed": False,
            "creation_source": "auto",
            "notes": ""
        }
        return eid
    
    def get_entity_by_motive_marker(self, marker_name):
        for eid, e in self.entities.items():
            if marker_name in e.get("motive_markers", []):
                return eid, e
        return None, None
    
    def get_entity_by_slam_cluster(self, cluster_id):
        for eid, e in self.entities.items():
            if cluster_id in e.get("slam_clusters", []):
                return eid, e
        return None, None
    
    def link_slam_cluster(self, entity_id, cluster_id, session_name, confidence=0.7):
        if entity_id not in self.entities:
            return False
        e = self.entities[entity_id]
        if cluster_id not in e["slam_clusters"]:
            e["slam_clusters"].append(cluster_id)
        if session_name not in e["sessions_seen"]:
            e["sessions_seen"].append(session_name)
        e["last_seen_utc"] = utc_now_iso()
        return True
    
    def link_video_bbox(self, entity_id, bbox_info):
        if entity_id not in self.entities:
            return False
        self.entities[entity_id]["video_bboxes"].append(bbox_info)
        return True
    
    def confirm_entity(self, entity_id, confirmed_by="human"):
        if entity_id in self.entities:
            self.entities[entity_id]["user_confirmed"] = True
            self.entities[entity_id]["confirmed_by"] = confirmed_by
            self.entities[entity_id]["confirmed_at_utc"] = utc_now_iso()
    
    def suggest_grouping(self, motive_markers, deep_memory):
        """
        Suggest which markers belong to same entity.
        Heuristic: markers with similar name prefix + similar movement patterns.
        """
        suggestions = []
        # Group by name prefix
        groups = {}
        for m in motive_markers:
            # Extract prefix (e.g. "kiarash" from "kiarash_leftwrist")
            prefix = m.split("_")[0].split(" ")[0].lower()
            if len(prefix) < 3:
                prefix = m.lower()
            groups.setdefault(prefix, []).append(m)
        
        # Also check if speeds are similar (same person's markers move together)
        for prefix, markers in groups.items():
            if len(markers) > 1:
                # Check speeds from deep memory
                speeds = []
                for m in markers:
                    track = deep_memory.get("object_tracks", {}).get(m, {})
                    speeds.append(track.get("mean_speed_mps", 0))
                if speeds and max(speeds) - min(speeds) < 0.5:
                    suggestions.append({
                        "suggested_entity_name": f"person_{prefix}",
                        "markers": markers,
                        "reason": f"Same name prefix '{prefix}' + similar speeds {[round(s,2) for s in speeds]}",
                        "confidence": 0.85
                    })
        
        # Ungrouped -> single entity each
        grouped_markers = set()
        for s in suggestions:
            grouped_markers.update(s["markers"])
        for m in motive_markers:
            if m not in grouped_markers:
                suggestions.append({
                    "suggested_entity_name": m,
                    "markers": [m],
                    "reason": "Standalone marker (no group found)",
                    "confidence": 0.5
                })
        
        return suggestions


def rebuild_from_deep_memory(root_path, auto_confirm=False):
    """
    Rebuild entity registry from deep memory using intelligent grouping.
    """
    dm_path = os.path.join(root_path, "persistent_knowledge", "deep_learning_memory.pkl")
    if not os.path.exists(dm_path):
        print("[EntityRegistry] No deep memory found.")
        return None
    
    with open(dm_path, "rb") as f:
        deep_memory = pickle.load(f)
    
    registry = EntityRegistry(root_path)
    # Reset entities for rebuild
    old_count = len(registry.entities)
    registry.entities = {}
    
    all_markers = list(deep_memory.get("object_tracks", {}).keys())
    print(f"[EntityRegistry] Found {len(all_markers)} markers in deep memory")
    
    suggestions = registry.suggest_grouping(all_markers, deep_memory)
    print(f"[EntityRegistry] Generated {len(suggestions)} entity groupings\n")
    
    HUMAN_KEYWORDS = ("hat", "wrist", "hand", "head", "human", "person", "kiarash")
    ROBOT_KEYWORDS = ("mir", "robot")
    STATIC_KEYWORDS = ("station", "table", "shelf", "wall", "box")
    
    for s in suggestions:
        markers = s["markers"]
        name = s["suggested_entity_name"]
        nl = name.lower()
        
        # Auto-classify
        if any(k in nl for k in HUMAN_KEYWORDS):
            etype = "human"
            is_dyn = True
        elif any(k in nl for k in ROBOT_KEYWORDS):
            etype = "robot"
            is_dyn = True
        elif any(k in nl for k in STATIC_KEYWORDS):
            etype = "static_furniture"
            is_dyn = False
        else:
            # Check dynamics from deep memory
            speeds = [deep_memory["object_tracks"].get(m, {}).get("mean_speed_mps", 0) for m in markers]
            avg_speed = sum(speeds) / max(len(speeds), 1)
            if avg_speed > 0.1:
                etype = "dynamic_obstacle"
                is_dyn = True
            else:
                etype = "unknown"
                is_dyn = False
        
        eid = registry.create_entity(
            canonical_name=name,
            entity_type=etype,
            motive_markers=markers,
            classification=etype,
            is_dynamic=is_dyn,
            confidence=s["confidence"]
        )
        
        # Aggregate stats from all markers in group
        total_obs = 0
        sessions = set()
        for m in markers:
            t = deep_memory["object_tracks"].get(m, {})
            total_obs += t.get("total_observations", 0)
            sessions.update(t.get("sessions_list", []))
        registry.entities[eid]["total_observations"] = total_obs
        registry.entities[eid]["sessions_seen"] = sorted(sessions)
        
        if auto_confirm:
            registry.confirm_entity(eid, confirmed_by="auto")
        
        confirmed = " [AUTO-CONFIRMED]" if auto_confirm else " [PENDING]"
        print(f"  {eid}: {name} ({etype}, dynamic={is_dyn}){confirmed}")
        print(f"    markers: {markers}")
        print(f"    reason: {s['reason']}")
        print()
    
    registry.save()
    print(f"[EntityRegistry] Saved {len(registry.entities)} entities (was {old_count})")
    return registry


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--auto-confirm", action="store_true")
    p.add_argument("--root", default=None)
    args = p.parse_args()
    
    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if args.rebuild:
        rebuild_from_deep_memory(root, auto_confirm=args.auto_confirm)
    else:
        r = EntityRegistry(root)
        print(f"Current entities: {len(r.entities)}")
        for eid, e in r.entities.items():
            print(f"  {eid}: {e.get('canonical_name')} ({e.get('entity_type')})")
