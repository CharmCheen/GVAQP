# Full pipeline smoke report

SOFTWARE_PIPELINE_SMOKE = PASS

Mode: replay using the repository's checked-in example-style frozen candidate/outcome contract; no Oracle call and no model inference.

Verified order: SCAN -> candidate generation -> Frontier admission/deduplication -> fixed 25:75 choice -> replay CONFIRM adapter -> parsing -> materialization -> utility deduplication -> fsync/atomic durable commit -> FINAL/STOP.

INJECTED_TEST_FIXTURE = true (integration-only; it proves software-chain execution, not detector or VLM quality).
REAL_VLM_PIPELINE_SMOKE = BLOCKED_MISSING_MODEL_ID_AND_BACKEND.
