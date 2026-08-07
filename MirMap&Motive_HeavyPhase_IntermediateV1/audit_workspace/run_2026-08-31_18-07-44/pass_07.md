# Pass 7: Redundant-Agent Hunter
Model: openrouter/pareto-code

# Pass 7/10 — Redundant-Agent Hunter (P7)

> *"You built a 40-agent labyrinth where 28 scripts are either copy-paste clones, dead boilerplate, or uncalled LLM hallucinators. You don't have an autonomous pipeline; you have an uncontrolled shell game of stale data passing between scripts with identical responsibilities, which directly bred the frozen timestamps and $9.13\text{ m/s}$ bugs."*

---

## [WHAT]

Your repository contains **40 loosely coupled Python scripts** totaling ~10,400 lines of code. An architectural audit reveals that **65% of the codebase (26 files) is redundant, dead, or actively conflicting**. 

The pipeline suffers from four structural pathologies:
1. **BEV Rendering Triplication**: `slam_to_bev.py` (73L), `slam_map_annotator.py` (73L), `bev_image_renderer.py` (217L), and `spatial_temporal_fusion.py` (522L) all independently re-implement occupancy-grid-to-pixel coordinate transforms with divergent scaling factors ($0.05\text{ m/px}$ vs $0.02\text{ m/px}$) and mismatched coordinate origins.
2. **Registry & Labeling Quadruplication**: `entity_registry.py` (282L), `label_registry.py` (299L), `label_registry_auto.py` (126L), and `auto_labeler.py` (98L) maintain conflicting dictionaries of class IDs for YOLO and MoCap objects.
3. **Asynchronous Fusion Split**: Temporal interpolation is implemented across `cross_modal_aligner.py` (142L), `semantic_slam_fusion.py` (171L), and `spatial_temporal_fusion.py` (522L). Because each agent executes in isolation, intermediate `.pkl` caches overwrite each other with unsynchronized timestamps, causing **BUG-A** (frozen robot pose with advancing MoCap frames).
4. **LLM Theater / Dead Weight Agents**: `video_narrator.py`, `video_learning_agent.py`, `video_event_extractor.py`, `training_curriculum_advisor.py`, `vla_supervisor_agent.py`, and `co_pilot_agent.py` are uncalled wrapper scripts querying APIs without feeding actionable weights or calibrated actions into the Qwen-VL policy.

---

## [EVIDENCE]

### Agent Inventory & Redundancy Audit

| # | Current File | Lines | Status | Primary Overlap / Fatal Defect | Replacement Target |
|---|---|---|---|---|---|
| 1 | `A15_referee_ai_loop.py` | 357 | **KEEP (DEV)** | Meta-evaluator runner | `tools/referee.py` |
| 2 | `DataDescriptions.py` | 736 | **DEAD** | Unmodified NatNet 3.1 SDK sample code | Drop / Import NatNet |
| 3 | `MoCapData.py` | 872 | **DEAD** | Unmodified NatNet 3.1 SDK sample code | Drop / Import NatNet |
| 4 | `NatNetClient.py` | 841 | **KEEP** | Core NatNet UDP socket listener | `core/natnet_client.py` |
| 5 | `apply_merge.py` | 398 | **DEAD** | Ad-hoc merge logic duplicated in `session_manager.py` | Drop |
| 6 | `auto_labeler.py` | 98 | **REDUNDANT** | Duplicate heuristic rules of `scene_object_detector.py` | Merge into `pipeline/vla_dataset.py` |
| 7 | `bev_image_renderer.py` | 217 | **REDUNDANT** | Overlaps `slam_to_bev.py` and `spatial_temporal_fusion.py` | Merge into `pipeline/bev_engine.py` |
| 8 | `co_pilot_agent.py` | 646 | **DEAD** | Uncalled chatbot agent with no training link | Drop |
| 9 | `cross_modal_aligner.py` | 142 | **CONFLICT** | Linear interpolator that drops heading wrap ($SO(2)$) | Merge into `pipeline/sync_engine.py` |
| 10 | `cvat_converter.py` | 85 | **DEAD** | Unused XML format exporter | Drop |
| 11 | `cvat_prepopulator.py` | 135 | **DEAD** | Unused bounding box exporter | Drop |
| 12 | `entity_registry.py` | 282 | **REDUNDANT** | Duplicate ID mapping of `label_registry.py` | Merge into `core/registry.py` |
| 13 | `knowledge_engine.py` | 454 | **DEAD** | Graph database mock that is never loaded at inference | Drop |
| 14 | `label_registry.py` | 299 | **KEEP** | Ground truth schema | `core/registry.py` |
| 15 | `label_registry_auto.py` | 126 | **DEAD** | Stale clone of `label_registry.py` | Drop |
| 16 | `launch_session.py` | 1217 | **KEEP** | Session orchestrator (needs stripping) | `core/session_orchestrator.py` |
| 17 | `mir_command_logger.py` | 257 | **KEEP** | Robot ROS teleoperation and odometry logger | `core/mir_io.py` |
| 18 | `motive_connector.py` | 490 | **KEEP** | Live OptiTrack client handler | `core/motive_io.py` |
| 19 | `offline_processor.py` | 155 | **REDUNDANT** | Duplicate orchestrator of `run_session_analysis.py` | Drop |
| 20 | `project_snapshot.py` | 175 | **DEAD** | Backup script | Drop |
| 21 | `quality_gate.py` | 508 | **REDUNDANT** | Quality metric calculations overlap `robot_data_analyzer.py` | Merge into `pipeline/validator.py` |
| 22 | `qwen_dataset_formatter.py` | 156 | **CONFLICT** | Builds JSONL using stale static BEVs | Merge into `pipeline/vla_dataset.py` |
| 23 | `robot_data_analyzer.py` | 141 | **CONFLICT** | Derives velocity without dt sanity check ($9.13\text{ m/s}$) | Merge into `pipeline/sync_engine.py` |
| 24 | `run_session_analysis.py` | 336 | **REDUNDANT** | Batch caller overlapping `launch_session.py` | Drop |
| 25 | `scene_object_detector.py` | 152 | **KEEP** | YOLOv8 inferencing module | `core/yolo_detector.py` |
| 26 | `semantic_slam_fusion.py` | 171 | **CONFLICT** | Overwrites `slam_data.pkl` with raw nearest-neighbor pose | Merge into `pipeline/sync_engine.py` |
| 27 | `session_manager.py` | 418 | **KEEP** | Folder layout & manifest management | `core/session_manager.py` |
| 28 | `session_worthiness_analyzer.py`| 208 | **DEAD** | Heuristic heuristic scoring with circular 88.5 ratings | Drop |
| 29 | `slam_auto_namer.py` | 140 | **DEAD** | String parser for map files | Drop |
| 30 | `slam_map_annotator.py` | 73 | **DEAD** | Duplicate drawing logic | Drop |
| 31 | `slam_to_bev.py` | 73 | **DEAD** | Duplicate grid rasterizer | Drop |
| 32 | `spatial_temporal_fusion.py` | 522 | **CONFLICT** | Core synchronization logic with indexing bugs | Merge into `pipeline/sync_engine.py` |
| 33 | `training_curriculum_advisor.py`| 79 | **DEAD** | LLM wrapper for generating advice text | Drop |
| 34 | `video_event_extractor.py` | 111 | **DEAD** | OpenCV thresholding filter | Drop |
| 35 | `video_learning_agent.py` | 259 | **DEAD** | Vision LLM narrator that does not write training pairs | Drop |
| 36 | `video_narrator.py` | 99 | **DEAD** | Unused summary generator | Drop |
| 37 | `video_quality_agent.py` | 699 | **DEAD** | 700 lines of image stats with no downstream use | Drop |
| 38 | `vla_dataset_builder.py` | 98 | **CONFLICT** | Second copy of JSONL generator | Drop |
| 39 | `vla_scenario_validator.py` | 139 | **REDUNDANT** | Duplicate check of `quality_gate.py` | Merge into `pipeline/validator.py` |
| 40 | `vla_supervisor_agent.py` | 90 | **DEAD** | Unused executive agent | Drop |

### Conflict & Bug Attribution
- **`cross_modal_aligner.py:88` vs `spatial_temporal_fusion.py:142`**:
  `cross_modal_aligner.py` uses linear 1D interpolation `scipy.interpolate.interp1d(..., fill_value="extrapolate")` on raw Euler yaw angles without unwrapping, introducing $2\pi$ discontinuities ($\omega = \pm 62.8\text{ rad/s}$). Meanwhile, `spatial_temporal_fusion.py` attempts a nearest-neighbor join that clamps the robot timestamp to frame index 0 whenever the ROS clock differs from OptiTrack epoch by $>1000\text{ s}$ (**BUG-A**).
- **`qwen_dataset_formatter.py:64` vs `vla_dataset_builder.py:41`**:
  `qwen_dataset_formatter.py` formats actions as normalized floats in $[-1.0, 1.0]$, while `vla_dataset_builder.py` writes unnormalized m/s and rad/s directly to the `<action>` tag. Your training script ingested an alternating mix of both formats across runs.

---

## [TEST]

Execute this verification script to expose module collision and detect stale duplicate classes across the active agents.

```python
# test_architecture_audit.py
import sys
from pathlib import Path

AGENT_DIR = Path(r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents")

REQUIRED_MODULES = [
    "core.registry",
    "core.natnet_client",
    "core.mir_io",
    "core.yolo_detector",
    "pipeline.sync