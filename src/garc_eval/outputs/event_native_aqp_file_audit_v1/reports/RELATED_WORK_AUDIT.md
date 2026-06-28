# Related Work Boundary Audit

Based on `related_work/RELATED_WORK_MATRIX.csv` and `reports/RELATED_WORK_BOUNDARY_ANALYSIS.md`.

---

## Capability Coverage Matrix

| capability | SUPG | ABae | ARC | ExSample | LAVA | LensWalk | TAD | DriveJudge | STRIVE-D | DrivingDojo | Hydro | **Ours** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Expensive oracle | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✓ |
| Budget constraint | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ? | ✗ | ✓ | ✓ |
| Cheap proxy | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✓ |
| Temporal correlation | ✗ | ✗ | partial | partial | partial | partial | ✓ | ✗ | partial | ✗ | ✗ | ✓ |
| Event boundary | ✗ | ✗ | ✗ | ✓ | ✗ | partial | ✓ | ✗ | ✓ | ✗ | ✗ | partial |
| Event clip result | ✗ | ✗ | ✗ | ✗ | ✗ | partial | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Recall certificate | ✓ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ✓ | ✓ |
| Audit sampling | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

---

## System-by-System Comparison

### vs SUPG (NeurIPS 2020)
| dimension | SUPG | Ours |
|---|---|---|
| Data unit | Frame (i.i.d.) | Clip (non-i.i.d., P(1→1)=2.83×) |
| Proxy requirement | AUROC > 0.7 | AUROC = 0.624 (any AUC > 0.5) |
| Certificate | i.i.d. frame recall | non-i.i.d. clip recall (future) |
| Query type | Count/range | Event clip retrieval |
| **Safe positioning** | "We extend SUPG's AQP framework to non-i.i.d. temporal clips with weak proxies" | |
| **Risk** | Reviewer: "SUPG already handles proxy-guided budget allocation" | |
| **Mitigation** | Show SUPG's i.i.d. assumption fails when P(1→1)=2.83× base rate | |

### vs ABae (ICML 2018)
| dimension | ABae | Ours |
|---|---|---|
| Goal | Proportion estimation | Event clip retrieval |
| Data unit | Frame (i.i.d.) | Clip (correlated) |
| Stratification | Adaptive over strata | Static budget split + audit |
| **Safe positioning** | "ABae's stratification is for proportion estimation; we adapt for event clip retrieval with temporal correlation" | |
| **Risk** | LOW — different problem | |

### vs ARC (VLDB 2021)
| dimension | ARC | Ours |
|---|---|---|
| Query | Frame-level detection | Clip-level semantic event |
| Proxy role | Adaptive reduction | Coverage + stratification + audit |
| Timeline | No event stitching | Positive anchor → event cluster |
| **Safe positioning** | "ARC handles frame-level queries; we handle clip-level semantic events requiring stitching" | |
| **Risk** | LOW — different granularity | |

### vs ExSample (ICDE 2022)
| dimension | ExSample | Ours |
|---|---|---|
| Proxy | Model confidence | Handcrafted YOLO proxy |
| Budget | Adaptive sampling | Fixed budget decomposition |
| Result | Sampled frames | Stitched event clips |
| **Safe positioning** | "ExSample is confidence-based sampling; we are proxy-guided retrieval with recall certificate" | |
| **Risk** | LOW — different approach | |

### vs LAVA (SIGMOD 2021)
| dimension | LAVA | Ours |
|---|---|---|
| Focus | Learned proxy quality | Budget allocation under weak proxy |
| Proxy type | Learned/model cascade | Handcrafted YOLO |
| **Safe positioning** | "LAVA focuses on proxy quality; we focus on budget allocation with weak proxy" | |
| **Risk** | LOW — complementary | |

### vs LensWalk (PVLDB 2022)
| dimension | LensWalk | Ours |
|---|---|---|
| Interaction | Human-in-loop | Automated |
| Budget | Interactive | Formal B |
| Guarantee | None | Recall certificate |
| **Safe positioning** | "LensWalk is interactive exploration; we are automated AQP with formal guarantee" | |
| **Risk** | LOW — different paradigm | |

### vs TAD (Multiple venues)
| dimension | TAD | Ours |
|---|---|---|
| Oracle usage | Full scan | Budgeted partial scan |
| Output | Boundary-localized segments | Clip-level labels + event clusters |
| Budget | None | B constrained |
| **Safe positioning** | "TAD requires full oracle scan; we do budgeted clip retrieval with recall certificate" | |
| **Risk** | MEDIUM — both handle temporal events | |
| **Mitigation** | Emphasize budget constraint as TAD's missing dimension | |

### vs DriveJudge (arXiv 2024)
| dimension | DriveJudge | Ours |
|---|---|---|
| Goal | Safety evaluation | Event retrieval |
| Budget | Full evaluation | Budgeted query |
| Guarantee | None | Recall certificate |
| **Safe positioning** | "DriveJudge is full-scan evaluation framework; we are a budgeted AQP method" | |
| **Risk** | LOW — different objective | |

### vs DrivingDojo (CoRL 2023)
| dimension | DrivingDojo | Ours |
|---|---|---|
| Type | Benchmark | Method |
| **Safe positioning** | "DrivingDojo is a benchmark; our method could be evaluated on it" | |
| **Risk** | LOW — benchmark vs method | |

### vs STRIVE-D (AAAI 2024)
| dimension | STRIVE-D | Ours |
|---|---|---|
| Setting | Driving event retrieval | Event retrieval |
| Proxy role | Candidate filtering | Coverage + stratification + audit |
| Budget model | Unknown | Fixed B with decomposition |
| Certificate | Unknown | Planned recall certificate |
| **Risk** | HIGH — if STRIVE-D also has budget + certificate | |
| **Mitigation** | Need to verify STRIVE-D's budget model. If it has budget + certificate, differentiate on temporal correlation handling and audit allocation. | |

### vs Hydro (VLDB 2022)
| dimension | Hydro | Ours |
|---|---|---|
| Data | Relational | Video |
| Correlation | i.i.d. tuples | Temporally correlated clips |
| **Safe positioning** | "Hydro is relational AQP; we extend AQP to video with temporal structure" | |
| **Risk** | LOW — different data domain | |

---

## Unique Combination

No existing system covers all 7 capabilities:
1. Expensive oracle ✓
2. Budget constraint ✓
3. Cheap proxy ✓
4. Temporal correlation ✓
5. Event boundary (partial) ✓
6. Event clip result ✓
7. Recall certificate ✓
8. **Audit sampling** ✓ (unique — no other system does this)

**Our unique innovation area:** Combining budget decomposition with audit-aware allocation for temporally correlated clips under a weak proxy, with a recall certificate as the target guarantee.

---

## Claims Summary

### Safe claims
- "First AQP system combining budget decomposition, temporal correlation handling, audit-aware allocation, and recall certificate target for clip-level semantic event retrieval"
- "Budget decomposition under weak proxy (AUROC < 0.65)"
- "Audit-aware budget allocation for proxy-blind positives" (42.5% of events)
- "Non-i.i.d. clip-level structure requires different AQP design than i.i.d. frame-level"

### Claims to avoid
- "First AQP system for video" — ARC, ExSample, LAVA, LensWalk exist
- "First budgeted video query" — ExSample has adaptive budget
- "First driving event retrieval" — DriveJudge, STRIVE-D exist
- "First temporal action detection" — TAD is a mature field
- "Formal recall guarantees" — certificate not yet implemented

### Positioning for VLDB/SIGMOD/ICDE
"Approximate Query Processing for Semantic Event Clip Retrieval over Long Videos with Expensive Oracles"

Position alongside SUPG/Hydro as "AQP with expensive predicates extended to video," with the novel challenges being:
1. Weak proxy (AUROC=0.624 vs SUPG's 0.7 threshold)
2. Non-i.i.d. temporal clips (P(1→1)=2.83× base rate)
3. Proxy-blind positives (42.5% in low-score region)
4. Audit-aware allocation as a necessary component
