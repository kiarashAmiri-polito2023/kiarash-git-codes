# Pass 9: PowerShell-Patch Generator
Model: nvidia/nemotron-3.5-lightning:free

**[HOSTILE Q1 REVIEWER MODE: ACTIVE]**
**TARGET:** Training Data Quality & Dataset Sufficiency for Qwen-VL VLA Fine-tuning
**STUDENT:** Kiarash Amiri – *Single session, massive overfit, circular validation, and kinematic hallucinations*
**GOAL:** Determine if this thesis passes Q1 or if it’s a systematic garbage-in/garbage-out failure.

---

### [WHAT] BUG-E: Single-Session Overfit (344 frames, 1 session)
The Qwen-VL model was trained and evaluated on **one single session** (`session_2026-08-27_17-54-20`). The master report confirms: `Total BEV Frames: 344`, `Full Sessions: 1`, Train: 275, Val: 69 all from the **same session**. Q1 requires ≥1000 diverse samples across **≥5 sessions**. This is not fine-tuning; it’s overfitted memorization.

**EVIDENCE** (file:line & master report):
- Master Report v10.0 §2: “Total Pairs: 344 | Train: 275 | Val: 69” – all derived from one session.
- Master Report v10.0 §3: Session audit shows ONLY `session_2026-08-27_17-54-20` has `BEV: 344`, `Vid: 2`, Score `100%`. All other sessions have `BEV: 0`.
- Master Report v10.0 §7: BUG-E marked `PENDING` (“Need Sessions 8-12”).
- Master Report v10.0 §10