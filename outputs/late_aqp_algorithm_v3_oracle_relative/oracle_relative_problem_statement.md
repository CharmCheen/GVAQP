# Oracle-Relative AQP Problem Statement

## 1. Research object

Given:

- A long video \( V \).
- A semantic query \( q = \) "Visible Ego-Path Conflict (VEPC)".
- An optional cheap prior signal \( P \) (e.g., fused detection/scene scores).
- An expensive oracle \( O_{\text{ref}} \) that can label video intervals as positive/negative for \( q \).
- A finite oracle budget \( B \) (number of interval-label queries).

Return:

- A set of candidate event intervals \( A = \{a_1, \dots, a_k\} \).
- An estimate of oracle-relative positive temporal mass.
- An estimate of oracle-relative missing mass.
- A report of candidate-envelope leakage (positive intervals outside the initial candidate envelope).

## 2. Oracle-relative semantics

This project uses an **oracle-relative** semantics definition.

- The reference oracle \( O_{\text{ref}} \) currently consists of VLM-oracle labels materialized in `clean_interval_aqp_full_reference_v2_clean_no_leak`.
- All recall, precision, mass, and leakage metrics are interpreted **relative to \( O_{\text{ref}} \)**.
- Human annotation is one valid oracle provider, but it is **not a necessary condition** for the problem definition or for evaluation.

## 3. What we do not claim

We do **not** claim:

- Human-ground-truth validity of VEPC events.
- Real-world autonomous-driving safety truth.
- Formal recall / precision / coverage guarantee.
- Calibrated missing-mass estimate without a dense \( O_{\text{ref}} \) evaluation window.
- Full temporal-interval reconstruction of events.
- Superiority over SUPG, ABae, or any other external baseline unless explicitly compared.

## 4. What we can claim

We can claim:

- LATE-AQP improves **oracle-relative** discovery of long-interval VEPC events compared with ExSample-style expansion in the existing VLM-oracle replay.
- The observed gain is not explained by selected-duration inflation at the budgets examined.
- Initial evidence is consistent with candidate-envelope leakage and temporal neighborhood structure.

## 5. Why oracle-relative is sufficient for this stage

The current research stage targets empirical recall/precision improvement under a fixed oracle definition. A formal certificate or human-grounded validation is explicitly out of scope unless a future task demands it. All downstream calibration designs in this directory are therefore **oracle-relative calibration** designs.
