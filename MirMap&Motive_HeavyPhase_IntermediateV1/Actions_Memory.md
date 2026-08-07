# Actions Memory — حافظه اقدامات
# Last Updated: 2026-09-24 Step 45 (Call Graph Complete)
# Purpose: Track all actions, bugs discovered, test results, and decisions

## FORMAT
Each entry follows LAW78 protocol:
```
[DATE] STEP# | ACTION_TYPE | Agent/Target | FINDING | EVIDENCE | DECISION
```

---

## STEP 45 — Detailed Call Graph & Data Flow Analysis (2026-09-24)

### Action: Complete call-graph extraction via AST-level function analysis + data I/O tracing
**Evidence:** Python script scanned all 40 agent files for `def` signatures, `import` statements, and file I/O patterns (pkl/json read/write). Read launch_session.py lines 690-1289 for exact stage flow.
**Finding:** Full call chain mapped from `launch_session.main()` → 9 stages → VLA pipeline output. Data flow traced: slam_data.pkl + motive_data.pkl → fused_data.pkl → deep_memory.pkl → qwen_vla_dataset.jsonl

### Key Findings — Call Graph Details:

#### launch_session.py ORCHESTRATES exactly these agents in this order:
| Stage | Agent Called | Function Imported From | Input Files | Output Files | Status |
|-------|-------------|----------------------|-------------|--------------|--------|
| 1 | spatial_temporal_fusion | `fuse_session()`, `save_fusion_result()` | slam+motive+calib pkl | fused_data.pkl | ✅ Active |
| 2 | knowledge_engine | `analyze_session()` | fused_data.pkl | report + deep_memory update | ✅ Active |
| 3 | knowledge_engine | `rebuild_all_sessions()` | all sessions | deep_memory.pkl | ✅ Active |
| 4 | session_manager | `update_knowledge_from_session()` | fused_data+calib pkl | environment_knowledge.pkl | ✅ Active |
| 5 | label_registry_auto | `run_auto_registry()` | fused_data.pkl + taxonomy.json | label_registry.pkl | ✅ Active |
| 6 | cross_modal_aligner | `run_alignment()` ← BROKEN | slam+motive timestamps | cross_modal_matches.jsonl | ❌ SKIP |
| 7 | co_pilot_agent | `generate_report()` | all session data | co_pilot_report_vN.md | ✅ Active |
| 8 | auto_labeler | subprocess (interactive) | video files | auto_labels.xml | ⚠️ Interactive |
| 9a | slam_map_annotator | `annotate_slam_session()` | slam+motive pkl | slam_semantic_map.json | ✅ Active |
| 9b | slam_to_bev | `generate_bev_tokens()` → bev_image_renderer.process_session() | slam_data.pkl | bev_tokens.jsonl + BEV pngs | 🔴 BUG-DX,EC |
| 9c | video_narrator | `build_vla_narrative_and_dataset()` | slam+motive+commands pkl | qwen_vla_dataset.jsonl | ✅ Active |

#### Cross-Agent Dependencies (Who calls Whom):
- **co_pilot_agent** → knowledge_engine, entity_registry, robot_data_analyzer, session_manager
- **vla_dataset_builder** → robot_data_analyzer (`compute_differential_kinematics_robust()`)
- **quality_gate** → knowledge_engine (deep memory + stagnation check)
- **vla_supervisor_agent** → vla_scenario_validator (`analyze_session_physics()`)

#### Prompt Generation Flow:
- **video_narrator:** Extracts events from slam_data.pkl → builds prompt/response pairs per frame → outputs Qwen-VL JSONL format with BEV images + scene descriptions + action commands
- **co_pilot_agent:** Checks SLAM/Motive health → pulls knowledge_engine section → generates recommendations → writes Markdown report
- **vla_supervisor_agent:** Reads physics validation + video events → builds multi-modal confidence matrix (temporal_sync, spatial_accuracy, semantic_coverage, physics_validity)

### Bug Impact Assessment on VLA Training:
| Bug | Agent Affected | Line | Raw Evidence | Impact on Dataset | Severity |
|-----|---------------|------|-------------|-------------------|----------|
| BUG-DX | slam_to_bev.py | 48 | `"timestamp_rel_s": round(idx * 0.05, 3)` — synthetic timestamps | BEV tokens have wrong temporal alignment → VLA model learns incorrect timing | 🔴 HIGH |
| BUG-EC | bev_image_renderer.py | 177 | `min(len(robot_states), 344)` — hard frame cap | 45% data loss (621→344 frames) → smaller training dataset | 🔴 HIGH |
| BUG-EG | launch_session.py | 809 | `from cross_modal_aligner import run_alignment` — ImportError silenced | Stage 6 always skipped → no cross-modal temporal grounding | 🟡 MEDIUM |
| BUG-EA/EB | vla_scenario_validator/supervisor | 13,15 | `ROOT = Path(r"D:\kiarash\...")` — hardcoded D: drive | Won't run on RTX 5090 → no scenario coverage validation | 🔴 HIGH |
| BUG-ED | All sessions | cross_modal_matches | `human_confirmed: false` everywhere | No human-in-the-loop validation → dataset quality unverified | 🟡 MEDIUM |
| BUG-EE | auto_labeler.py | — | ultralytics package missing in openvla env | GroundingDINO non-functional → no auto-labeling | ⚪ LOW (not critical path) |

### Goal Alignment Results (Updated):
- **7 agents** directly serve VLA training goal (Critical Path)
- **5 agents** indirectly support (Secondary but useful)
- **13 agents** NOT needed for current training focus
- **3 agents** reserved for future inference phase

---

## STEP 44 — Initial Architecture Mapping (2026-09-24)

### Action: Complete codebase scan of all 39 agent files
**Evidence:** Read all Tier 1-7 agents via read_file tool
**Finding:** Pipeline has 9 stages; only Stages 1, 2, 3, 4, and 9 are on critical path for VLA training

### Bug Confirmations:
| Bug | Agent | Line | Raw Evidence | Severity |
|-----|-------|------|-------------|----------|
| BUG-DX | slam_to_bev.py | 48 | `"timestamp_rel_s": round(idx * 0.05, 3)` — synthetic timestamps | 🔴 HIGH |
| BUG-EC | bev_image_renderer.py | 177 | `min(len(robot_states), 344)` — hard frame cap | 🔴 HIGH (45% data loss) |
| BUG-EG | launch_session.py | 809 | `from cross_modal_aligner import run_alignment` — function doesn't exist | 🟡 MEDIUM |
| BUG-EA/EB | vla_scenario_validator.py line 15, vla_supervisor_agent.py line 13 | `ROOT = Path(r"D:\kiarash\...")` — hardcoded D: drive | 🔴 HIGH (wrong machine) |
| BUG-ED | All sessions cross_modal_matches | `human_confirmed: false` everywhere | 🟡 MEDIUM |
| BUG-EE | auto_labeler.py | ultralytics package missing in openvla env | ⚪ LOW |

---

## PENDING ACTIONS (Awaiting Operator Command)

### Phase 1: SOTA Test Criteria Research
- [ ] Search GitHub repos for multi-modal VLA dataset validation benchmarks
- [ ] Extract 100+ test criteria from roboflow, openvla, and related repos
- [ ] Map each criterion to specific agent + code line

### Phase 2: Agent-Specific Testing (5 tests per bug)
- [ ] BUG-DX: Verify timestamp generation logic vs actual SLAM data
- [ ] BUG-EC: Confirm frame count mismatch in BEV output
- [ ] BUG-EA/EB: Test path resolution on 5090 machine

### Phase 3: Dataset Quality Assessment
- [ ] Validate JSONL format compliance with Qwen-VL spec
- [ ] Check BEV image quality and coverage
- [ ] Verify scenario diversity in training pairs

---

## REPOSITORIES TO SEARCH (SOTA Testing)
1. `openvla/openvla` — Official OpenVLA dataset validation
2. `robot-learning/roboqa-temporal` — Temporal alignment tests
3. `huggingface/datasets` — VLM/VLA dataset quality checks
4. `qwenlm/qwen-vl` — Qwen-VL training format validation
5. `facebookresearch/vissl` — Visual self-supervised learning benchmarks
