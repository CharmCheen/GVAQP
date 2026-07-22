# Risk-limiting provisional interval pruning

The frozen interval tree has disjoint frontier blocks. POSITIVE and UNKNOWN
blocks are recursively resolved; a model NEGATIVE enters a provisional-prune
population `P` and remains statistically visible. COUNT may order work but
cannot remove a block.

For every `h in P`, `R_h` is the number of undiscovered unique canonical
anchors assigned to the half-open block. A fixed audit samples blocks with known
inclusion probability and fully unit-audits every sampled block. Events observed
by that audit become discovered; unaudited blocks remain covered by a residual
upper bound. Blocks must be disjoint or use a separately frozen unique anchor
assignment before sampling.

The formal B2 design is simple random sampling without replacement. B3 freezes
strata from block length and public proxy before audit outcomes. B4 dual cover is
not implemented because no overlap/anchor-assignment design was preregistered.
