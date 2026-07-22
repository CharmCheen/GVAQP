# PSVR H-ROLLOUT1A-R2 evidence-meaning audit

`SOURCE_EVIDENCE_INTEGRITY = PASS`  
`THEOREM_NONINFERIORITY_APPLIES = true`  
`THEOREM_CONDITIONS_SATISFIED = true`

## Strongest supported conclusion

`R2_EVIDENCE_STATUS = THEOREM_ALIGNED_IMPLEMENTATION_VALIDATION WITH BROAD SYNTHETIC STRICT-GAP EVIDENCE`  
`R2_ADDITIONAL_EMPIRICAL_INFORMATION = STRICT_GAP_EXISTS_BROADLY_IN_SYNTHETIC_WORKLOAD`  
`STRICT_GAP_EPISODE_COUNT = 451`  
`ZERO_GAP_EPISODE_COUNT = 61`  
`NEGATIVE_GAP_EPISODE_COUNT = 0`

The sealed raw evidence independently reproduces M1−π0 mean = 11.056640625. It contains 451 strict gains, 61 ties, and 0 losses. Thus strict gains are broad in this finite synthetic workload; they are not guaranteed by the non-inferiority theorem and do not establish practical or real-video effectiveness.

## Baseline equality

`M1_VS_PI0_MEAN = 11.056640625`  
`M1_VS_B2K1_MEAN = 11.056640625`  
`PI0_VS_B2K1_MEAN = 0.000000000`  
`GAIN_EQUALITY_EXPLANATION = A. pi0 and B2-K1 episode-wise completely equivalent`  
`BEST_FIXED_SELECTION_RULE = frozen global primary-utility macro-mean; no per-episode oracle`

## Regimes

`REGIME_DEFINITIONS = process, cost-variance, and process×cost definitions in R2_REGIME_ACCOUNTING.csv`  
`REGIME_COUNTS = Sparse 191; Bursty 210; Heterogeneous cost 311; Dense homogeneous 36; UNIFORM_SPARSE|SCAN_CHEAP 64`  
`REGIME_OVERLAP = overlapping slices, not independent replications; matrix in R2_REGIME_OVERLAP_MATRIX.csv`  
`WORST_REGIME_STATUS = EXPLORATORY_WORST_SLICE_ANALYSIS`

The reported means reconstruct as Sparse=7.9686, Bursty=12.8667, Heterogeneous cost=10.5145, Dense homogeneous=12.7778. The worst process×cost slice is `UNIFORM_SPARSE|SCAN_CHEAP`, N=64, mean=5.6875; its *minimum* label is exploratory ranking. Regimes overlap substantially and are not independent repeats.

## Review provenance

`REVIEWER_TYPE = automated agent / undocumented; no human provenance`  
`REVIEW_INPUT_SCOPE = pre-launch frozen code/protocol; no raw confirmatory traces`  
`REVIEW_CHECKLIST = copied verbatim in 06_REVIEW_PROVENANCE_AUDIT.md`  
`REVIEW_INDEPENDENCE_LIMITATION = no documented process/code/filesystem isolation; no post-result independently implemented raw reanalysis`  
`RECOMMENDED_REVIEW_WORDING = separate-agent integrity audit (pre-launch)`

## Evidence boundary and next action

`EXECUTION_INTEGRITY_EVIDENCE = repository-local matching R2/E1 source hashes; matching seed commitment; zero legacy/development intersections; 4608/4608 raw identities, hashes, and D1 values reconciled`  
`SCIENTIFIC_EFFECTIVENESS_EVIDENCE = theorem-derived ideal non-inferiority plus broad strict-gap evidence in the frozen synthetic workload only`  
`UNTESTED_CLAIMS = approximate/model-error robustness; planning-cost robustness; real-video transfer; physical wall-clock gain`

Execution integrity is strong conditional on repository-local artifacts: freeze hashes match, the seed commitment matches, no legacy/development seed intersection was found, and 4,608/4,608 identities, raw hashes, and D1 values reconcile. It is not an externally anchored forensic guarantee. Scientific effectiveness remains limited to the exact synthetic setting. H1B approximation/model-error/planning-cost robustness is untested, and remains the highest-value next empirical uncertainty; it was not run or modified here.

`CORRECTED_PAPER_WORDING = see 09_CORRECTED_R2_WORDING.md`  
`CORRECTED_PROJECT_STATUS = Level 2 theorem-aligned synthetic implementation validation`  
`H1B_PRIORITY = next empirical uncertainty, not executed in this audit`
