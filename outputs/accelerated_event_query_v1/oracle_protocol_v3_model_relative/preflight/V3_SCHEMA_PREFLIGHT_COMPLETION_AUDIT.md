# V3 Schema-and-Determinism Preflight Completion Audit

Audit state: `COMPLETE`

Final decision:
`V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED`

Exact execution seal:
`bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`

## Requirement-by-requirement evidence

| Requirement | Status | Authoritative evidence |
|---|---|---|
| Preserve V2 decision/artifacts | Proven | Frozen V2 paths remain unchanged from `eef5050cd`; decision remains `REVISE_ORACLE_PROTOCOL` |
| Model-relative authority/terminology | Proven | Contract, prompt, execution config, and metric-name tests |
| Strict minimal schema/parser | Proven | 94 tests and 11/11 physical strict parses; exact three-key schema; no time key |
| Unknown/parse-failure preservation | Proven by contract/tests | Neither occurred physically; both remain explicit indeterminate outcomes and never negative |
| K3 unit-label eventization | Proven | Frozen config/hash; actual forward/reverse/diagnostic-variant relation hashes identical |
| Five V2 regression cases | Proven | Regression manifest and unchanged V2 raw hashes |
| Frozen high-information sample | Proven | Exactly 11 calls on 5/3/3; all cases/videos/2–4 fps/repeats covered before outcomes |
| Exact frames/model binding | Proven | Model files rehashed; 251 frame occurrences decoded and authenticated |
| Exact user authorization | Proven | Approval SHA `f41aa836…` binds seal and exact 11-call manifest |
| Zero-retry physical execution | Proven | Exactly 11 starts/completions/acceptances; 0 failure, interruption, or retry event |
| Raw/runtime authentication | Proven | 11/11 records validate model-input, runtime, GPU, model, seal, and approval provenance |
| Ledger-to-raw join | Proven | 44 hash-chained events join attempt/session/processed/token/record hashes exactly |
| Same-process reproducibility | Proven | Three pairs match label, processed input, exact raw; one authenticated session per shard |
| Cross-replica reproducibility | Proven | `DALI_u0555` pair matches label, processed input, exact raw; sessions differ |
| Class support | Proven | 10 `not_relevant`, 1 `relevant`; unknown not required |
| Parsed/evidence publication | Proven | 11 parsed artifacts plus authenticated post-run evidence manifest |
| Construct diagnostics | Proven non-gating | Five exact-frame reviews; three polarity disagreements; zero relabel/gate changes |
| Analyzer/finalizer integrity | Proven | Finalizer recomputed exact analyzer metrics/parsed payloads before decision |
| Exactly one allowed decision | Proven | Decision file contains only `V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED` |
| Full-grid authorization | Not granted | PASS explicitly requires a new proposal, seal, independent review, and user approval |
| Downstream authorization | Not granted | Full labels/EventRelation do not exist; YOLO/replay/headroom/controller work remains forbidden |
| Full-grid proposal | Reviewed proposal only | Revision 1 `REVISE`; exact revision 2 independently returned `GO_TO_PREPARE_FULL_GRID_PREREGISTRATION`; no implementation/input expansion/compute authority |

## Physical accounting

- Calls: 11 expected / 11 observed.
- Attempt ledger events: 44 successful / 0 failed or uncertain.
- Labels: 10 `not_relevant`, 1 `relevant`, 0 `unknown`, 0 parse failure.
- Frames submitted: 251.
- Total inference: 201.694162 seconds.
- Actual compute including model loads and call overhead: 0.1517243908 A100
  GPU-hours.
- Retries: 0.

## Commands completed

```text
python -m pytest -q tests/accelerated_event_query
  -> 94 passed

PYTHONPATH=src python scripts/run_accelerated_event_query_oracle_v3_preflight.py \
  --execution-shard DALI --declared-physical-gpus 1,2 --validate-only
PYTHONPATH=src python scripts/run_accelerated_event_query_oracle_v3_preflight.py \
  --execution-shard HANGZHOU --declared-physical-gpus 3,5 --validate-only
PYTHONPATH=src python scripts/run_accelerated_event_query_oracle_v3_preflight.py \
  --execution-shard WUHAN --declared-physical-gpus 6,7 --validate-only
  -> all PASS

CUDA_VISIBLE_DEVICES=1,2 ... --execution-shard DALI --compute-approval <bound approval>
CUDA_VISIBLE_DEVICES=3,5 ... --execution-shard HANGZHOU --compute-approval <bound approval>
CUDA_VISIBLE_DEVICES=6,7 ... --execution-shard WUHAN --compute-approval <bound approval>
  -> exact 5/3/3 physical execution; all exit 0

PYTHONPATH=src python scripts/analyze_accelerated_event_query_oracle_v3_preflight.py
PYTHONPATH=src python scripts/decide_accelerated_event_query_oracle_v3_preflight.py
  -> authenticated PASS decision
```

## Completion conclusion

The authorized V3 preflight objective is complete and verified. The protocol
survived the decision-focused pilot. The evidence does not establish
representative three-video adequacy, because the sample is targeted and sparse
in positive/unknown/failure outcomes. The next action may only be a separately
authorized implementation, freeze, preregistration, and seal of the now-reviewed
full-grid proposal. No additional compute, input expansion, or downstream
inference is authorized by this result or by the proposal review.
