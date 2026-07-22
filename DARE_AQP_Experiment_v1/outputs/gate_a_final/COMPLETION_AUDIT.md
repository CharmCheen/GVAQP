# Gate A completion audit

| Requirement | Authoritative evidence | Status |
|---|---|---|
| Exact frozen model identities and revisions | `model_file_manifest.csv`; independent hash recomputation | Complete |
| Only necessary frozen files downloaded | 16-row manifest; exact snapshot inventories contain 8 files/model | Complete |
| GPU and persistent execution | `RESUME_LEDGER.md`; `logs/formal_inference.log`; runtime device fields | Complete |
| 347 frozen units per public signal | `raw_scores.csv`; `INFERENCE_COMPLETE.json`; independent review | Complete |
| Atomic safe resume | 694 unit JSON checkpoints and `unit_checkpoint_manifest.csv` | Complete |
| Ranking frozen before evaluator | ranking files/hashes precede evaluation; fail-closed recomputation log | Complete |
| No inference-label leakage | label-blind runner static audit and separated process artifacts | Complete |
| Public proxy, CLIP, X-CLIP, frozen fusion | exact four-signal final evaluator validation | Complete |
| Ideal oracle evaluator-only ceiling | `ideal_oracle_*` evaluation artifacts | Complete |
| Gate B exact linkage | `evaluation/gate_b_link.csv`, 20 registered cells | Complete |
| Top-k/event discovery/AUROC/AP | ranking metrics, diagnostics and first-discovery table | Complete |
| Frozen materializer event-F1 and AUC | per-budget metrics and `event_f1_auc.csv` | Complete |
| ARC/MAP overlap and position/duplicate diagnostics | dedicated evaluation CSVs | Complete |
| Cold/warm and component runtime ledger | model ledger plus 694-row per-unit runtime table | Complete; energy unavailable is explicit |
| Gate decision and route | `FINAL_DECISION.json`, `REPORT.md`, research-state update | Complete |
| Independent adversarial recomputation | 14 fail-closed checks in review JSON/Markdown | PASS |
| Physical exact-oracle VLM calls | inference completion, final decision and review | 0 |

Every explicit Gate A deliverable has direct current-state evidence. This audit
does not upgrade pseudo-events to human ground truth, establish cross-video
validity, or validate a real exact-oracle latency model.
