# Next-stage state machine

No downstream stage is authorized merely because its code or cached output
exists. Gate authority comes from this file plus a recorded decision in
`EXPERIMENT_DECISION_LEDGER.csv`.

```text
CURRENT: Human P1 = WAITING_HUMAN_REFERENCE
│
├── PASS
│   │
│   ├── Reconcile with existing model-relative P2 diagnostic
│   │   (already complete; INCONCLUSIVE; non-authorizing)
│   │
│   └── Run/define a formal human-grounded P2 killer only if the frozen
│       human result creates a claim not already tested by the cached audit
│       │
│       ├── Generic relevance+coverage explains the human effect
│       │       → query-policy algorithm novelty WEAK; stop escalation
│       │
│       └── Stable residual legal event-aware headroom remains
│               ↓
│              P3 event-aware selection
│               │
│               ├── weak / proxy-specific / non-generalizing
│               │       → stop; reassess thesis
│               │
│               └── strong cross-cluster and cross-proxy gain
│                       ↓
│                      P4 faithful endogenous SCAN substrate
│                       ↓
│                      action-regret prevalence/magnitude/
│                      predictability/downside audit
│                       │
│                       ├── rare, small, or unpredictable
│                       │       → controller remains CLOSED
│                       │
│                       └── non-rare + material + predictable +
│                           positive after physical costs
│                               ↓
│                              P5 controller
│
├── PARTIAL
│       → no automatic escalation
│       → reconcile proxy/query/video heterogeneity
│       → reassess whether the thesis is materialization,
│         acquisition, or only a bounded systems finding
│
└── FAIL
        → close the current geometry/event-evidence-policy mechanism
        → do not run a new formal P2 and do not build P3
        → revisit original theory, materialization validity, or substrate
```

## Current lock state

| Stage | State | Authorized now? | Entry condition |
|---|---|---:|---|
| P1 independent human event utility | `WAITING_HUMAN_REFERENCE` | Human annotation only, with explicit human-work authorization | Two independent annotations, adjudication, frozen reference, then frozen analyzer |
| Existing cached model-relative P2 diagnostic | `COMPLETE / INCONCLUSIVE / NON-AUTHORIZING` | No further run | Retain as negative diagnostic evidence |
| Formal post-human P2 killer | `BLOCKED_BY_P1` | No | P1 PASS and a written unresolved claim not already answered by existing P2 |
| P3 event-aware selection | `BLOCKED` | No | Formal P2 shows stable residual legal headroom |
| P4 faithful endogenous SCAN | `DEFERRED / NOT AUTHORIZED` | No | Strong P3 plus explicit authorization; or a separately approved pivot to test Claim B |
| P5 controller | `CLOSED` | No | P4 shows non-rare, material, cross-video predictable regret after physical costs |

## Gate discipline

- Shadow, automated, cached, model-relative, and reference-aware diagnostic
  outputs may update plausibility but cannot substitute for the required gate.
- A downstream directory existing in the repository is not authorization.
- `PARTIAL` never silently routes to PASS.
- A failed mechanism closes only the scoped mechanism; it does not convert the
  original research question into a universal failure.
- Every new experiment must name the claim ID it tests and the upstream gate
  that authorizes it before execution.

