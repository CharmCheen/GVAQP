# CENTER10 Multi-Method Replay Protocol V13.7

## Purpose

V13.7a is a no-new-large-VLM replay using existing V13.6 VLM labels. It compares multiple center10 anchor selection and budget allocation methods using only proxy features and existing labeled data.

**Cannot claim full-video event recall until a center10 full oracle reference is constructed.**

## Subordinate to

- `CASQ_CODEX_BRIEF_V12_1.md`
- `REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md`

## Global Restrictions

1. No new large-scale 32B VLM inference.
2. No model training.
3. VLM labels used only for evaluation after candidate rankings are frozen.
4. No human-truth claims.
5. No full-video recall claims without full center10 oracle.

## Allowed Claim

On the V13.6 labeled center10 subset, method X ranks VLM-positive O_enter_ego_path_v0 clips better/not better than uniform or random baselines.

## Forbidden Claims

- Human-truth recall
- Full-video recall
- Certified recall
- Generalization beyond realcartest
- Final online AQP usability
