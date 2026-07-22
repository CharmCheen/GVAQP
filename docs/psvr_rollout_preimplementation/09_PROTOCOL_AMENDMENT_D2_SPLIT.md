# Protocol amendment — D2 split

Amendment: `AMEND_D2_SPLIT_BEFORE_ANY_TOY_RESULTS`.

The previous terminal state was `BLOCKED_D2_NUMERIC_BINDING`. Direct audit
before this amendment found no toy policy results, no held-out toy results, no
physical policy results, no Oracle calls, no GPU jobs, and no real held-out
access. The amendment is therefore result-blind.

The dependency error is corrected as follows: D2-L is the complete logical
shield; D2-T is the exact-support numerical binding for toy work; D2-P remains
`BLOCKED_CALIBRATION_REQUIRED` for physical replay, prototypes, and deployment.
H-ROLLOUT1A and 1B do not require D2-P. H-ROLLOUT1C does.

This valid dependency amendment does not cure a separate internal
inconsistency in the frozen D3/D4 specifications. Consequently the amendment
is complete, while H-ROLLOUT1A execution remains unauthorized.

