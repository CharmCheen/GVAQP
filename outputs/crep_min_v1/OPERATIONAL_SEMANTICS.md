# CREP-Min v1 — Frozen Operational Semantics (Phase 1)

Status: FROZEN (this document + `OPERATIONAL_SEMANTICS.json` are the v1
contract). CPU-only; no inference; no project state files modified.

## 1. State

At decision step `t`, the execution state is

```
K_t = ( O_t, C_t, Γ_t, R_t, B_t, V_t )
```

| Symbol | Meaning | Fixed-candidate-replay instantiation (this repo) |
|---|---|---|
| `O_t` | currently legal, visible observations | verified outcomes of queried units; proxy scores of exposed candidates; no unqueried outcomes, no reference |
| `C_t` | currently visible candidates | all unit identities precomputed (1475); visibility = queried-set complement |
| `Γ_t` | legal action set / capabilities | `{VERIFY(c) : c ∉ queried}` — VERIFY legal only on not-yet-queried candidates |
| `R_t` | durable EventRelation | C1-gap materialized events from verified-relevant units (or K0/C3 variants under version pin `V_t`) |
| `B_t` | remaining resource | `budget − |queried|` (abstract VERIFY count) |
| `V_t` | version set | {proxy, verifier, materializer, evaluator, reference, cost-model} hashes |

## 2. Action transition — strict separation of six events

```
state
  -> (1) action selected      a ∈ Γ_t
  -> (2) action started       start_t
  -> (3) action completed     finish_t
  -> (4) outcome visible      outcome(a) revealed to policy state
  -> (5) relation materialized  R updated from (R_{t-1}, outcome)
  -> (6) relation committed   durable append (fsync)
```

Definitions (must never be conflated):

- **action selected**: policy output at `K_t`; the only event a policy
  controls (offline logs may record it).
- **action started**: resource consumed at `start_t`.
- **action completed**: `finish_t`; the earliest time the outcome may legally
  exist; deadline eligibility uses `finish_t`, never `start_t`.
- **outcome visible**: outcome enters `O`; a policy may read it only now.
- **relation materialized**: derived in-memory state from visible outcomes
  (deterministic function of (queried, outcomes, materializer version)).
- **relation committed**: durable, atomic, post-deadline-immutable.

## 3. Policy-visible vs oracle partition (hard)

| visible_* | oracle_* |
|---|---|
| proxy scores/ranks of all candidates | unqueried verifier outcomes |
| verified outcomes of queried units | reference event ids / EventF1 |
| queried set, budget, clock | future candidates (non-existent under endogenous SCAN) |
| derived C1 components (from visible outcomes) | evaluator state |

## 4. Version closure requirements (Phase 2 closure F)

Every claim certificate must pin:
`V_t = (proxy_table_hash, verifier_table_hash, materializer_hash, matcher_hash, reference_hash, cost_hash)`.

Locally available pins: P2 protocol input hashes, SCAN_MANIFEST hashes,
V10 REFERENCE_MANIFEST hash, engine fidelity anchor (252/252 vs P2).

## 5. Scope boundary

- This semantics is for FIXED_CANDIDATE_REPLAY (endogenous SCAN instantiation
  is a *future* semantics; its closure properties are precisely what
  counterexamples C1–C4 formalize as missing).
- Human reference: external-validity evaluator only, never policy input.
