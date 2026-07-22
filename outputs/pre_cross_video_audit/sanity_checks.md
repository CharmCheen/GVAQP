# Pre-Cross-Video Sanity Checks

| check                                                                     | status   | detail                                                                                    |
|:--------------------------------------------------------------------------|:---------|:------------------------------------------------------------------------------------------|
| No algorithm outputs modified                                             | PASS     | audit writes only outputs/pre_cross_video_audit and docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md |
| No parameter tuning performed                                             | PASS     | fixed parameters read from prior scripts and documented                                   |
| No reference events used to modify parameters                             | PASS     | reference events used only for forensics/evaluation overlap                               |
| Trigger-count audit reads/reconstructs fixed outputs only                 | PASS     | rows=810                                                                                  |
| ARC claim audit states overlap_any disadvantage honestly                  | PASS     | B<=10 ARC wins are classified                                                             |
| Stage 1B overcoverage root cause computed from segment/reference overlaps | PASS     | rows=96                                                                                   |
| SUPG audit checks file paths and unit sets                                | PASS     | rows=30                                                                                   |
| Frozen config document exists                                             | PASS     | docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md                                                     |
| Any possible implementation bug explicitly flagged                        | PASS     | materializer_output_changed_any=True, supg_path_alias_any=False                           |
| Cross-video go/no-go decision explicit                                    | PASS     | PREFLIGHT_PASS                                                                            |
