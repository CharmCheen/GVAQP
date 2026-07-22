# Planning cost and admission

Planning consumes a real visible horizon transition before any samples are used.
If remaining time is not strictly larger than the frozen cost, the policy skips
planning and acts through current pi0. The post-planning base action is always
recomputed.
