# SCAN false-negative audit

- Original substrate: 1475 units and 1475 precomputed candidates; structural exposure recall 1.0.
- Model-relative semantic positives: 251; positives with candidates: 251; without candidates: 0.
- Natural `SCAN failed -> candidate never enters frontier` is impossible in the audited sequential environment because unit/proxy/oracle universes must match and scanning releases every member of a stored cell.
- A low proxy score can delay VERIFY: this is a ranking miss, not an exposure miss.
- E1/E2/E3 delete candidates by outcome-blind hash and are `SYNTHETIC_DIAGNOSTIC_ONLY`, not evidence of natural cheap-sensor false negatives.
