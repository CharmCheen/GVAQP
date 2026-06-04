# Topic-by-Topic Assessment

## A. Query-Impact-Aware Predictive Execution

**Problem statement:** For ego-relative geometric predicates in moving-camera driving videos, skip oracle calls when prediction uncertainty does not affect the clip-level answer, but trigger correction near predicate boundaries or clip-critical regions.

**Real demand / scenario:** Autonomous driving perception pipelines process hours of multi-camera video. Running expensive oracles (3D detectors, depth estimators) on every frame is wasteful when target states are predictable over short horizons. A query-aware execution engine could reduce oracle cost by 50-80% while maintaining clip-level quality.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- ARC: uses proxy pruning + MAB sampling but no predictive skipping based on geometric state prediction
- SUPG: frame-level selection with guarantees, no temporal prediction
- ABae: aggregation with expensive predicates, no clip semantics
- Seiden: oracle-proxy architecture, no geometry-aware prediction
- Spatialyze: geospatial video queries, no predictive oracle skipping

**Outputs supporting it:**
- `real_kinematic_uadetrac`: boundary_only_m10 beats fixed_rate by 0.103 F1 (UA-DETRAC 2D)
- `nuscenes_feasibility`: real 3D pipeline works, baselines degrade meaningfully
- `nuscenes_audit`: evaluation corrected, naive_oracle=1.0

**Outputs weakening it:**
- `real_kinematic_uadetrac`: advantage is small (0.103 F1), parameter-sensitive (margin=20 fails)
- `factorial_ablation`: propagation dominates allocation (5x), suggesting allocation tricks have limited impact
- `audit_agent_e`: hidden_risk allocation provides minimal improvement over uniform

**Additional evidence needed:**
- Query-impact-aware triggering implemented and tested on nuScenes real 3D data
- Ablation of each component (boundary, staleness, disagreement)
- Comparison with Kalman-based and uncertainty-based triggering
- Statistical significance across multiple seeds

**Strongest baselines required:**
- Fixed-rate oracle (k=2,3,5,10)
- Linear interpolation
- Kalman fixed-interval
- Kalman uncertainty-only
- Boundary-only triggering
- ARC-style adaptive sampling

**Main technical contribution:** A principled framework for deciding when to call the oracle based on whether prediction uncertainty could change the clip-level query answer.

**Main risk:** The advantage may be too small or too parameter-sensitive to constitute a strong paper. The factorial ablation suggests allocation tricks have limited impact.

**Top-conference fit:** Database systems / AQP / VDBMS (VLDB/SIGMOD) — moderate fit. The geometry-aware aspect is novel for DB venues but the contribution is more systems/ML than theoretical.

**Scores:**
- Novelty: 6/10 (predictive execution for video queries is novel, but the idea of skipping oracle calls is not)
- Feasibility: 7/10 (real 3D data available, baselines implemented, but method not yet tested)
- Technical depth: 5/10 (the method is primarily engineering, limited theoretical contribution)
- Data readiness: 8/10 (nuScenes mini pipeline complete, query table built)
- Baseline readiness: 7/10 (6 baselines implemented, evaluation corrected)
- Top-conference potential: 5/10 (marginal advantage, may not be strong enough for VLDB/SIGMOD)
- Risk: 7/10 (high risk that advantage is too small or disappears on harder queries)

---

## B. Clip-Level Guaranteed AQP / G-ARC

**Problem statement:** Given a relevant clip query with oracle budget constraint, return a set of clips with high-probability guarantees on clip-level recall, precision, or IoU — not just frame-level metrics.

**Real demand / scenario:** Video search systems need to guarantee that returned clips actually contain the queried content. Frame-level guarantees (SUPG) don't transfer to clip-level because clip boundaries create dependencies that break i.i.d. assumptions. A user searching for "pedestrian crossing for at least 5 seconds" needs clip-level recall guarantees, not frame-level recall guarantees.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- ARC: has confidence estimation but NOT high-probability guarantees (Pr[Clip-Recall >= gamma] >= 1-delta)
- SUPG: provides frame-level guarantees only, clips are not i.i.d. records
- ABae: aggregation guarantees, not selection/clip guarantees
- Seiden: no guarantees at all
- Spatialyze: no guarantees at all

**Outputs supporting it:**
- `smoke_test`: clip degradation 5-20x larger than frame degradation (real phenomenon)
- `audit_agent_c`: effect stable across 240 parameter combinations
- `audit_agent_d`: proxy_noise causes 20-27x amplification
- `factorial_ablation`: propagation dominates, nearest-neighbor is near-perfect
- `hard_synthetic`: NN fails on hard regimes (regime_shift, mixed_hard)
- `G-ARC_Research_Report`: detailed literature survey confirms the gap exists

**Outputs weakening it:**
- `factorial_ablation`: nearest-neighbor is already near-perfect on easy synthetic data
- `hard_synthetic`: only 2 out of 5 regimes are actually hard
- No real-data validation of clip-level guarantees yet

**Additional evidence needed:**
- Formal guarantee definition and proof (Pr[Clip-Recall >= gamma] >= 1-delta)
- Real-data validation on nuScenes with clip-level guarantee violation rates
- Comparison with ARC's confidence-based approach
- Demonstration that guarantees are meaningful (not trivially satisfied)

**Strongest baselines required:**
- ARC (confidence-based clip selection)
- SUPG (frame-level guarantees applied to clips)
- Fixed-rate oracle
- Uniform random sampling
- Nearest-neighbor interpolation

**Main technical contribution:** Extending AQP guarantees from frame-level to clip-level, handling the non-i.i.d. structure of clips and the IoU-based hit semantics.

**Main risk:** The theoretical contribution may be hard to formalize cleanly. The nearest-neighbor baseline is already near-perfect on easy data, making it hard to show meaningful improvement.

**Top-conference fit:** Database systems / AQP (VLDB/SIGMOD) — strong fit. This is a genuine database query processing problem with statistical guarantees. The clip-level extension is a natural and novel contribution for DB venues.

**Scores:**
- Novelty: 8/10 (no existing work provides clip-level high-probability guarantees)
- Feasibility: 6/10 (theoretical contribution is harder to produce than systems contribution)
- Technical depth: 8/10 (requires formal guarantee design, possibly conformal prediction tools)
- Data readiness: 6/10 (synthetic data strong, real data pipeline exists but not validated for guarantees)
- Baseline readiness: 7/10 (strong synthetic baselines, real baselines partial)
- Top-conference potential: 8/10 (genuine gap in DB/AQP literature, clear novelty)
- Risk: 5/10 (moderate risk — the theory is tractable but needs careful formalization)

---

## C. Segment-Aware AQP for Video Queries

**Problem statement:** Video queries return segments (clips), not individual records. AQP methods designed for i.i.d. records don't handle the temporal dependencies, boundary uncertainty, and IoU-based hit semantics of video segments.

**Real demand / scenario:** Any video search system that returns temporal segments (highlights, events, activities) needs AQP methods that understand segment structure. This is a generalization of G-ARC that applies to any video query returning temporal segments.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- Generalizes G-ARC to any segment-returning query
- More general than geometry-aware (A) — applies to any video predicate
- More specific than Seiden — focuses on segment semantics, not just oracle-proxy architecture

**Outputs supporting it:**
- All outputs supporting G-ARC (B)
- `real_mvp`: frame-to-clip gap is the main finding across all experiments

**Outputs weakening it:**
- May be too broad — hard to define a clean contribution scope
- No unique technical contribution beyond G-ARC

**Additional evidence needed:**
- Same as G-ARC, plus demonstration across multiple query types (not just count/geometric)

**Strongest baselines required:** Same as G-ARC.

**Main technical contribution:** A general framework for segment-aware AQP that handles temporal dependencies and boundary uncertainty.

**Main risk:** Too broad — may dilute the contribution. G-ARC is already a subset of this.

**Top-conference fit:** Database systems / AQP (VLDB/SIGMOD) — moderate fit. Broader scope but potentially less focused contribution.

**Scores:**
- Novelty: 7/10 (generalizes G-ARC but may be too broad)
- Feasibility: 6/10 (same as G-ARC)
- Technical depth: 7/10 (same theoretical challenges as G-ARC)
- Data readiness: 6/10 (same as G-ARC)
- Baseline readiness: 7/10 (same as G-ARC)
- Top-conference potential: 7/10 (broader but less focused)
- Risk: 6/10 (broader scope may dilute contribution)

---

## D. Geometry-Aware Relevant Clip Query Processing

**Problem statement:** For driving videos with ego motion, relevant clip queries depend on ego-relative geometric predicates (in_fov, within_30m, ego_front). The geometry adds structure that can be exploited for more efficient query processing.

**Real demand / scenario:** Autonomous driving perception needs to efficiently find clips where objects satisfy geometric conditions relative to the ego vehicle. This is a specific instance of video query processing with domain-specific structure.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- ARC: general video queries, no geometry-specific optimization
- Spatialyze: geospatial queries but not ego-relative geometry
- More specific than C (Segment-Aware) — focused on driving geometry

**Outputs supporting it:**
- `nuscenes_feasibility`: real 3D pipeline works, all predicates populated
- `nuscenes_audit`: evaluation correct, baselines meaningful
- `real_kinematic_uadetrac`: boundary-aware triggering shows advantage on 2D proxy

**Outputs weakening it:**
- `real_kinematic_uadetrac`: advantage is small and parameter-sensitive
- The geometry-specific contribution may not be significant enough
- May be too application-specific for DB venues

**Additional evidence needed:**
- Query-impact-aware triggering on nuScenes real 3D data
- Demonstration that geometry-aware prediction beats generic temporal prediction
- Ablation showing geometry-specific contribution

**Strongest baselines required:**
- All baselines from A (Query-Impact-Aware)
- Plus: generic temporal prediction (no geometry)
- Plus: ARC-style adaptive sampling

**Main technical contribution:** Exploiting ego-relative geometric structure for more efficient video query processing.

**Main risk:** Too application-specific. The geometry-aware contribution may not generalize beyond driving videos.

**Top-conference fit:** Computer vision / autonomous driving (CVPR/ECCV/ICRA) — better fit than DB venues. Database venues may find it too application-specific.

**Scores:**
- Novelty: 5/10 (geometry-aware processing is novel but application-specific)
- Feasibility: 8/10 (real 3D data available, pipeline complete)
- Technical depth: 4/10 (primarily engineering, limited theoretical contribution)
- Data readiness: 8/10 (nuScenes pipeline complete)
- Baseline readiness: 7/10 (baselines implemented)
- Top-conference potential: 4/10 (too application-specific for DB venues, may fit CV venues)
- Risk: 6/10 (advantage may be too small or too specific)

---

## E. Anytime / Progressive Relevant Clip Query Processing

**Problem statement:** Return intermediate clip results as oracle budget is consumed, with quality guarantees that improve monotonically with budget.

**Real demand / scenario:** Interactive video search where users want to see results immediately and refine as more budget is spent. Anytime algorithms provide results at any budget level with known quality bounds.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- SUPG: returns a final set, not progressive results
- ABae: aggregation, not progressive clip selection
- Novel aspect: anytime guarantees for clip-level queries

**Outputs supporting it:**
- `nuscenes_feasibility`: baselines show monotonic degradation with budget
- `real_mvp`: budget-quality curves are smooth

**Outputs weakening it:**
- No existing experiments test anytime/progressive behavior
- The anytime aspect is primarily an interface/API contribution, not algorithmic

**Additional evidence needed:**
- Anytime algorithm design
- Progressive quality guarantee proof
- User study or interactive demo

**Strongest baselines required:**
- SUPG (final-set baseline)
- Fixed-rate with increasing budget
- ARC (progressive sampling)

**Main technical contribution:** Anytime algorithm for clip-level AQP with monotonic quality guarantees.

**Main risk:** The anytime aspect may be seen as incremental. The core algorithmic challenge is the same as G-ARC.

**Top-conference fit:** Database systems (VLDB/SIGMOD) — moderate fit. The anytime aspect is interesting but may not be enough for a standalone paper.

**Scores:**
- Novelty: 5/10 (anytime is a useful property but not a core contribution)
- Feasibility: 7/10 (can build on G-ARC work)
- Technical depth: 6/10 (requires careful algorithm design)
- Data readiness: 6/10 (same as G-ARC)
- Baseline readiness: 6/10 (needs new anytime baselines)
- Top-conference potential: 5/10 (may be too incremental)
- Risk: 5/10 (moderate risk — depends on G-ARC foundation)

---

## F. Uncertainty-Aware Relevant Clip Semantics

**Problem statement:** Define clip semantics that explicitly account for prediction uncertainty. Instead of hard clip boundaries, use soft boundaries with confidence scores. Instead of binary tau satisfaction, use probabilistic tau satisfaction.

**Real demand / scenario:** Video search results should express uncertainty. A clip that is "probably 5 seconds of pedestrian crossing" is more useful than a binary yes/no answer. Uncertainty-aware semantics enable better user trust and downstream decision-making.

**How it differs from ARC/SUPG/ABae/Seiden/Spatialyze:**
- ARC: confidence estimation but binary clip decisions
- Novel aspect: soft clip boundaries with uncertainty quantification

**Outputs supporting it:**
- `audit_agent_d`: proxy_noise causes boundary uncertainty (20-27x amplification)
- `hard_synthetic`: boundary_ambig regime is hard for NN
- `factorial_ablation`: boundary precision is a differentiator

**Outputs weakening it:**
- No existing experiments test soft clip semantics
- The uncertainty-aware aspect may be too complex for a first paper
- Users may prefer hard clip boundaries

**Additional evidence needed:**
- Formal definition of uncertainty-aware clip semantics
- User study comparing hard vs soft clip boundaries
- Demonstration that uncertainty-aware methods improve downstream decisions

**Strongest baselines required:**
- Hard-boundary methods (G-ARC)
- ARC confidence-based approach
- Bayesian clip boundary estimation

**Main technical contribution:** Uncertainty-aware clip semantics with formal uncertainty quantification.

**Main risk:** Too complex for a first paper. May be better as a follow-up after G-ARC.

**Top-conference fit:** Database systems / IR (VLDB/SIGMOD/SIGIR) — moderate fit. The uncertainty aspect is interesting but may be too complex.

**Scores:**
- Novelty: 7/10 (uncertainty-aware clip semantics is novel)
- Feasibility: 4/10 (complex to implement and evaluate)
- Technical depth: 8/10 (requires formal uncertainty quantification)
- Data readiness: 5/10 (needs new evaluation framework)
- Baseline readiness: 4/10 (needs new uncertainty-aware baselines)
- Top-conference potential: 6/10 (interesting but complex)
- Risk: 8/10 (high risk — too complex, may not be publishable as first paper)
