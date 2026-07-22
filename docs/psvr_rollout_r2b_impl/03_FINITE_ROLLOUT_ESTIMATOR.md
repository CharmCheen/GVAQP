# Finite rollout estimator

The paired model API supplies aligned return vectors for candidate and current
base actions. The estimator computes their elementwise difference, mean, sample
standard deviation and fixed 95% normal LCB. All alternatives share the same
model-owned paired draw protocol.
