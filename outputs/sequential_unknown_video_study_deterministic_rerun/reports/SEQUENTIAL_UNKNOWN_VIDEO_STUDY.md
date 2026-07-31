# Unknown-video sequential SCAN/VERIFY study

## Frozen result

Five candidate policies were compared only on reciprocal realcartest-slice
development folds.  The method frozen before inspecting the primary query
video was:

```text
DYNAMIC_ADAPTIVE_K3_VALUE_V3
```

### Development selection

| method | anytime_event_recall_auc | anytime_event_f1_auc | event_recall | event_f1 | event_precision | selected_before_primary |
| --- | --- | --- | --- | --- | --- | --- |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 0.272 | 0.348 | 0.467 | 0.530 | 0.902 | True |
| DYNAMIC_K3_VALUE_V2 | 0.272 | 0.348 | 0.467 | 0.530 | 0.902 | False |
| FIXED_SCAN1_VERIFY3 | 0.270 | 0.354 | 0.462 | 0.540 | 0.909 | False |
| FIXED_SCAN1_VERIFY1 | 0.249 | 0.329 | 0.438 | 0.511 | 0.860 | False |
| DYNAMIC_PROXY_VALUE_V1 | 0.231 | 0.314 | 0.413 | 0.496 | 0.919 | False |

### Held-out query-bound comparison

| method | budget | scan_actions | verify_actions | returned_event_count | event_precision | event_recall | event_f1 | anytime_event_recall_auc | first_event_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARC_TWO_STAGE_COMMON | 5.000 | 35.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | nan |
| ARC_TWO_STAGE_COMMON | 10.000 | 35.000 | 6.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | nan |
| ARC_TWO_STAGE_COMMON | 20.000 | 35.000 | 16.000 | 0.600 | 0.400 | 0.023 | 0.043 | 0.006 | 13.500 |
| ARC_TWO_STAGE_COMMON | 50.000 | 35.000 | 46.000 | 2.600 | 0.800 | 0.100 | 0.177 | 0.038 | 19.250 |
| ARC_TWO_STAGE_COMMON | 80.000 | 35.000 | 76.000 | 5.600 | 1.000 | 0.215 | 0.354 | 0.084 | 25.900 |
| ARC_TWO_STAGE_COMMON | 100.000 | 35.000 | 96.000 | 7.000 | 1.000 | 0.269 | 0.424 | 0.116 | 25.900 |
| CURRENT_TWO_STAGE_RAW | 5.000 | 35.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | nan |
| CURRENT_TWO_STAGE_RAW | 10.000 | 35.000 | 6.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | nan |
| CURRENT_TWO_STAGE_RAW | 20.000 | 35.000 | 16.000 | 3.000 | 1.000 | 0.115 | 0.207 | 0.026 | 14.500 |
| CURRENT_TWO_STAGE_RAW | 50.000 | 35.000 | 46.000 | 4.000 | 1.000 | 0.154 | 0.267 | 0.099 | 14.500 |
| CURRENT_TWO_STAGE_RAW | 80.000 | 35.000 | 76.000 | 8.000 | 1.000 | 0.308 | 0.471 | 0.158 | 14.500 |
| CURRENT_TWO_STAGE_RAW | 100.000 | 35.000 | 96.000 | 11.000 | 1.000 | 0.423 | 0.595 | 0.204 | 14.500 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 5.000 | 7.000 | 4.000 | 2.000 | 1.000 | 0.077 | 0.143 | 0.040 | 1.100 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 10.000 | 15.000 | 8.000 | 3.000 | 1.000 | 0.115 | 0.207 | 0.060 | 1.100 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 20.000 | 27.000 | 17.000 | 4.000 | 1.000 | 0.154 | 0.267 | 0.092 | 1.100 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 50.000 | 35.000 | 46.000 | 5.000 | 1.000 | 0.192 | 0.323 | 0.130 | 1.100 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 80.000 | 35.000 | 76.000 | 9.000 | 1.000 | 0.346 | 0.514 | 0.187 | 1.100 |
| DYNAMIC_ADAPTIVE_K3_VALUE_V3 | 100.000 | 35.000 | 96.000 | 11.000 | 0.909 | 0.385 | 0.541 | 0.225 | 1.100 |

## Exact execution semantics

- The video starts with zero visible proxy scores and zero labels.
- `SCAN(cell)` reveals proxy scores for one label-blind 10-unit cell.
- `VERIFY(unit)` is legal only after that unit has been scanned and reveals
  exactly that frozen label.
- After every committed action, public state, online calibration and strict K3
  are recomputed before the next decision.
- SCAN costs `0.1` and VERIFY costs `1.0` abstract units.  These are mechanism
  costs, not physical timings.
- Probable publication is disabled because the prior cached calibration found
  no threshold satisfying the 0.80 Wilson lower-bound gate.

## Scientific boundary

The primary video did not participate in candidate selection or posterior
training.  The development derivatives lack prompt/parser hashes and originate
from one source video, so this is a held-out mechanism test rather than broad
generalization evidence.  A physical conclusion requires measured SCAN and
VERIFY costs and the same replay under a real deadline.
