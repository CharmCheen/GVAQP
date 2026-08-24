# Next-stage state machine

Current: **B1a protocol frozen; bind fresh inputs before requesting execution authorization.**

```text
B0 CPU action/information/evaluator contract
├── FAIL: reference leakage, forced candidates, unequal clocks,
│         or asymmetric evaluation is required
│         → stop Claim-B implementation; revise the problem
└── PASS: infrastructure qualified only
          → freeze fresh-workload and physical-cost protocol
          → require separate explicit authorization
             ↓
            B1 natural opportunity
            ├── absent/rare/trivial → close adaptive Claim B
            └── material and replicated
                   ↓
                  B2 legal online observability
                  ├── not predictable held-out → retain simple fixed policy
                  └── predictable and safe
                         ↓
                        B3 deployable policy evaluation
```

Human P1 is a separate deferred external-validity route. It is not a
prerequisite for B0 CPU qualification and is not silently replaced by it.

## Lock table

| Stage | State | Authorized now? | Entry condition |
|---|---|---:|---|
| P0 Claim-B pivot | `COMPLETE` | No rerun | CPU-only pivot and current DATB retirement recorded |
| B0 CPU contract qualification | `PASS / INFRASTRUCTURE QUALIFIED` | No rerun | Eight invariants and exact parity passed; 26 executor tests passed |
| B1a protocol design | `COMPLETE / FROZEN` | No rerun | Frozen package and CPU preflight complete |
| B1a input binding | `BLOCKED_INPUTS_UNBOUND` | Read-only binding preparation only | Three fresh video hashes; SCAN artifact/runtime; verifier/prompt/runtime |
| B1a natural opportunity execution | `BLOCKED` | No | Complete input binding plus separate explicit external-compute authorization |
| B1b natural opportunity confirmation | `BLOCKED` | No | B1a PASS plus at least six additional fresh videos and new preregistration |
| B2 observability | `BLOCKED` | No | B1 material and replicated |
| B3 adaptive policy | `BLOCKED` | No | B2 held-out predictability and downside gate |
| P5 controller/MAB/RL | `CLOSED` | No | Not reconsidered until B0-B2 pass |
| Human P1 | `DEFERRED_BY_SCOPE` | No | Explicit human-work authorization |

## B0 CPU PASS criteria

1. SCAN/PROPOSE returns 0-N candidates; zero never triggers hidden fallback.
2. Candidate VERIFY is illegal until that candidate is exposed.
3. DirectVerify(region) is distinct, not SCAN plus secret candidate lookup.
4. Policy state contains query and observed evidence but no reference truth.
5. Materialization uses only locally verified relations available at that time.
6. All actions debit one clock; deadline-crossing actions do not mutate state.
7. Identical action/evidence traces score identically for every policy.
8. Tests cover empty, singleton, multiple candidates, illegal access, query
   conditioning, deadline behavior, and exact parity.

A CPU PASS authorizes protocol design only, not inference, physical measures,
human work, or empirical B1-B3 claims.
