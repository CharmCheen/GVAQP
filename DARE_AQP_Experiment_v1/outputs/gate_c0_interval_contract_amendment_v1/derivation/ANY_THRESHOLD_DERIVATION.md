# ANY threshold derivation

The frozen 347-unit/26-anchor hierarchy was replayed with synthetic effective
ANY errors before any physical response existed. The grid crosses sensitivity,
specificity, UNKNOWN rate, independent errors, multi-event adversarial false
negatives and boundary-concentrated false negatives.

At the registered optimistic constant-cost cell, only two conservative cells
pass all placements: sensitivity 1.00, UNKNOWN 0, and specificity 0.99 or 1.00.
Their worst cost ratios are 0.675072 and 0.640490. Any adversarial false negative
can remove enough anchors to violate 80% recall, so the maximum is zero. At the
registered alpha=0.95 grid cell, no ANY-only cell passes even with exact output.

Frozen formal thresholds are therefore sensitivity 1.00, specificity 0.99,
false negatives 0 and UNKNOWN 0. They apply overall and separately to each
tested interval length, boundary stratum and multi-event stratum. The result is
a feasibility boundary, not a claim that a VLM can meet it.
