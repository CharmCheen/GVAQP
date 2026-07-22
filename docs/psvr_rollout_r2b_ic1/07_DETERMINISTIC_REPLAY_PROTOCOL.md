# Deterministic replay

The independent verifier checks evidence and sidecar hashes without importing the production executor, paired model, exact evaluator, or metric aggregator. It independently recomputes every A4 keyed uniform, inverse-CDF baseline and perturbed outcome, A1/A2 sign, transition hash, paired difference, mean, variance, LCB, selected-action threshold, and full-horizon utility timeline from the compact evidence. Exact evaluator sidecars remain evaluator-only diagnostics and are checked structurally by this verifier.
