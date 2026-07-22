# Mathematical audit

The posterior is `P(w|h) = 1/|C(h)|` for consistent worlds `C(h)` and zero
otherwise. Since each world includes the complete finite transition tape,
`L(h|w)` is exactly a deterministic indicator. The planner evaluates
`sum_w P(w|h) G(h,a,pi0;w)` over that same support for every SCAN, CONFIRM and
STOP candidate, with no unequal lookahead or realized-future coupling.
SCAN admission uses the unchanged global D2-T `B_S=565` ticks plus reserve
`B_C=138` ticks, not a realized or local empirical duration.
