# Exact posterior and conditional rollout

The R2 prior is the uniform distribution over 288 finite fully materialized
worlds. The exact posterior enumerates that entire library and renormalizes the
consistent worlds. This is enumeration, not particle filtering, rejection
sampling, learned inference, or a realized-world shortcut.

For every legal candidate action, M1 sums its full-horizon D1 future utility
over the same posterior worlds, executes the candidate once, then invokes the
same closed-loop shielded pi0 on each simulated visible history. STOP has its
durable current value. Planning never receives the actual environment object.
