# MF-PSVR Stage-A model card

## Outcome

- Readiness decision: `NOT_READY_FOR_PHYSICAL_PILOT`.
- Selected representation: `M0_LOGISTIC`.
- Best aggregate model: `M0_LOGISTIC` (development LOSO AUPRC 0.555469).
- Best temporal model: `TCN_TEMPORAL` (development LOSO AUPRC 0.335634).
- Selected fixed pool-audit AUPRC: 0.8197781385281386.
- Analysis status: exploratory; not preregistered and not cryptographically blinded to oracle labels.

## Evaluation contract

Exact leave-one-`(source_dataset, session_id)`-out predictions over the preassigned `model_train` and `model_calibration` roles are the primary selection evidence. The `pool_audit` role (32 semantic rows before binary exclusions) was arithmetically excluded from selection and fitting and evaluated only after the winner was fixed. The full dataset was locally available throughout; no cryptographic blind or label-blind preregistration is claimed. Random row splits are absent.

Leave-one-dataset-out is not identifiable because Stage A contains one dataset family. Leave-one-query-out is reported as a transfer stress test. AUPRC is deliberately left undefined for one-class source slices.

## Model inputs

Aggregate models use only the numeric runtime-visible feature list bound by `STAGE_A_FEATURE_SCHEMA.json`: 61 columns retained from 72 candidates by a label-free, intercept-aware full-rank pruning. Raw numeric `witness_class_id` is excluded. Temporal models use 64-step YOLO/ByteTrack features, query one-hot conditioning, and witness-class one-hot conditioning. Source/session/call/unit/anchor/event/oracle fields are excluded. No RGB backbone or YOLO retraining occurs.

## Interpretation limits

This is a stratum-enriched support sample, not a prevalence sample. Unit-level oracle outcomes do not verify the witness track itself. Cross-session transport is measured, but cross-dataset transport is unresolved. Coefficients and gain scores are exploratory associations, not independently identified feature effects. The pool-audit set is small, so its uncertainty is substantial even when its AUPRC is identifiable.

The final calibration role has 1 positive and 27 negative binary rows (Q1/Q2 positives: 1/0). Its status is `UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE`. Serialized Platt maps for M1/TCN/GRU reproduce the exploratory audit only and are not deployable calibrators.
