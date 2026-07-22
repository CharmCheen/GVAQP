
# Mathematical identities and assumptions

## AUC audit

For right-continuous staircase utility, partitioning at commit times proves `integral u = u(0)T + sum Delta u_k(T-t_k)`. Here `u(0)=0`. With F1, `Delta u_k` is set-dependent; the event surrogate is not algebraically equivalent to AnytimeAUC_F1.

## SMDP recursion

`V^pi(I,rho)=E_pi[integral_0^rho u(I_z) dz]` and, for an admissible action with duration `tau_a<=rho`, `Q^pi(I,a,rho)=E[u(I)tau_a+V^pi(I',rho-tau_a)]`. Subtracting the constant current-utility area yields the incremental form `bar Q^pi=E[Delta u(I,a,I')(rho-tau_a)+bar V^pi(I',rho-tau_a)]`. Boundary convention: an action completing exactly at T is complete, but has zero remaining-horizon event surrogate; an overrun is inadmissible and never truncated into success.

## Ideal rollout claim boundary

One-step policy improvement is invoked only with an exact transition model, exact expected values, a proper pi0, inclusion of pi0's own action in the candidate set, full-horizon continuation (or exact terminal value), and zero physical planning cost. It is a method hypothesis until run. With approximate action values satisfying `||Qhat-Q||_infinity<=epsilon`, selecting the Qhat maximizer loses at most `2 epsilon` in that one decision: `Q(a*)-Q(ahat)<=2epsilon`. This is not a trajectory guarantee, finite-sample no-harm theorem, or physical no-harm result.

## Bibliographic verification

- Dimitri P. Bertsekas and John N. Tsitsiklis, *Neuro-Dynamic Programming*, Athena Scientific, Belmont, MA, 1996, ISBN 1-886529-10-8 / 978-1-886529-10-6. Metadata checked against the authors' MIT-hosted book front matter: https://web.mit.edu/dimitrib/www/NDP.pdf
- Dimitri P. Bertsekas, John N. Tsitsiklis, and Cynara Wu, “Rollout Algorithms for Combinatorial Optimization,” *Journal of Heuristics* 3(3), 245–262, 1997, DOI 10.1023/A:1009635226865. Metadata checked against the authors' paper and DBLP: https://faculty.engineering.asu.edu/bertsekas/wp-content/uploads/sites/129/2020/03/rollout.pdf and https://dblp.org/rec/journals/heuristics/BertsekasTW97

Neither citation licenses stronger claims outside its assumptions.
