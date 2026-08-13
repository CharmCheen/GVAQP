# Original costly partial-observation GVAQP problem

For temporal regions (V=\{r_1,\ldots,r_N\}), define the runtime state

\[
s_t=(U_t,O_t,F_t,H_t,R_t),
\]

where (U_t) are unseen regions, (O_t) acquired cheap observations, (F_t) the exposed candidate frontier, (H_t) verified semantic history/event state, and (R_t) remaining resources. Legal actions are

\[
A_t=\{SCAN(r):r\in U_t\}\cup\{VERIFY(c):c\in F_t\}.
\]

`SCAN(r)` pays measured cheap decode/sensing/proxy cost, reads previously unobserved video, obtains an imperfect observation with false positives/false negatives, and may create new candidate opportunities. `VERIFY(c)` is legal only for exposed evidence, pays a larger semantic cost, and reveals an authoritative semantic observation. The policy maximizes expected terminal/anytime utility of the resulting `EventRelation` subject to resources. The problem is not merely ranking a fully pre-existing candidate list.
