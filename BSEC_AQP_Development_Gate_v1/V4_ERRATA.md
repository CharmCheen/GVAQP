# v4 errata and supersession

The four-domain v4 exploration is preserved byte-for-byte as a historical freeze. It is superseded by the five-domain v2 exploration and external protocol v5.

Known v4 metadata defect: `outputs/pstr_exploration/selected_candidate_auc.csv` has an `exact_oracle_calls` column containing a pipe-delimited budget schedule, not measured calls. It must not be interpreted as accounting evidence. Exact calls are correctly recorded per row in `outputs/pstr_exploration/per_budget_runs.csv`. The superseding `outputs/pstr_exploration_v2/selected_candidate_auc.csv` removes the defective field; its `per_budget_runs.csv` again records measured exact calls.

Known v4 scope defect: dataset3 was omitted even though its controlled ARC public proxy was available. The v2 exploration adds dataset3, persists pure-proxy and other baseline AUCs, and recomputes leave-one-domain-out evidence over five domains.
