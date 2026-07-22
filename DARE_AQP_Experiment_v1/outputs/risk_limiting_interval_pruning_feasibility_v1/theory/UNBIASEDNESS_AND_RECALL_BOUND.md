# Unbiasedness, variance and recall bound

Conditional on arbitrary frozen ANY outputs and discovery history, the block
population and all `R_h` are fixed. Under independent Bernoulli sampling,

`R_hat = sum_h I_h R_h / pi_h`

is conditionally unbiased because `E[I_h | P]=pi_h`. Its conditional variance
is `sum_h (1-pi_h) R_h^2/pi_h`; the usual pairwise-inclusion covariance term is
added for dependent designs.

For SRSWOR of `n` among `H` blocks, `R_hat=(H/n) sum_sample R_h` and
`Var(R_hat)=H^2(1-n/H)S_R^2/n`. Stratified HT sums the corresponding stratum
estimators and variances. Repeated inference on a block is not an independent
population unit.

The simulation uses a distribution-free one-sided Serfling bound. With values
in `[0,b]`,

`mean_R <= sample_mean + b sqrt((1-(n-1)/H) log(1/delta)/(2n))`.

Stratified bounds use Bonferroni `delta/J`. The total upper bound is capped by
the deterministic sum of block lengths. After subtracting sampled/discovered
anchors, call the remaining bound `U_P`. With `D` discovered events, the safe
recall lower bound is `D/(D+U_P)`. This is valid without independence or uniform
placement of model errors; only audit randomization is stochastic.
