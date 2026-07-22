# H-ROLLOUT1B planning time and fallback semantics

Planning time is an SMDP action cost, not a side-channel measurement. Before an override, the planner consumes `P` ticks from the same 1600-tick horizon; `P` is one of `0, 2, 5, 10, 20`. The post-planning action is selected only from actions still legal after that elapsed time. If planning exhausts the deadline, the environment STOPs; there is no implicit flush.

The predeclared policy set is shielded pi0; approximate rollout without fallback; approximate rollout with point-estimate fallback; LCB-gated rollout; and planning-admission plus LCB fallback. LCB policies override pi0 only when `LCB_0.95(D_hat(a)) > b_model + epsilon_overhead`, where `b_model = 0.20 * HORIZON_TICKS` only for a joint-corner error condition and zero otherwise, and `epsilon_overhead = P`. Planning admission uses the same inequality before consuming planning time; otherwise it executes immediate pi0.

Required net-cost outcomes are break-even planning cost, net utility after planning, unused deadline, late-CONFIRM opportunity loss, and plan-admission frequency.
