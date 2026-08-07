# Pass 10: Consensus Judge
Model: openrouter/auto-beta

# Pass 10/10 — Consensus Judge: Final Verdict

---

## [WHAT]

The MirMap&Motive thesis, as documented in MASTER_REPORT v7.7 and supported by the supplied artifacts, **cannot pass a Q1 defense in its current form.** The headline metric — *MAE_v = 0.060 m/s, −62.1% vs Zero-BL* — is computed against corrupted training targets (BUG-C), on a single-session dataset of 344 frames (BUG-E), using a self-scoring pipeline that audits itself (BUG-G). The chain of evidence (eval JSON, training history, BEV image, YOLO image) shows **mode collapse, not learning**: the model has memorized ~3 discrete (v, ω) pairs and reproduces them verbatim, regardless of input.

The seven observed bugs are not independent. They form a **causal chain**:

```
BUG-A (sync) → misaligned BEV inputs
   ↓
BUG-B (YOLO) → wrong object labels in BEV
   ↓
BUG-E (1 session) → no generalization signal
   ↓
BUG-C (9.13 m/s) → corrupted velocity targets
   ↓
MAE_v = 0.060 reported as "publication-grade"
   ↓
BUG-G (self-score 88.5 → 82.5) → false confidence
```

Any Q1 reviewer who traces one link will trace the others.

---

## [EVIDENCE]

### E1. BUG-C — Velocity calculation is corrupted (FATAL)

The MASTER_REPORT itself never reports the *9.13 m/s* number, but BUG-C is listed in your own audit header and BUG-D ("R²_w = 0.134") is consistent with broken targets. Predicted velocities cluster at `0.107, 0.407, 0.480, 0.114, 0.000` — exactly the template outputs visible in `eval_results_v3.json`. The model has learned the **median**, not the regression.

**Likely file:line locus** (inferred from agent roster + standard patterns):

| File | Suspect Line | Reason |
|---|---|---|
| `agents/motive_connector.py` | ~L310–L340 | MoCap packet parsing; positions likely kept in **mm** |
| `agents/robot_data_analyzer.py` | ~L87 (`v = dx / dt`) | Linear velocity from consecutive poses |
| `agents/vla_dataset_builder.py` | ~L42 (`targets = [...]`) | JSONL export without unit conversion |
| `agents/slam_data.pkl` loader | unknown | SLAM may report in cm, not m |
| `generate_publication_report_v5.py` | ~L217 (`speed_heatmap`) | Where 9.13 surfaces visually |

Most plausible bug pattern: **MoCap positions in mm, dt in seconds, no `/1000` conversion** → mm/s mislabeled as m/s. A real 0.0913 m/s human step becomes "9.13 m/s" by a factor of 100. Or: `dt ≈ 0` on two duplicate timestamps → division-by-zero, then clamped to a sentinel.

### E2. BUG-G — Self-scoring is circular

```
generate_publication_report_v5.py → writes MASTER_REPORT
MASTER_REPORT v7.7 → claims "82.5/100"
generate_publication_report_v5.py → reads eval_results_v3.json → emits figures
eval_results_v3.json → produced by your own train_qwen_vla.py
train_qwen_vla.py → trained on data from your own builders
```

There is **no external benchmark, no held-out test set, no cross-validation against MiR REST API logs, no human evaluation.** The "Grade A−" is the script praising its own output. This is what a Q1 reviewer calls **evaluation theater.**

### E3. BUG-E — One session, 344 frames = memorization

`session_2026-08-27_17-54-20` is the **only** session with full data (per MASTER_REPORT §3). All 344 frames come from:
- one operator (you),
- one lighting condition,
- one obstacle layout,
- one camera calibration,
- one ~6 min recording.

With 275 train + 69 val from one session, the model cannot generalize. The QLoRA loss curve (0.74 → 0.085 in 6 epochs) is the textbook overfit signature.

### E4. BUG-D — Mode collapse visible in raw predictions

From `eval_results_v3.json` (verbatim):

| Sample | GT | Pred | Class |
|---|---|---|---|
| 1 | (0.366, −0.043) | (0.407, −0.049) | FORWARD |
| 2 | (0.445, −0.259) | (0.407, −0.399) | FORWARD |
| 4 | (0.003, 0.022) | (0.107, +0.057) | IDLE |
| 6 | (0.001, −0.007) | (0.114, −0.037) | IDLE |
| 7 | (0.424, −0.436) | (0.480, −0.148) | FORWARD |

Cruise predictions all start with `0.407...` or `0.480...`. Idle predictions all start with `0.107...` or `0.114...`. **This is a lookup table, not a policy.** R²_w = 0.134 follows directly: angular output is noise around a single mode.

### E5. BUG-B — YOLO failure confirmed by image

The frame labeled `514` shows **4 bounding boxes stacked on the same human**, with class confidence visibly low. Frame `0` shows a robotic arm with **zero detections** — your 18-class industrial model does not contain the robot itself. The BEV (top image) labels three stationary rectangles as "PERSON," but their positions do not correspond to the MoCap-tracked operator visible in the camera frame.

### E6. BUG-A — Sync failure visible in BEV

The BEV shows the robot as a small blue square with a tiny trajectory stub, while the MoCap-derived "PERSON" markers are placed at **decoupled coordinates** with no temporal interpolation. `cross_modal_aligner.py` is only 157 lines — far too small to do proper SLAM↔MoCap timestamp interpolation at 30 Hz vs 180 Hz.

### E7. BUG-F — Statistical power = zero

Val n=69, Rotation val n=3. With n=3 you cannot reject H₀. Any "rotation performance" line in the paper is **decorative**, not evidential.

### E