# Independent Temporal-Order Opportunity Probe Contract V1

Status: `PROTOCOL_FROZEN_INPUTS_UNBOUND`
Freeze time: 2026-08-07T04:47:18Z
Branch/commit at freeze: `dspro` / `620378413b1f5f3cd3ed304e701fc480d8d17ba3`
Experiment ID: `INDEPENDENT_TEMPORAL_ORDER_PROBE_V1`

This contract freezes the protocol before a new source is bound or semantically opened. It authorizes no new oracle calls and no experiment execution while the source or hardware bindings remain `TBD_NOT_BOUND`.

## 1. Decision question

On one independent continuous long driving video, under one frozen physical hard-deadline contract, does a deterministic label-blind temporal-bisection SCAN order recover frozen-oracle-relative distinct events earlier and recover at least one more distinct event by the deadline than chronological fixed interleaving and scan-then-verify?

This is Gate O: a fixed-order opportunity probe. It is not a test of adaptive scheduling, MAB, learned prediction, or controller quality.

## 2. Frozen query and semantic oracle

Primary query: `Q1 / OTHER_VEHICLE_ENTERS_EGO_PATH`.

Operational semantics are exactly `DENSE_PRESENCE_STRICT_V13_6` in `configs/prompts/confirm_visual.yaml`, SHA-256 `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`.

All quality is relative to the frozen Qwen oracle, not human truth:

- model: `Qwen/Qwen3-VL-32B-Instruct`;
- model/revision manifest: `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`;
- revision: `0cfaf48183f594c314753d30a4c4974bc75f3ccb`;
- backend: Transformers, bfloat16, `device_map=auto`;
- video sampling: 2 fps, RGB, decoded end inclusive;
- generation: greedy, `do_sample=false`, `temperature=null`, `max_new_tokens=256`;
- parser: strict presence-compatible JSON parser, parser source hash `c02b545c0c5d2969508eea9a5470f0cb67d71282b25059948106504f9f4edd31`;
- labels: positive, negative, abstain; unknown/parse failure/timeout never become negative silently.

No prompt, parser, model, clip sampling, or decode parameter may change after source A is bound.

## 3. Unit, SCAN, VERIFY, and action legality

### Unit grid

- Non-overlapping 10-second units from video time zero.
- Only the final unit may be shorter.
- Unit IDs are contiguous chronological integers from zero.
- Ten consecutive units form one SCAN cell; only the final cell may contain fewer units.

### SCAN

The SCAN operator is the frozen Q1 YOLOv8n physical proxy in `outputs/psvr_two_video_loop/final_proxy/FINAL_PROXY_CONFIG.json`:

- YOLOv8n weight hash `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`;
- resolution 640, sample rate 5 fps, confidence 0.25, NMS IoU 0.45;
- selected proxy family `YOLOV8`, query head Q1;
- one physical SCAN processes one complete 10-unit cell and durably publishes all unit proxy scores/candidates from that cell.

SCAN output is public only after its durable commit.

### VERIFY

VERIFY runs the frozen oracle on exactly one already-SCAN-exposed 10-second unit. The target is always the highest proxy score among exposed, unverified units, with ascending unit ID as the deterministic tie-break.

`VERIFY(c)` is legal iff:

1. the SCAN cell containing `c` has durably committed;
2. `c` is present in the public exposed frontier;
3. `c` has not previously been verified in this run;
4. the deadline admission guard admits the complete VERIFY plus durable commit tail.

No method may verify an unscanned candidate or access reference labels, future proxy rows, future costs, or another policy's observations.

## 4. Frozen K3 / EventRelation

Primary output is verified-only. `PROBABLE_EVENT`, RC-SEM speculative publication, and REFINE are disabled.

Materializer: `k3_bridge_safe` / consecutive verified-positive units with:

```text
g_max = 1
d_core_max = 40.0 seconds
d_seg_max = 60.0 seconds
```

The evaluator is the frozen one-to-one event evaluator with SHA-256 `0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610`. Reference events are produced by exhaustive application of the same frozen oracle and materializer in an evaluator-only process. The reference is sealed and unavailable to every runtime policy.

## 5. Physical workload and timing boundary

Workload view: warm oracle, cold per-run proxy/query state.

- Model load and one fixed warm-up occur before `run_start`; cold-load time is reported separately and is not part of primary D.
- Every policy/repetition starts with empty SCAN state, empty frontier, zero VERIFY observations, empty K3/EventRelation, and a fresh output directory.
- Primary action-cycle wall time starts immediately before deterministic policy selection and ends only after the selected action, state update, K3 materialization, snapshot serialization, fsync, and atomic rename have completed.
- SCAN time includes scheduling, validation, seek/decode, detector/tracker/proxy computation, frontier update, K3 update, snapshot, fsync, and atomic commit.
- VERIFY time includes scheduling, validation, clip decode/sampling, VLM preprocessing/generation/parsing, frontier update, K3/EventRelation materialization, snapshot, fsync, and atomic commit.
- Post-deadline results do not enter utility. Overrun actions remain in the intention-to-run and cost ledger.

Target hardware identity must be bound before source A reference generation or policy execution. All nine primary runs use the same bound GPU/model bytes/software environment.

## 6. Deadline freeze rule

The exact source-A deadline is derived once, before semantic reference inspection or policy execution, from a method-independent physical preflight on the bound hardware:

```text
D_min = SCAN_q95 + VERIFY_q95 + COMMIT_q95 + 1.0 second
D_transition = 0.9765756132103428 * FULL_PROXY_PASS_p50
D = max(D_min, D_transition)
```

`FULL_PROXY_PASS_p50` uses three complete proxy-only timing runs on source A. Proxy outputs are sealed and cannot be inspected for policy or threshold changes. VERIFY q95 must come from the frozen same-oracle hardware profile or a source-independent calibration clip; it must not use source-A semantic outcomes. The derived numeric D and all component values are written and hashed before any primary run.

No policy outcome may alter D.

## 7. Deterministic policies

The only policies are:

### A. `CHRONOLOGICAL_FIXED_SCAN1_VERIFY1`

- SCAN cell order: `0, 1, ..., m-1`.
- Start with SCAN.
- After each completed SCAN, execute one legal highest-proxy VERIFY.
- If the required action is inadmissible, use the other action only if legal; otherwise STOP.

### B. `TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1`

- Cell order is generated once from cell count `m` by breadth-first interval bisection.
- Initialize queue with `[0, m-1]`.
- Pop `[l,r]`; if nonempty emit `floor((l+r)/2)`, then append `[l,mid-1]` and `[mid+1,r]`.
- The order depends only on `m`; it cannot use video content, proxy output, oracle output, or cost outcomes.
- SCAN/VERIFY alternation, VERIFY target, legality, admission and fallback are identical to policy A.

### C. `CHRONOLOGICAL_SCAN_THEN_VERIFY`

- SCAN cells chronologically until every cell has committed or no SCAN is admissible.
- Only after all cells are scanned may it execute highest-proxy legal VERIFY actions.
- If full scan cannot complete within D, it returns the last verified-only durable snapshot; it does not switch early based on outcomes.

A versus B is the primary order isolation. C is the staging/interleaving diagnostic.

## 8. Snapshot and run schedule

A durable snapshot is written:

1. at run initialization (`t=0`, empty relation);
2. after every completed SCAN;
3. after every completed VERIFY;
4. at STOP/deadline using the last durable state.

Three physical repetitions are run per policy in this frozen Latin-square order:

```text
replicate 0: A, B, C
replicate 1: B, C, A
replicate 2: C, A, B
```

No output directory, model process, frontier, posterior, cost estimator, or snapshot state is reused across runs. Oracle caching may not bypass physical inference.

## 9. Metrics

Primary view: equal wall-clock time on `[0,D]`.

For right-continuous verified-only event recall `R(t)`:

```text
AnytimeEventRecallAUC = (1/D) * integral_0^D R(t) dt
```

The same right-continuous normalized integral is computed for Event-F1(t). Commit time, not action start time, changes utility.

Required metrics:

- Anytime Event Recall AUC (primary);
- Anytime Event-F1 AUC;
- terminal distinct-event recall and Event-F1 at D;
- confirmed distinct events at D;
- SCAN cell/unit coverage;
- VERIFY calls and determinate/positive counts;
- first discovery time for every matched reference event;
- time to first confirmed event;
- SCAN, VERIFY, scheduler, materialization, serialization/fsync and total wall-clock breakdown;
- deadline rejection, overrun, miss and post-deadline commit counts.

Equal-call is diagnostic only. It compares event recovery after each common VERIFY-call count using the same physical traces. It cannot support a deadline-gain claim.

## 10. Preregistered decision mapping

Let B be temporal bisection and `S=max(A,C)` be the stronger comparator by mean primary equal-time Recall AUC. Freeze practical thresholds:

```text
epsilon_auc = 0.01 absolute normalized Recall-AUC
epsilon_events = 1 additional confirmed distinct event at D
replication_direction = B Recall-AUC > S in at least 2 of 3 paired repetitions
```

- `O_POSITIVE_EXPLORATORY`: mean `AUC_B - AUC_S >= 0.01`, B recovers at least one additional confirmed distinct event at D, direction passes in at least 2/3 repetitions, and B has no additional deadline miss/post-deadline commit. This supports temporal order as an execution primitive only; it does not support adaptivity.
- `O_ALGORITHM_SIGNAL_PHYSICAL_NO_GO`: equal-call B satisfies the analogous order advantage, but equal-time B fails the positive gate. Diagnose physical cost; do not start MAB/controller work.
- `O_NEGATIVE`: mean `AUC_B - AUC_S <= 0` or B recovers fewer terminal distinct events. Remove temporal-bisection as a core mechanism claim. This does not logically imply reachable adaptive headroom H is zero.
- `O_INCONCLUSIVE`: all remaining cases, including a positive delta smaller than the frozen practical thresholds. No mechanism claim; do not tune bisection on source A.

After the O decision is emitted, source A automatically changes from `opportunity_probe` to `development`. It must never again be called held-out or confirmation data.

## 11. Forbidden until O is closed

No MAB, epsilon-greedy, UCB, Thompson sampling, learned predictor, action-value model, RL/SMDP, dynamic controller, REFINE, probable-event publication, proxy retuning, K3 retuning, policy threshold search, expanded action space, or broad physical matrix.

Any engineering repair is limited to path/schema/accounting/hash/integrity/determinism errors, creates an amendment record, and reruns all affected policies from empty state. A repair may not alter policy semantics or be selected using quality outcomes.

## 12. Source roles

- Existing videos: hypothesis generation only.
- New video A: one-shot Gate O probe; automatically development after O.
- New videos B/C: future H/L/R confirmation; remain unopened and unprocessed.

The source-role registry is `outputs/independent_temporal_order_probe_v1/contracts/source_roles.json`. Execution remains blocked until A/B/C are hash-bound, independence/provenance is recorded, target hardware is bound, and the final freeze manifest reports `READY_FOR_EXECUTION`.
