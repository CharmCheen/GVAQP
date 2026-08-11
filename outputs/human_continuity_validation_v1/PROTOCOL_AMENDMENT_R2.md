# Pre-label Analysis Clarification (R2)

Active amendment: `7eb23201edd5d72d2fc040e9150098df3df015b82fc5372a3a6f09e999e8bdd1`

Amends R1 protocol: `06deda4503981179bdd2bc9157f94f80c104dcc7fffb5e866da4fd10325716ac`.  This was created while `HUMAN_LABELS_PRIMARY.jsonl` was empty. It does **not** change population, primary or reserve cases, source videos, query, VLM unit labels, C0/C1/K3 definitions, or clips. It only fixes the predeclared analysis seed, bootstrap count, decision thresholds, and the objective reserve-unlock condition.

Reserve may be unlocked only if the frozen R2 `INCONCLUSIVE_PRIMARY` condition is met.
