# B1a CPU preregistration preflight

## Decision

`B1A_PROTOCOL_FROZEN_EXECUTION_BLOCKED_INPUTS_UNBOUND`

The protocol is internally frozen and result-neutral. Exactly six inherited
queries match the discovery registry byte-for-byte; three ordered fresh-video
slots exist; no semantic execution was performed.

## Blocking inputs

- fresh inputs are not bound
- three eligible fresh video hashes are absent
- query-conditioned SCAN implementation/artifact/runtime is unbound
- semantic verifier/prompt/runtime is unbound
- external execution is not authorized

## Planned scale

- 3 fresh independent videos × 6 queries = 18 workloads.
- 60 analysis regions per video.
- 1,080 exhaustive DirectVerify calls.
- At most 2,160 primary candidate-VERIFY calls.

These counts show why “continue” should not silently trigger external compute.
Binding and execution require a separate, hash-complete authorization.

## Scientific disposition

The next action is input binding, not algorithm design. If eligible videos or a
query-conditioned scanner cannot be bound, B1 remains blocked. Human annotation
is not required by this model-relative B1a protocol.
