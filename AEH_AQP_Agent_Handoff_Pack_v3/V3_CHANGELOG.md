# v3 Changelog

Compared with v2:

- sealed `algorithmic_mechanism_viability_gate_v1` as `IDEAL_SIGNAL_ONLY`;
- recorded 149/149 settings and 141,750 policy runs;
- stopped exploration, counterfactual planning and real cheap-primitive engineering;
- replaced the resume prompt with a one-shot frozen S2 representation-transfer prompt;
- added exact R0/R1 × P0/P1 isolation and decision rules;
- made EventRelation + Barrier-Constrained Event Materialization the retained mainline;
- added the subsequent operator-centered roadmap;
- added server installation and validation instructions.

No legacy reference was rewritten. v3 should be installed beside v2, not over it.
