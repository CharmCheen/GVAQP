# Completion Audit

| check | passed |
| --- | --- |
| CASQ V12.1 read | True |
| v1 VLM audit imported into v2 with provenance | True |
| External label mapping updated to LOOSE_APPROXIMATION / AUDIT_UNRELIABLE | True |
| Section 23.2 bound invariants implemented | True |
| row-level block audit table persisted | True |
| candidate dev/report split used | True |
| no event-boundary leakage in candidate generation | True |
| representation candidate run or explicitly unavailable | True |
| selectivity report generated | True |
| single-dataset claim scope applied | True |
| final report exists | True |
| final decision line exists exactly once | True |
| all required tables exist or explicitly N/A | True |
| token leak check passed | True |
| python -m py_compile passed | True |

Final decision:

```text
NEXAR_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)
```
