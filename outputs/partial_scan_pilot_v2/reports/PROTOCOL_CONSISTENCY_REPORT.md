# V2 Application Protocol Consistency Report

Scope is application IPC, public schemas, and runtime accounting only.

`ACTION_RESPONSE_FIELDS = step_id, unit_id` and response objects use exact-key
validation. The request step must match exactly; a unit must be in the current
unscanned public-unit set. Extra fields, missing fields, stale or future steps,
unknown units, already-scanned units, and a duplicate response after acceptance
are rejected as `POLICY_PROTOCOL_ERROR` at the public boundary.

The unused `ACTION` message-type constant has been removed. `step_id` remains
present in requests, public state, and responses. The worker, public schema,
isolated client, ReplayEnvironment, and Physical runner use the same response
shape.

Constructed-message tests passed: valid response; missing, stale, future,
unknown, already-scanned, extra-field and duplicate responses; malformed JSON;
policy timeout; and redacted internal exceptions.

`APPLICATION_PROTOCOL_SEPARATION = PASS`

This result is application-level protocol separation only. It is not a claim of
malicious-policy containment or runtime isolation.
