# Original GVAQP / PSVR Thesis Recovery

## Finding

Repository history repeatedly frames the project as **budgeted construction of a semantic `EventRelation` from an incomplete cheap scan plus expensive verification**, not as a standalone temporal clustering project.  Proxy imperfection, SCAN/VERIFY allocation, anytime quality, and deadline-safe visibility are first-order historical requirements.  Materialization is also explicit, but originally as the operator that converts confirmed sparse evidence into the durable query result.

This recovery predates and is not rewritten from the P0 materializer outcome.  The current audit protocol is `14e0b391a87d1a5546df49dc74374fc598e673269c8e843e6b3e3313825fc72c`.

## Source-level chronology

| Evidence | Recovered requirement | Current interpretation |
|---|---|---|
| `configs/research_contract_v1.yaml` | Primary output `EventRelation`; actions `SCAN_FIXED`, `VERIFY_TOP1`, `STOP`; safety order includes terminal recall and anytime-recall AUC | Budget/resource conversion and durable result semantics are core contract items |
| `docs/PSVR_P0_P1_P2_EXPERIMENT_CONTRACT.md` | Proxy representations, candidate universe, event recall/F1 vs calls/deadline AUC, full-path costs | Proxy quality and resource-quality curves were formal experiment concerns |
| `configs/scan_confirm_myopic_vps.yaml` / `fixed_ratio_25_75.yaml` | Myopic SCAN/CONFIRM and fixed allocation baselines | Scan/verify allocation was an executable research axis, though seconds-based and not directly compatible with this cached matrix |
| commit `5047241b0` (2026-07-27) | Frozen partial-scan and scan-confirm results | Incomplete exposure under resource limits was already being evaluated |
| commits `dd84374c9`, `97d3412a9` (2026-07-29) | Binary SMDP evidence and ARC baseline adaptation | Adaptive/control baselines were explored; no stable mainline win followed |
| commit `735bd2f97` (2026-08-08) | Temporal-order mechanism probe | Deterministic ordering became the supported simple execution direction |
| `MAB_RESEARCH_DIRECTION_DECISION.md` | Physical-anytime, causal exposure, completion accounting; explicitly not a MAB efficacy paper | The controller research question survived, but learned-bandit claims were frozen out |
| P0 V3 and mechanism ablation | C1 fixes a large materialization failure under sparse traces | Materialization is now a supported stage, but does not erase the older proxy/budget question |

## Conflicts and limits

- Historical configs express budgets in seconds and aspire to hard deadlines; P0 and this audit use **oracle invocation counts**.  Query-budget replay cannot establish physical hard-deadline superiority.
- Historical proxy/controller studies often use Guangzhou, realcartest, dataset3, Nexar clips, older labels, or abstract costs.  They establish provenance of the thesis, not current three-video effectiveness.
- Historical `Ours`, MAB, SMDP, ECP, and fixed-ratio names do not denote one common current policy.  They are not silently promoted into the primary matrix.
- The current prospective V3 scan gives every 10-second unit a candidate.  Its original exposure is therefore complete by construction; current proxy imperfection is primarily a **ranking** question until outcome-blind thinning is introduced as stress analysis.
