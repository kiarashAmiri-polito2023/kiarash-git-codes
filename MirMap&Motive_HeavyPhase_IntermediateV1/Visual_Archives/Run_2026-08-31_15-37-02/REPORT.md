# Publication-Grade Visual Report

**Run ID:** `Run_2026-08-31_15-37-02`  
**Operator:** Kiarash Amiri (s322803)  
**Institution:** Politecnico di Torino / DIGEP  
**Session analyzed:** `session_2026-08-27_17-54-20`  
**Videos used:** `session_2026-08-27_17-54-20-Camera 1 (M69428).avi`, `session_2026-08-27_17-54-20-Camera 7 (M69432).avi`

## Health & Integrity Status

| Check | Result |
|---|---|
| BEV frames discovered | 344 |
| Camera videos used | 2 |
| Eval predictions loaded | 69 |
| Training epochs loaded | 6 |
| Canary logs per epoch | 6 |
| Errors logged | **0** |

## Folder Inventory

| Folder | Files |
|---|---|
| `1_BEV_Frames` | 20 |
| `2_YOLO_Detections` | 32 |
| `3_SLAM_Maps` | 3 |
| `4_Publication_Figures` | 7 |
| `5_Decision_Dashboards` | 6 |

## Key Scientific Results (all from real files)

- **MAE_v** = `0.0600 m/s`
- **MAE_w** = `0.0799 rad/s`
- **Zero baseline MAE_v** = `0.1582`
- **Improvement over zero-BL** = `-62.1%`

## Data Provenance (zero hardcoded numbers)

| Artifact | Source file |
|---|---|
| Table 1 | `eval_results_v3.json` [mae_v, mae_w, z_bl, m_bl] |
| Figure 1 (Loss) | `training_history.json` [epochs] |
| Figure 2 (Canary) | `training_history.json` [canary] |
| Figure 3 (Scatter) | `eval_results_v3.json` [p] |
| Figure 4 (Behavioral MAE) | `eval_results_v3.json` [p][cls] |
| Figure 5 (Chain-of-Thought) | `eval_results_v3.json` [p][raw] |
| Figure 6 (BEV Montage) | `sessions/*/bev_images/*.png` |
| Maps 1-3 | `slam_data.pkl` + `fused_data.pkl` |
| YOLO detections | `motive sessions/*.avi` + `yolo_detections.json` |

## Verdict

- Integrity: PASS (0 errors)
- Ready for supervisor review: **YES**