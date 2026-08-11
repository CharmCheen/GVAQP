# Materialization Mainline Decision

Decision: `REVISE`

Evidence level: controlled cached replay; model-relative and circularity-qualified.

Independent videos: `3`

Comparable selectors: `3`

Controlled pairs: `54`

Median Delta F1: `0.1457`

Fraction K3 > K0: `74.1%`

Main failure mode reduced: selected-negative barrier crossings, K0 `24.370` vs K3 `0.000` mean per cell.

Main unresolved risk: the evaluation event relation itself is current-V3-K3 constructed from full-grid model-relative labels; this supports a conditional reconstruction study, not independent human event-boundary truth.

Recommended next experiment: a pre-frozen boundary-insensitive or small frozen human sanity evaluation, selected independently of these P0 results, to test whether the observed effect survives the K3-defined reference interaction.
