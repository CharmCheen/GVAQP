# Independent Adversarial Review — Staged Seal V2

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

- Exact execution seal SHA-256: `2bcac47886e4029dae67b3fcc42bb87c24f65f765d945d4fc7020dfd4f59116d`
- Exact review bundle SHA-256: `959f648d17cdea07ffe99499acf0b27546908cb755e6d8e5ea2cc072f9afea43`
- Source commit: `0d8b6248fdde323df938e0351380774df4926a11`

Decisive counterexample: after W0 spawned, the W1 authentication callback
atomically changed the global state to `STOPPED` and then returned a valid
idle snapshot. The supervisor used its stale loop-top `READY` observation and
spawned both W1 and W2 while the durable global state was already `STOPPED`.
It detected fail-stop only on the next loop. This violates the frozen rule
that an activated-worker fault prevents every future pending activation.

Observed spawn sequence:

```text
W0 -> spawned while READY
W1 -> spawned while STOPPED
W2 -> spawned while STOPPED
```

No formal execution root, model load, or model inference existed during this
review. The exact seal and bundle are rejected and must not authorize compute.
