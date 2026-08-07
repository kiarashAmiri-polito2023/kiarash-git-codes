# Agent Architecture — 5x Precision Dossier (Step 46)
# Generated: 2026-09-24 | Methodology: AST-level function extraction + full source read + data flow tracing
# LAW1 Compliance: Read-only diagnostic phase

## MASTER DATA FLOW PIPELINE
```
Motive Session → [session_manager] → [motive_connector] → [NatNetClient/MoCapData/DataDescriptions]
    ↓
[quality_gate] ← [video_quality_agent] ← [session_worthiness_analyzer]
    ↓
[robot_data_analyzer] → [slam_to_bev] → [bev_image_renderer]
    ↓
[cross_modal_aligner] → [semantic_slam_fusion] → [spatial_temporal_fusion]
    ↓
[video_event_extractor] → [scene_object_detector] → [auto_labeler]
    ↓
[vla_dataset_builder] → [qwen_dataset_formatter] → [cvat_converter]
    ↓
[vla_supervisor_agent] → [vla_scenario_validator] → [training_curriculum_advisor]
```

## CRITICAL AGENTS (Direct Thesis Impact)

### 1. launch_session.py — ORCHESTRATOR
**Role:** Main entry point, session launcher, pipeline coordinator
**Functions (37):** `launch_session()`, `configure_logging()`, `validate_environment()`
**Inputs:** Session config YAML/JSON, Motive session path
**Outputs:** Orchestrated agent execution results, consolidated reports
**Thesis Contribution:** G1-G55 coordination, ensures all agents execute in correct order

### 2. motive_connector.py — MOTIVE BRIDGE (26 funcs)
**Role:** Connects to Motive system, extracts video/motion capture data
**Functions:** `connect_to_motive()`, `extract_session_data()`, `get_video_path()`
**Inputs:** Motive session directory, connection parameters
**Outputs:** Raw motion capture streams, video file paths, session metadata
**Thesis Contribution:** G1 (dataset quality) — primary data acquisition

### 3. NatNetClient.py — OPTITRACK RECEIVER (49 funcs)
**Role:** Real-time OptiTrack/NatNet protocol client for live pose streaming
**Functions:** `NatNetClient.connect()`, `receive_frame()`, `parse_rigid_body()`
**Inputs:** Network socket, OptiTrack broadcast
**Outputs:** Rigid body transforms [x,y,z,qw,qx,qy,qz], timestamps
**Thesis Contribution:** G1 real-time pose acquisition for SLAM fusion

### 4. MoCapData.py — MOCAP DATA MODEL (113 funcs)
**Role:** Data structures, transformations, coordinate systems for motion capture
**Functions:** `RigidBodyPose`, `TransformChain`, `CoordinateFrame`
**Inputs:** Raw NatNet packets
**Outputs:** Structured pose objects with metadata, calibrated transforms
**Thesis Contribution:** G2 (pipeline reliability) — data integrity layer

### 5. DataDescriptions.py — SCHEMA DEFINITIONS (74 funcs)
**Role:** Type definitions, validation schemas, protobuf-like structures
**Functions:** All data type classes and validators
**Inputs/Outputs:** Schema enforcement across all agents
**Thesis Contribution:** G2 reliability through strict typing

### 6. quality_gate.py — QUALITY ENFORCER (11 funcs)
**Role:** Validates data quality before processing, rejects bad sessions
**Functions:** `QualityGate.evaluate()`, `check_thresholds()`
**Inputs:** Raw session data from motive_connector
**Outputs:** Pass/fail verdict with quality scores per dimension
**Thesis Contribution:** G1 dataset quality gate

### 7. video_quality_agent.py — VIDEO ANALYST (14 funcs)
**Role:** Analyzes video frames for quality, motion blur, lighting conditions
**Functions:** `analyze_frame_quality()`, `detect_motion_blur()`
**Inputs:** Video file paths from motive_connector
**Outputs:** Quality metrics per frame/segment, recommendations
**Thesis Contribution:** G1 video data quality assessment

### 8. session_worthiness_analyzer.py — SESSION FILTER (4 funcs)
**Role:** Determines if a Motive session is worth processing for thesis goals
**Functions:** `analyze_session()`, `score_usefulness()`
**Inputs:** Session metadata, preliminary stats
**Outputs:** Worthiness score, inclusion/exclusion decision
**Thesis Contribution:** G1 data curation

### 9. robot_data_analyzer.py — KINEMATICS ENGINE (4 funcs)
**Role:** Computes velocities, accelerations from pose data; validates MiR100 physics
**Functions:** `compute_differential_kinematics_robust()`, `validate_mir100_commands()`
**Inputs:** Pose arrays [x,y,yaw], timestamps
**Outputs:** Velocity v[m/s], angular velocity w[rad/s], safety validation
**Thesis Contribution:** G2 pipeline reliability, BUG-C/D fixes (velocity 9.13→1.5 m/s)

### 10. slam_to_bev.py — SLAM→BEV CONVERTER (1 func)
**Role:** Converts SLAM map data to Bird's Eye View representation
**Functions:** `slam_to_bev()`
**Inputs:** SLAM point cloud/map, robot poses
**Outputs:** BEV grid/image suitable for VLA model input
**Thesis Contribution:** G49-G55 (VLA training data preparation)

### 11. bev_image_renderer.py — VISUALIZATION (4 funcs)
**Role:** Renders BEV images with overlays, annotations, robot trajectory
**Functions:** `render_bev()`, `add_robot_overlay()`
**Inputs:** BEV grid from slam_to_bev, annotation data
**Outputs:** PNG/BMP BEV images for dataset and visualization
**Thesis Contribution:** G49 visual training data

### 12. cross_modal_aligner.py — TEMPORAL ALIGNMENT (4 funcs)
**Role:** Aligns video frames with SLAM poses by timestamp synchronization
**Functions:** `align_video_to_slam()`, `sync_timestamps()`
**Inputs:** Video timestamps, SLAM timestamps, both data streams
**Outputs:** Synchronized pairs [(frame_i, pose_j)], alignment report
**Thesis Contribution:** G2 pipeline reliability — critical for VLA training

### 13. semantic_slam_fusion.py — SEMANTIC FUSION (3 funcs)
**Role:** Merges semantic labels with SLAM geometry
**Functions:** `fuse_semantic_geometry()`, `annotate_map()`
**Inputs:** Semantic detections, SLAM map
**Outputs:** Semantically annotated 2D/3D maps
**Thesis Contribution:** G49-G55 enriched training data

### 14. spatial_temporal_fusion.py — SPATIO-TEMPORAL (15 funcs)
**Role:** Fuses spatial and temporal dimensions for coherent scene understanding
**Functions:** `fuse_spatiotemporal()`, `track_objects()`
**Inputs:** Sequential frames with semantic annotations
**Outputs:** Temporal object tracks, scene evolution model
**Thesis Contribution:** G49-G55 dynamic scene understanding

### 15. video_event_extractor.py — EVENT DETECTION (2 funcs)
**Role:** Extracts meaningful events from video streams
**Functions:** `extract_events()`, `classify_scene()`
**Inputs:** Video frames, quality metrics
**Outputs:** Event timestamps, classifications, descriptions
**Thesis Contribution:** G49 scenario identification

### 16. scene_object_detector.py — OBJECT DETECTION (4 funcs)
**Role:** Detects and classifies objects in scenes using GroundingDINO/YOLO
**Functions:** `detect_objects()`, `classify_scene_elements()`
**Inputs:** Video frames, BEV images
**Outputs:** Bounding boxes, labels, confidence scores
**Thesis Contribution:** G49 semantic grounding

### 17. auto_labeler.py — AUTOMATIC LABELING (4 funcs)
**Role:** Generates training labels from detected objects and events
**Functions:** `auto_generate_labels()`, `validate_labels()`
**Inputs:** Detection results, event data
**Outputs:** Structured labels in VLA-compatible format
**Thesis Contribution:** G49-G55 labeled dataset generation

### 18. vla_dataset_builder.py — DATASET ASSEMBLY (3 funcs)
**Role:** Assembles all processed data into VLA training dataset
**Functions:** `build_vla_dataset()`, `validate_dataset()`
**Inputs:** BEV images, labels, semantic maps, aligned timestamps
**Outputs:** Complete VLA training dataset (images + instructions + actions)
**Thesis Contribution:** G49-G55 PRIMARY — creates the actual training data

### 19. qwen_dataset_formatter.py — QWEN FORMATTER (3 funcs)
**Role:** Formats dataset specifically for Qwen3-VL model architecture
**Functions:** `format_for_qwen()`, `create_conversation_pairs()`
**Inputs:** VLA dataset from vla_dataset_builder
**Outputs:** Qwen3-VL compatible JSON/JSONL training files
**Thesis Contribution:** G49-G55 model-specific formatting

### 20. cvat_converter.py — CVAT EXPORT (4 funcs)
**Role:** Converts annotations to CVAT format for manual review/correction
**Functions:** `export_to_cvat()`, `import_corrections()`
**Inputs:** Auto-generated labels, HITL corrections
**Outputs:** CVAT XML/JSON projects
**Thesis Contribution:** G52/G53 HITL workflow support

### 21. vla_supervisor_agent.py — VLA SUPERVISOR (1 func)
**Role:** Oversees VLA training process, monitors metrics
**Functions:** `supervise_training()`
**Inputs:** Training logs, validation results
**Outputs:** Training decisions, hyperparameter adjustments
**Thesis Contribution:** G54-G55 VLA model training supervision

### 22. vla_scenario_validator.py — SCENARIO VALIDATOR (1 func)
**Role:** Validates that generated scenarios meet thesis requirements
**Functions:** `validate_scenarios()`
**Inputs:** Generated scenarios, dataset samples
**Outputs:** Validation report, pass/fail per scenario type
**Thesis Contribution:** G49-G55 quality assurance

### 23. training_curriculum_advisor.py — CURRICULUM DESIGN (1 func)
**Role:** Designs and adapts the training curriculum for VLA model
**Functions:** `advise_curriculum()`
**Inputs:** Dataset characteristics, model performance
**Outputs:** Curriculum schedule, difficulty progression
**Thesis Contribution:** G54-G55 optimal training strategy

## INFRASTRUCTURE AGENTS (Supporting)

### 24. session_manager.py — SESSION LIFECYCLE (10 funcs)
**Role:** Manages session creation, monitoring, cleanup
**Functions:** `create_session()`, `monitor_status()`
**Thesis Contribution:** G2 operational reliability

### 25. co_pilot_agent.py — CO-PILOT (12 funcs)
**Role:** Interactive assistant for operator decisions and HITL
**Functions:** `prompt_decision()`, `log_operator_input()`
**Thesis Contribution:** G52/G53 HITL integration

### 26. offline_processor.py — OFFLINE MODE (6 funcs)
**Role:** Processes data when live connection unavailable
**Functions:** `process_offline()`, `load_cached_data()`
**Thesis Contribution:** G2 resilience

### 27. entity_registry.py — ENTITY TRACKING (14 funcs)
**Role:** Registry for all entities (robots, objects, people) in system
**Functions:** `register_entity()`, `lookup_entity()`
**Thesis Contribution:** G50 identity management

### 28. knowledge_engine.py — KNOWLEDGE BASE (24 funcs)
**Role:** Centralized knowledge storage and retrieval
**Functions:** `store_fact()`, `query_knowledge()`
**Thesis Contribution:** G51 learning persistence

### 29. label_registry.py — LABEL MANAGEMENT (17 funcs)
**Role:** Manages label taxonomy, consistency, versioning
**Functions:** `add_label_type()`, `validate_consistency()`
**Thesis Contribution:** G49 label quality

### 30. mir_command_logger.py — COMMAND LOGGING (13 funcs)
**Role:** Logs all commands sent to MiR100 for reproducibility
**Functions:** `log_command()`, `replay_log()`
**Thesis Contribution:** G2 audit trail

## SPECIALIZED AGENTS

### 31. A15_referee_ai_loop.py — REFEREE (11 funcs)
**Role:** Independent quality referee, validates agent outputs
**Functions:** `referee_check()`, `dispute_resolution()`
**Thesis Contribution:** Quality assurance layer

### 32. A16_agent_deep_analyzer.py — DEEP ANALYZER (10 funcs)
**Role:** Deep analysis of agent behavior and performance
**Functions:** `analyze_agent_behavior()`, `performance_metrics()`
**Thesis Contribution:** Diagnostic capability

### 33. slam_auto_namer.py — MAP NAMING (3 funcs)
**Role:** Automatic naming/categorization of SLAM maps
**Functions:** `auto_name_map()`, `categorize_environment()`
**Thesis Contribution:** G49 organization

### 34. slam_map_annotator.py — MAP ANNOTATION (1 func)
**Role:** Annotates SLAM maps with semantic information
**Functions:** `annotate_slam_map()`
**Thesis Contribution:** G49 enriched data

### 35. video_narrator.py — VIDEO NARRATION (1 func)
**Role:** Generates natural language descriptions of video events
**Functions:** `narrate_video()`
**Thesis Contribution:** G49 instruction generation for VLA

### 36. video_learning_agent.py — VIDEO LEARNING (3 funcs)
**Role:** Learns patterns from video data, improves over time
**Functions:** `learn_from_video()`, `apply_learned_patterns()`
**Thesis Contribution:** G51 continuous improvement

### 37. project_snapshot.py — SNAPSHOT (13 funcs)
**Role:** Captures project state for reproducibility
**Functions:** `take_snapshot()`, `restore_state()`
**Thesis Contribution:** G2 reproducibility

### 38. run_session_analysis.py — ANALYSIS RUNNER (9 funcs)
**Role:** Runs analysis pipelines on completed sessions
**Functions:** `run_analysis()`, `generate_report()`
**Thesis Contribution:** G1-G55 results generation

### 39. label_registry_auto.py — AUTO REGISTRY (4 funcs)
**Role:** Automatic label registry maintenance
**Functions:** `auto_update_registry()`
**Thesis Contribution:** G49 automation

### 40. apply_merge.py — MERGE HELPER (10 funcs)
**Role:** Applies and manages code/data merges
**Functions:** `apply_merge()`, `resolve_conflicts()`
**Thesis Contribution:** Development workflow

### 41. SendDataToNatNet.py — NATNET SENDER (small utility)
**Role:** Sends data to NatNet for external systems
**Functions:** Minimal sender utility
**Thesis Contribution:** External integration

## AGENT DEPENDENCY GRAPH
```
launch_session → session_manager → motive_connector → [NatNetClient, MoCapData]
                                      ↓
                              quality_gate ← video_quality_agent
                                      ↓
                              robot_data_analyzer → slam_to_bev → bev_image_renderer
                                      ↓
                              cross_modal_aligner ← video_event_extractor
                                      ↓
                      semantic_slam_fusion ← scene_object_detector ← auto_labeler
                                      ↓
                          vla_dataset_builder → qwen_dataset_formatter
                                      ↓
                          vla_supervisor_agent → training_curriculum_advisor
```

## LAW79: Agent Dossier Auto-Update Protocol
**Before any code change to an agent file:**
1. Record current function signatures (AST) in this dossier
2. After change, diff the AST and update affected sections
3. Log the delta in Actions_Memory.md with Step number
4. Re-run relevant diagnostic tests per LAW78

## AGENT CATEGORIZATION BY THESIS GOAL
**G1 Dataset Quality:** motive_connector, quality_gate, video_quality_agent, session_worthiness_analyzer
**G2 Pipeline Reliability:** robot_data_analyzer, cross_modal_aligner, session_manager, offline_processor
**G49-G55 VLA Training:** vla_dataset_builder, qwen_dataset_formatter, slam_to_bev, bev_image_renderer, semantic_slam_fusion, scene_object_detector, auto_labeler, video_narrator, vla_supervisor_agent, vla_scenario_validator, training_curriculum_advisor
**G50 Identity:** entity_registry
**G51 Learning:** knowledge_engine, video_learning_agent
**G52/G53 HITL:** co_pilot_agent, cvat_converter
