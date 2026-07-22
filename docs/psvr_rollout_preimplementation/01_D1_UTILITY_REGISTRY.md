
# D1 — Utility registry

Status: `COMPLETE_FROZEN`.

The main problem starts with an empty committed set, so `u(0)=0`. The general staircase identity may contain `u(0)T`, but that term is identically zero here and is not a design contribution. If commits occur at `0<t_1<...<t_K<=T`, with `Delta u_k=u(t_k+)-u(t_k-)`, then

`integral_0^T u(t)dt = sum_k Delta u_k (T-t_k)`.

This holds for any durable staircase utility. It does not make rewards state-independent: for F1, each increment depends on the entire committed set.

The algorithm surrogate is `sum_e in TP (T-tau_e)_+ - lambda sum_f in FP (T-tau_f)_+`, with primary `lambda=1` and preregistered auxiliary sensitivities `0,2`. `tau` is first durable commit time. Duplicate reward and post-deadline reward are zero. The committed set is append-only; identity, interpretation, and interval cannot be revised, revoked, or post-hoc merged. Boundary enhancement is excluded.

The surrogate is not the paper metric. Primary evaluation is AnytimeAUC_F1, time-weighted unique-event utility, TTFC, unique events, precision, and recall; mechanism, rollout, and safety diagnostics are enumerated in `UTILITY_REGISTRY.json`.

Planning changes no committed state while it runs. Its duration shortens the remaining horizon, so it is charged naturally through AUC; rollout admission and action choice must use net planning-aware value rather than a cost-free value followed by feasibility alone.
