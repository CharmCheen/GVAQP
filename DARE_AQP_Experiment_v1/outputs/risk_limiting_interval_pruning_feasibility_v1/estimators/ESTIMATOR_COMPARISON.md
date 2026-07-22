# Estimator and confidence-method comparison

- Exact hypergeometric inversion is valid when the sampled population value is
  binary, such as “block contains at least one residual event.” It does not
  upper-bound the total event count when a block can contain multiple anchors
  without an additional multiplicity bound. It is therefore diagnostic here.
- Horvitz–Thompson is conditionally unbiased for total residual anchor count
  under known nonzero inclusion probabilities, but an unbiased point estimate
  alone is not a recall certificate.
- SRSWOR HT plus a one-sided Serfling upper bound is the primary B2 method.
- Stratified HT plus per-stratum Serfling bounds with Bonferroni allocation is
  the primary B3 method.
- Sequential/anytime methods are not used. A future multistage design requires
  frozen alpha spending or a valid confidence sequence.

The simulator reports HT bias, empirical coverage, bound width and certificate
rate separately. A cell cannot pass merely because empirical recall is high.
