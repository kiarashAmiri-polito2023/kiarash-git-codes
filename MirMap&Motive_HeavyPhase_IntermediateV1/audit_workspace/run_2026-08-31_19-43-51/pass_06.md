# Pass 6: Qwen-VL Training Skeptic
Model: nvidia/nemotron-3.5-lightning:free

# HOSTILE Q1 REVIEWER — PASS 6/10: QWEN-VL TRAINING SKEPTIC
## Focus: BUG-C — Calculation Bug (max velocity 9.13 m/s vs MiR100 1.5 m/s)

**[WHAT]**

The reported "max velocity = 9.13 m/s" is **physically impossible** for a MiR100 (spec: 1.5 m/s max). This value does not appear in the RTX 3090 training logs (MAE_v = 0.060 m/s suggests predicted velocities are well below 1.5 m/s). The bug is therefore in **post-processing/reporting**, not in the VLA predictions themselves. The 9.13 m/s is almost certainly a unit-conversion error, a `dt` inversion, or a frame-count–vs–seconds mistake in the dataset builder or report generator. Without a correct velocity ground truth, the VLA is trained on garbage target values, and the MAE of 0.060 m/s is meaningless — it measures error relative to a broken target.

**Most likely source:** `robot_data_analyzer.py` or the dataset formatting pipeline that computes/clamps velocities before Qwen-VL pairing. The number 9.13 hints at: `1.5 * 6.087` (random multiplier), `344 frames / 37.8 ms dt`, or a `mm/s → m/s` divide-by-1000 omission.

**[EVIDENCE]**

| Metric | Reported | MiR100 Spec | Bug |
|---|---|---|---|
| `max(|v|)` | **9.13 m/s** | **1.5 m/s** | **6.09× overflow** |
| `mae_v` (eval) | 0.060 m/s | — | Small MAE relative to broken target |
| `mae_w` (eval) | 0.0799 rad/s | 1.0 rad/s max | Angular MAE reasonable |
| Dataset size | 344 frames (1 session) | — | BUG-E compounding issue |

**File:line hypotheses (based on agent roster):**
- `robot_data_analyzer.py` line ~87: velocity computation from MoCap/SLAM pose diffs
- `vla_dataset_builder.py` line ~42: velocity clamping/normalization before JSONL export
- `generate_publication_report_v5.py` line ~217: dashboard max-speed annotation (likely where 9.13 is hardcoded/plotted)

*Exact line numbers depend on source not fully exposed; I identify the **function** and **logical locus**.*

**[TEST]**

Run this PowerShell snippet on the working directory to expose the velocity source:

```powershell
# POWERSHELL: Find where 9.13 is generated
$BASE = "D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
$sessions = Get-ChildItem -