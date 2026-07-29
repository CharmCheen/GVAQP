# Accelerated Event Query Next Decision

Current loop decision: `REVISE_ORACLE_PROTOCOL` (not a terminal research decision).

Independent review showed that the V1 preflight could produce a false pass and did not present reviewers and Qwen with identical frames. It is preserved as rejected before execution. V2 now has exact frame and model identities, an explicit 32-call manifest, end-to-end processed-tensor authentication, exact no-retry generation accounting, a mandatory user-approval artifact, complete positive-claim grounding, and a frozen finalizer.

The replacement seal at commit `b09f99974` passed independent re-review. The reviewer also injected a processed-input mismatch and observed fail-closed behavior. All 51 focused tests and the CPU-only 10/11/11 shard validations pass; raw outputs and attempt ledgers remain zero.

The highest-value next action is therefore explicit user approval or rejection of the exact targeted pilot. Approval covers only 32 physical generations (24 base, six 4-fps sensitivity, and two cross-replica anchors) on three disjoint two-GPU replicas. Any uncertain or failed generation stops the run and cannot be retried automatically. A completed run still cannot pass until every unique positive claim receives the frozen independent visual grounding review.

The pilot is estimated at 0.44 A100 GPU-hours before model-load and preprocessing overhead. If it passes, the next action is to design and separately approve a larger reproducible content-blind audit—not to launch the full 1,475-unit oracle. If it fails, route the observed failure through the frozen numeric, reproducibility, sensitivity, semantic, or grounding gate and do not proceed to controller work.
