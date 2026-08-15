# Geometry Audit (local, CPU-only)

Four separate geometry claims are audited independently. None implies any
other. Statuses: SUPPORTED / PARTIAL / DISFAVORED / ABSENT / PENDING /
UNVERIFIABLE.

## G1 — geometry predicts model-relative terminal EventF1

- **Status: SUPPORTED (model-relative scope only).**
- Re-derived locally from `outputs/event_evidence_geometry_v1/LOVO_RESULTS.csv`:
  macro per-video LOVO R²: yield-only **0.0057**, yield+public/online
  geometry **0.7953**, reference-aware upper diagnostic **0.9803**
  (reported as 0.006 / 0.795 / 0.980 — consistent).
- Scope guard: reference is full-grid K3-defined and model-relative; 3
  videos; the association is descriptive, not causal mediation.
- `EVENT_EVIDENCE_GEOMETRY = PARTIAL` as an overall decision remains fair
  because only 1/3 videos supplies a top equal-yield counterexample with
  F1 gap ≥ 0.15.

## G2 — geometry predicts VLM-direct independent-style event recovery

- **Status: DISFAVORED.**
- Shadow result (machine-readable, locally re-verified): macro coverage
  effect **+0.003193**; 2/6 clusters positive, 2 zero, 2 negative; 2/3
  source-video means positive; proxy directions conflict (YOLO −0.004974,
  optical flow +0.009136); geometry improves LOVO MAE by only **0.000665**;
  frozen-C1 matched-pair effect −0.001026 (not C1-driven).
- Reference caveat: dual sessions of the SAME Qwen3-VL-8B checkpoint
  (matched-event fraction 0.313) — low independence, not human truth.
- `SHADOW_P1_POTENTIAL = LOW` is supported by the local numbers.

## G3 — geometry predicts independent human-event recovery

- **Status: PENDING (protocol frozen; zero labels).**
- `HUMAN_EVENT_LABELS.jsonl` has 0 rows (verified: empty-file sha256
  `e3b0c442…`). Six clusters frozen; analyzer ready; no P1 PASS/PARTIAL/FAIL
  exists. No inference is licensed in either direction.

## G4 — geometry predicts SCAN/VERIFY action value

- **Status: ABSENT.**
- The 108-state cached table contains both SCAN-better and VERIFY-better
  states (25/26/57 at 1e-12; 5/5/98 at practical delta 0.005 — same deltas,
  different thresholds, reconciled), but learned public-state rules
  (AUROC 0.548; regret 0.009693 vs fixed 0.000885) do NOT predict action
  value from policy-visible geometry.
- `SEMANTIC_STATE_RESIDUAL` in P2 = ABSENT; no local experiment measures
  geometry as an action-value predictor on physical or human data.
- The old R² 0.795 is terminal-quality association under a reference-aware
  reference; it does not constitute action-value evidence (it used
  reference-aware columns marked OFFLINE_DIAGNOSTIC_ONLY).

## Cross-claim discipline

- G1 (SUPPORTED, model-relative) does NOT imply G3 (PENDING) or G4 (ABSENT).
- The VLM-shadow artifacts exist locally in machine-readable form and their
  headline numbers were re-verified; the shadow therefore stays A-class for
  its own ontology claim, but its ontology is same-checkpoint and low-agreement.
- Any statement of the form "geometry helps event recovery" without the
  model-relative qualifier is unsupported locally.
