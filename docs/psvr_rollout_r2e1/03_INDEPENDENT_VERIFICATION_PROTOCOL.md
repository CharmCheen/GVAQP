# Independent verification

The verifier imports neither coordinator functions nor derived CSVs. Starting
from ledger and raw JSON only, it verifies trace SHA-256, one-to-one public
identity binding, method-universe completeness, raw identity agreement, and
recomputes D1 utility, AnytimeAUC-F1, TTFC, recall, unique commits and duplicate
confirms from visible observation sequences plus evaluator truth tokens. Any
disagreement with coordinator-recorded trace metrics blocks the decision.

Pairing, regime aggregation and Gate consume only the verifier's recomputed
records. The verifier report explicitly declares `derived_outputs_read=false`.
