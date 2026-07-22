# Sequential validity

Version 1 is fixed-stage. The audit fraction and design are frozen before audit
labels are opened; the same data are not repeatedly tested until a favorable
bound appears.

A future multistage design must either allocate the total 0.05 error probability
across looks before execution or use an anytime-valid confidence sequence with
known inclusion propensities. Reopening a sampled negative block is mandatory:
the complete block audit discovers its anchors and charges every unit call, but
does not authorize changing inclusion probabilities for already frozen stages.
Adaptive later stages must condition only on recorded history and preserve
positive inclusion probability for every remaining provisional block.
