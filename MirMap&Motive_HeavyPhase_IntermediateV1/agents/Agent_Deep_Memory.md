# Agent Deep Memory Registry - Auto-Updated
# Last scan: 2026-09-26 | Total: 41 agents across 10 categories
# LAW79: This file auto-updates on every code change or test run

## INFRASTRUCTURE
  - **DataDescriptions.py** (737L)
    Classes: MarkerSetDescription, RBMarker, RigidBodyDescription, SkeletonDescription, ForcePlateDescription, DeviceDescription, CameraDescription, DataDescriptions
  - **MoCapData.py** (873L)
    Classes: FramePrefixData, MarkerData, MarkerSetData, RigidBodyMarker, RigidBody, RigidBodyData, Skeleton, SkeletonData, LabeledMarker, LabeledMarkerData, ForcePlateChannelData, ForcePlate, ForcePlateData, DeviceChannelData, Device, DeviceData, FrameSuffixData, MoCapData
  - **NatNetClient.py** (842L)
    Classes: NatNetClient

## DATA_ACQUISITION
  - **motive_connector.py** (491L) | Module: motive_connector.py  (v2 — rewritten against the ACTUAL NatNetClient SDK)
    Classes: MotiveConnector
  - **mir_command_logger.py** (258L) | mir_command_logger.py - Robot Command History Logger (v1.0)
    Classes: MirCommandLogger

## FUSION_ALIGNMENT
  - **spatial_temporal_fusion.py** (523L) | Agent 3: spatial_temporal_fusion.py (v2)
    Functions: utc_now_iso, load_calibration, load_slam_session, load_motive_session, motive_to_mir_point, robot_edge_distance_m, safety_zone, is_zero_placeholder_mm
  - **cross_modal_aligner.py** (229L) | cross_modal_aligner.py — FIXED v2.0
    Functions: match_slam_to_mocap_interpolated, compute_sync_quality, match_slam_to_mocap, run_alignment
  - **semantic_slam_fusion.py** (172L) | semantic_slam_fusion.py (v1.0)
    Functions: map_pixels_to_slam, fuse_session_data, main
  - **slam_auto_namer.py** (141L) | slam_auto_namer.py - Automatic SLAM Cluster Naming (v1.0)
    Functions: utc_now_iso, link_slam_to_entities, main

## ANALYSIS_INSIGHT
  - **robot_data_analyzer.py** (220L) | robot_data_analyzer.py — FIXED v2.0
    Functions: wrap_to_pi, compute_differential_kinematics_robust, validate_mir100_commands, compute_session_statistics
  - **session_worthiness_analyzer.py** (209L)
    Functions: utc_now_iso, load_pkl, analyze_session_worthiness, main
  - **video_quality_agent.py** (700L) | video_quality_agent.py - Industry-Grade Video Quality Agent (v2.0)
    Functions: utc_now_iso, find_project_root, list_video_sessions, count_csv_frames, detect_ghost_overlay, measure_motion_blur, measure_dynamic_range, compute_scene_diversity
  - **video_event_extractor.py** (112L) | Video Event Extractor Agent
    Functions: analyze_video_file, process_all_sessions
  - **video_learning_agent.py** (260L) | video_learning_agent.py (v1.0)
    Functions: compute_video_motion_profile, analyze_mocap_dynamics, pair_and_analyze_all_sessions
  - **vla_scenario_validator.py** (140L) | VLA Physical Scenario Validator (v2.0 - Anti-Hallucination & Multi-Modal Grounding)
    Functions: analyze_session_physics
  - **quality_gate.py** (509L) | quality_gate.py — Flag Generator (v2)
    Functions: run_quality_gate

## VLA_DATASET
  - **qwen_dataset_formatter.py** (157L) | qwen_dataset_formatter.py (v3.0 - Real Dynamic SLAM Ground Truth)
    Functions: classify_behavior, format_session, main
  - **vla_dataset_builder.py** (151L) | vla_dataset_builder.py — Fully Adaptive Multi-Modal Dataset Builder
    Functions: find_bev_images, extract_kinematics, build_qwen_training_pairs
  - **video_narrator.py** (100L) | VIDEO NARRATOR & QWEN-VLA DATASET GENERATOR
    Functions: build_vla_narrative_and_dataset

## KNOWLEDGE_MEMORY
  - **knowledge_engine.py** (455L) | knowledge_engine.py — Cumulative Learning Brain (v2.2)
    Functions: utc_now_iso, safe_pickle_dump, load_deep_memory, save_deep_memory, cluster_lidar_points, transfer_labels_to_clusters, extract_session_features, update_memory_from_session
  - **session_manager.py** (419L) | session_manager.py — Project Inspector + Memory Manager
    Functions: utc_now_iso, utc_now_epoch, load_persistent_knowledge, save_persistent_knowledge, bootstrap_project_root, create_new_session_folder, update_knowledge_from_session, inspect_project
  - **entity_registry.py** (283L) | entity_registry.py - Master Entity Registry (v1.0)
    Classes: EntityRegistry
  - **apply_merge.py** (399L) | apply_merge.py — Human-Approved Merge Executor
    Functions: utc_now_iso, timestamp_tag, deep_memory_path, deep_memory_summary_path, backup_dir, create_backup, list_all_backups, print_preview_summary

## AUDIT_ANALYZER
  - **A15_referee_ai_loop.py** (405L) | A15_referee_ai_loop.py v3.5 — Hybrid 2-Part Persona + Auto Model Discovery
    Functions: load_key, discover_free_models, read_safe, find_files, encode_image_b64, scan_agent_code, get_dashboard_images, gather_data
  - **A16_agent_deep_analyzer.py** (594L) | A16_agent_deep_analyzer.py — Intelligent Multi-AI Agent Analyzer v1.0
    Functions: check_api_availability, query_claude, query_grok, query_gemini, query_openrouter, query_all_models, scan_agent_files, analyze_session_quality
  - **A18_deep_agent_verifier.py** (234L)
    Functions: extract_json, query_lmstudio, analyze_agent, warmup_lmstudio, main
  - **project_snapshot.py** (651L)
    Functions: audit_agents, audit_persistent_knowledge, deep_vla_audit, audit_multimodal_dataset, audit_sessions, audit_model, verify_bug_fixes, audit_backup

## LABELING_DETECTION
  - **auto_labeler.py** (261L) | auto_labeler.py — Fixed v2
    Functions: load_gdino_model, run_grounding_dino, create_cvat_xml, auto_label_video
  - **cvat_converter.py** (86L) | agents/cvat_converter.py - CVAT Export to Project JSONL
    Functions: utc_now_iso, parse_cvat_xml, convert_to_jsonl, main
  - **label_registry.py** (300L) | agents/label_registry.py - Persistent Label Registry (v1)
    Classes: LabelRegistry
  - **label_registry_auto.py** (127L) | agents/label_registry_auto.py - Auto-Activation Module
    Functions: load_taxonomy, classify_by_taxonomy, run_auto_registry, main
  - **scene_object_detector.py** (119L) | scene_object_detector.py - Fixed v2
    Functions: get_model, detect_objects_safe

## BEV_RENDERING
  - **slam_to_bev.py** (95L) | SLAM TO BEV (Bird's Eye View Tokenizer for VLA Models)
    Functions: generate_bev_tokens
  - **bev_image_renderer.py** (220L)
    Functions: world_to_bev, render_semantic_bev_frame, process_session, main
  - **slam_map_annotator.py** (74L) | SLAM MAP ANNOTATOR - Industrial Production Grade
    Functions: annotate_slam_session

## ORCHESTRATION
  - **launch_session.py** (1218L) | launch_session.py — v7 (Full VLA Pipeline) (Extended Pipeline + New Agents)
    Classes: CrashLogger, MirSlamLogger, MotiveTrackerThread
  - **run_session_analysis.py** (337L) | run_session_analysis.py — Orchestrator for Full Session Workflow
    Functions: utc_now_iso, run_fusion, run_knowledge_engine_safe, run_quality_gate, generate_merge_review_package, initialize_comprehensive_report, append_agent_output, run_full_analysis
  - **offline_processor.py** (156L) | agents/offline_processor.py - Standalone processor for existing sessions
    Functions: find_project_root, list_sessions, pick_session, run_stage, process_session, main

## REPORTING
  - **co_pilot_agent.py** (647L) | Agent: co_pilot_agent.py  ("کمک خلبان") — v2
    Functions: utc_now_iso, check_slam_health, check_motive_health, check_fusion_quality, check_calibration_sanity, review_persistent_knowledge, get_knowledge_engine_section, get_session_discoveries
  - **vla_supervisor_agent.py** (91L) | VLA Master Supervisor Agent (Multi-Modal Grounded Intelligence)
    Functions: run_supervisor
  - **training_curriculum_advisor.py** (80L) | Training Curriculum Advisor (Next-Session Intelligent Tutor)
    Functions: generate_curriculum
