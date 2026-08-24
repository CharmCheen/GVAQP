# Execution priority and stop conditions

| Priority | Action | Claim defended | Cost | Dependency | Stop condition |
|---|---|---|---|---|---|
| P0 | Bind three fresh videos and prove independence | B1a validity | Low | User/data source | Fewer than three eligible sources |
| P0 | Bind query-conditioned SCAN artifact | B0→B1 transition | Medium | Exact code/weight hash | Missing weight, forced fallback, or query-blind output |
| P0 | Bind verifier/prompt/runtime | Model-relative reference | Medium | Exact model/config | Different candidate/direct semantics |
| P1 | Cost-only calibration and deadline freeze | Fair cost axis | Medium | Execution authorization | Outputs exposed or costs not paired/common |
| P1 | Exhaustive DirectVerify reference | B1a utility | High | Frozen deadlines and verifier | Reference failure rate >10% |
| P1 | Six fixed-policy executions | B1a opportunity | High | Complete reference | Any leakage/parity failure |
| P2 | Frozen analysis and decision | B1a gate | Low | Complete cells | Missing cells or post-freeze modification |

Estimated call counts are deliberately not converted into a claimed execution
cost before input binding. At maximum, the primary analysis contains 1,080
DirectVerify regions plus up to 2,160 candidate verifications; failures and
retries remain charged. This is substantial external computation and therefore
requires explicit execution authorization.

There is no `ccfa.yaml` in the project. The six canonical root state files
remain the project tracker; creating a parallel CCFA tracker is unnecessary for
this gate.
