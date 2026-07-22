
# D2 — Safety-shielded base policy pi0

Status: `LOGICAL_SPEC_COMPLETE`; numeric status: `BLOCKED_NUMERIC_BINDING`; physically executable freeze: **no**.

## State, actions, and ordering

`x_t=(I_t,rho_t)`, where `I_t=(C_t,H_t,E_t,m_t,q)` contains scan state, Event-Hypothesis Frontier, durable events, runtime mode, and frozen query, and `rho_t=T-t`. Actions are SCAN(region), atomic CONFIRM(h,w), and STOP. Only CONFIRM can modify committed output; no decision boundary exposes dirty confirmed state. SAFE_HARBOR returns the last complete durable snapshot without flushing.

Hypotheses sort by `(hypothesis_created_at,hypothesis_id)` and witnesses within them by `(witness_created_at,witness_id)`. Scores, M0, labels, future information, and rollout results cannot alter this order. The deterministic scan iterator sorts the frozen public manifest by `(start_time,end_time,unit_id)`; it uses 10-second nominal units and the manifest's explicit final boundary. Exact hashes are in `BASE_POLICY_SPEC.json`.

## Total decision rule

Let `P_C(x)={(h,w): w is unverified and not pending, B_C(x,h,w)<=rho}`. If nonempty, CONFIRM the first group-FIFO pair. Otherwise SCAN the next region only if `B_S(x,r)+R_C<=rho`. Otherwise STOP. A missing bound is not infinity or a guessed default: it makes that action inadmissible. Thus the logical function is defined everywhere, deterministic, standalone, non-anticipatory, deadline-aware, learned-estimator-free, and near-zero overhead.

`z_F=(|H|,s_max,s_median,rho)` is logging/analysis/admission/model/alerting data only. It cannot force SCAN, veto safe CONFIRM, or override rollout.

## Cost and safety audit

Complete costs must include selection, switching, queue, seek/decode, proxy/tracking, Oracle, parse, materialize, snapshot, commit, and frontier update. The frozen H-DS1 guard supplies a stricter operational CONFIRM reserve: `27.1050437105+0.2854655565=27.3905092670` seconds. It is a sum of two operational upper estimators, not a calibrated 0.9 quantile of complete `D_C`; `ALPHA_CONFIRM` is therefore unbound. Paired traces give empirical development evidence for one video/query/A800 workload, not WCET, a formal coverage level, or zero-miss theory.

The existing SCAN admission formula is `2.6691289902` seconds before a separate commit reserve. It derives from a per-frame p95, multiplies it by 50, adds an allowance, and adapts after observing completed SCAN wall time. It is not a directly calibrated pre-action full-obligation `B_S`; treating it as one would commit the prohibited phase-quantile/composition error. Therefore `TOTAL_SCAN_BOUND`, `ALPHA_SCAN`, and a certified global `MIN_ACTION_DURATION` remain blocking fields.

## Properties and proof obligations

- Conditional deadline safety: if every admitted action duration is at most its certified complete bound and admission requires bound `<=rho`, completion occurs by T. For SCAN, reserving `R_C` additionally leaves one standard CONFIRM slot. This theorem cannot currently be instantiated because `B_S` is missing.
- Empirical chance safety: calibrated quantiles support only workload-scoped empirical chance claims; H-DS1's 0/13 misses is validation evidence, not a formal zero-miss guarantee.
- Properness has two proofs. Under the requested positive-duration premise, at most `ceil(T/d_min)` non-STOP actions occur, but numeric `d_min` is unbound. Independently, a finite lexicographic rank decreases: SCAN consumes one of 347 regions and emits finitely many witnesses; CONFIRM terminalizes at least its selected witness. Thus logical termination does not rely on the missing numeric lower bound.
- Non-anticipation follows because the rule is a function only of runtime-visible `x_t` and fixed profiles.
- Evidence honesty follows from append-only state transitions: SCAN and STOP leave `E_t` unchanged; only completed atomic CONFIRM may replace it with `E_t union {e}`.

The focused pure unit tests cover all mandated action cases, deterministic tie-breaking, future-field rejection, and fail-closed missing binding.
