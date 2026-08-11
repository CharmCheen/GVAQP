# Frontier contract

- Admission/deduplication identity: `unit_id`.
- Candidate generation binds the highest frozen-score track on first visibility, with ascending track/candidate identity tie breaks; that unit-to-track witness is immutable.
- Retention: highest frozen visible score, capacity 10 by default.
- Deterministic order: `(-score, unit_id, track_id, candidate_id)`.
- A retained unit may be updated by later visible information before terminalization.
- Capacity-dropped units enter `discarded`; CONFIRMed units enter `queried`; neither can re-enter.
- Candidate age is computed from public elapsed time and creation time.
- CONFIRM always selects the first row under the frozen order.
- CONFIRM terminalizes only after backend execution, parsing, event materialization, deduplication, and durable action commit all succeed.
