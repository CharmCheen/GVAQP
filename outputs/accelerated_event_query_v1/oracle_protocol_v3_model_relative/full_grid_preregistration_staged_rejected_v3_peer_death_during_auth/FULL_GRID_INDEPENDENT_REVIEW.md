# Independent Adversarial Review — Staged Seal V3

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

- Exact execution seal SHA-256: `c0094a5135136111afad31dfce288cdd6ada49095af1d7c5bc1fe086058aa3aa`
- Exact review bundle SHA-256: `9dbe57b49d025fde959a786d7907d31a07bab9e9fb4b59bd6f651220981b07cd`
- Source commit: `ecadfb3e4bf539c152193c8766d793a7c6bb838b`

Decisive counterexample: W0 died with return code `-9` during W2's
pending-pair GPU authentication, after the loop-top health poll. Since no
actor had yet persisted global `STOPPED`, the activation helper read `READY`
and spawned W2. The next loop then observed W0's death and stopped globally.

```text
spawned = [(W0, READY), (W2, READY)]
next failure = abrupt_worker_exit:W0:returncode=-9
final state = STOPPED / post_load_process_fault
```

The two earlier staged races were independently confirmed fixed, but this
distinct peer-liveness race violates the frozen rule that active-worker death
prevents later activation. No formal execution root, model load, or inference
existed during review. This exact seal and bundle are rejected.
