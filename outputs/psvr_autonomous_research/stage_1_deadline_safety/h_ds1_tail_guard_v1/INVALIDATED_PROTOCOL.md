# H-DS1 v1 Protocol Status

`INVALID_PROTOCOL_DIAGNOSTIC_ONLY`

The single physical sample is retained as negative evidence. Its 14.525 s commit
included a fresh Python process, pandas/scipy import, frozen K3 import, chroot,
and UID/GID drop on every commit. That is not the deployed Regime-B workload,
where the isolated materializer is initialized before the deadline and K3 is
invoked through a persistent evidence-only capability.

Nothing in this directory may enter a tail profile or be resumed. The physical
VERIFY observation remains useful as a diagnostic, but it is not mixed into the
new workload identity. The replacement experiment is
`h_ds1_tail_guard_v2_persistent_k3`.
