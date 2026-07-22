# PSTR next-confirmation preregistration

Historical note: this v4 preregistration is superseded by `PSTR_EXTERNAL_CONFIRMATION_V5.md` and `config/frozen_external_confirmation_v5.json` after independent review found an omitted dataset3 proxy and underspecified external-test contracts.

Freeze time: 2026-07-13 02:15:13 UTC, after every currently available realcartest label domain had been opened and before any future external domain is acquired.

## Why DASR is not the terminal method

The frozen DASR gate mechanically passed its local five-seed rule, but the result was weak: the rich-interval AUC margin over the specified ARC mean was 0.010220, the sparse interval tied, and the final DASR curve was identical to stratified-only retrieval. A post-hoc 1,000-seed audit estimated ARC mean AUC at 0.655448 versus DASR at 0.674074, yet 48.1% of ARC seeds were higher. More decisively, pure public-proxy top-k reached 0.686480 and beat DASR. DASR therefore does not satisfy a strong-baseline terminal claim.

## Frozen next candidate

Proxy-Stratified Temporal Retrieval (PSTR-5:4) uses the same public proxy available to ARC. For budget `B`, it creates `min(n, B + floor(B/4))` equal contiguous temporal cells, retains the highest-proxy unit from every cell, ranks those representatives by proxy, and selects the first `B`. Selection is deterministic, label-blind, and always returns exactly `B` distinct units when `B <= n`.

The one-quarter overhead is fitted. It was selected after all four realcartest domains were open. Its current evidence is therefore exploratory. A leave-one-domain-out replay, in which overhead was selected only on the other three domains, produced three strict AUC wins and one tie versus shared-K3 ARC, but all domains still share one source video.

## Required next test

The next valid confirmation requires an independently sourced video. PSTR selections and every comparator selection must be sealed before oracle labels or references are opened. Primary success requires strict pooled normalized event-F1 AUC superiority over both pure proxy top-k and the precisely named `threshold-0.4 ARC-refinement + proxy-order exact-fill, shared K3` comparator. Every method must use exactly `B` unique oracle observations and the identical K3 materializer/evaluator.

SUPG, MMR, facility location, and DPP-style diversification remain mandatory strong baselines. A failure rejects PSTR-5:4; the cell overhead must not be retuned on the confirmation data and then called confirmed.
