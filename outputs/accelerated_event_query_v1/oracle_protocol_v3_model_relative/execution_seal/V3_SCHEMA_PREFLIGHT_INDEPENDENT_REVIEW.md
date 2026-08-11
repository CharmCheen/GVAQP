# V3 Schema Preflight Independent Review

Final verdict: `GO`

Exact execution seal SHA-256:
`bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`

Exact source commit:
`921fa8b9c0e90fbeee4365aa41d813be9bf2df8f`

Preregistration SHA-256:
`89fc2d0d57f09d3e24c6c6e57f3e6c15c47bc402bb1f31af9b0d30455e3b732f`

Pre-execution provenance SHA-256:
`530b4314af4a3a49ad9b9998b7b6ad587d0d17041fff6905726f21fda6863e3d`

## Review history

The independent reviewer issued `NO-GO` for obsolete seal `84d352fb…` after
finding incomplete raw/runtime authentication, missing ledger-to-raw joins,
incorrect processed-input decision precedence, unauthenticated same-process
membership, and incomplete parsed/provenance publication. That seal is invalid
and must never be approved.

The repaired package added recomputed model-input identity; exact
runtime/GPU/model/approval checks; attempt/session/processed-token/record joins;
durable same-process and cross-replica session rules; corrected input-binding
precedence; per-call parsed outputs; frozen pre-execution and write-once post-run
evidence manifests; explicit 2/4-fps reporting; exact evidence schemas and
membership; and read-only analyzer recomputation by the decision finalizer.

## Independent verification of the final seal

- DALI/HANGZHOU/WUHAN validate-only runs independently passed at `5/3/3`.
- All checkpoint manifests were rehashed and every frozen frame input was
  redecoded; repeat and cross-replica model-input identities matched.
- The focused test suite independently passed: `94 passed`.
- Seal, preregistration, provenance, source, model, prompt, schema, parser,
  runner, analyzer, finalizer, K3, frame, schedule, and mapping bindings match.
- Frozen V2 evidence has no diff from commit `eef5050cd`.
- No V3 compute approval, raw generation output, attempt ledger, or parsed
  result exists.
- No remaining blocker was found.

## Authority boundary

This `GO` authorizes only requesting explicit user approval for the unchanged
11-call, 5/3/3, zero-retry V3 schema-and-determinism preflight. It is not compute
approval. It does not authorize the 1,475-unit full grid or any YOLO ceiling,
replay, headroom, or controller claim.
