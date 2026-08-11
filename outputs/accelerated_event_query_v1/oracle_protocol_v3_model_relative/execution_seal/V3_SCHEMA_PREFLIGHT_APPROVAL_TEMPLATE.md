# V3 Schema Preflight Compute Approval Template

Status: `NOT_APPROVED_TEMPLATE`

No Qwen3-VL-32B inference is authorized by this template. After independent
review, the user must explicitly approve the unchanged sealed experiment.

- Execution seal SHA-256: `bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`
- Authorized call manifest SHA-256: `081fcd5ac8212649d9f998bb0aaabccd2787a12efc09b1b0a919795ea23a6288`
- Exact physical calls: `11`
- Estimated compute: approximately `0.19 A100 GPU-hours` plus normal host overhead
- Retry budget: `0`
- Full-grid authorization: `none`

Only after explicit approval, create
`execution_seal/V3_SCHEMA_PREFLIGHT_COMPUTE_APPROVAL.json` with exactly:

```json
{
  "status": "APPROVED_BY_USER",
  "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_SCHEMA_PREFLIGHT",
  "execution_seal_sha256": "bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61",
  "authorized_call_manifest_sha256": "081fcd5ac8212649d9f998bb0aaabccd2787a12efc09b1b0a919795ea23a6288",
  "approved_physical_call_count": 11,
  "approval_scope": "exactly the 11 sealed V3 schema-and-determinism preflight calls; zero retry; no full-grid or downstream execution",
  "user_approval_evidence": "FILL_WITH_EXACT_USER_APPROVAL_REFERENCE"
}
```

Abort rather than execute if any bound input, source, checkpoint, prompt,
schema, parser, schedule, analyzer, decision mapping, or seal differs.
