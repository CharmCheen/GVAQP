# ARC Full-Text and Artifact Audit

`AUDIT_DECISION = NOVELTY_POSITION_REVISED`

## Strongest supported conclusion

ARC is direct prior art for approximate relevant-clip queries, exhaustive
query-specific proxy inference, temporal clustering, and progressive oracle
refinement. It therefore invalidates any MF-PSVR claim to be the first
proxy-plus-oracle relevant-clip system, the first progressive query-time clip
refiner, or the first use of query-conditioned temporal evidence.

The remaining MF-PSVR research hypothesis is narrower: incomplete evidence is
generated at query time, SCAN/REFINE/VERIFY compete under one enforced physical
clock, only frozen-oracle-confirmed results enter a typed EventRelation, and
materialization plus durable commit are charged to the same deadline. This is
a hypothesis, not an established contribution.

## Evidence scope and provenance

### Observed evidence

- The complete ten-page ARC paper was audited from title through references,
  including algorithms, evaluation protocol, ablations, and limitations. The
  authoritative landing records are the [ACM DOI](https://doi.org/10.1145/3726302.3729896)
  and [SIGIR 2025 program entry](https://sigir2025.dei.unipd.it/detailed-program/paper?paper=d9731321ef4e063ebbee79298fa36f56).
- The local `refe_repos/ARC-main` snapshot was inspected end to end for data
  preparation, clustering, refinement, timing, and evaluation. Its six core
  files are content-hashed in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json).
- The snapshot has no `.git` metadata, and the repository URL named in its
  README was unavailable during this audit. Conclusions about the paper are
  high confidence; conclusions about released behavior apply only to this
  hashed snapshot.

### Assumption

The local snapshot is treated as an author-associated artifact because it was
already present in the reference repository and names the paper authors'
repository. It is not treated as a commit-verifiable canonical release.

## Reconstructed ARC contract

ARC defines a relevant clip as a contiguous interval of at least `tau` frames
whose frames all satisfy a frame-level predicate, with output clips constrained
to be non-overlapping. It returns *candidate relevant clips* and defines their
quality by temporal IoU and an estimated probability of hitting true clips.

The paper's execution has two phases:

1. **Pruning.** Run a probabilistic proxy over every frame, transform proxy
   distributions according to the query predicate, cluster adjacent frames in
   time, and derive initial candidate clips.
2. **Refinement.** Spend oracle samples between candidate regions and
   non-candidate frames. Candidate regions use a bandit-style priority;
   non-candidates use proxy uncertainty. Propagate oracle labels and repeatedly
   recompute candidate confidence until a confidence target or oracle budget is
   reached.

The default reported configuration uses Mask R-CNN as oracle, CMDN as proxy,
`tau = 300` frames, temporal IoU and confidence thresholds of `0.9`, and an
oracle sampling budget equal to 10% of frames. The paper reports a 32.57x mean
speedup and mean quality values near 0.99 across its five datasets. Those are
the paper's reported benchmark observations; they are not evidence of hard
deadline compliance or of performance on this repository's benchmark.

## Decision-critical assumption audit

| Question | Finding | Evidence class |
|---|---|---|
| Is proxy evidence pre-materialized? | Conceptually it is generated at query processing time, but it is exhaustively generated for **all frames before refinement**. The snapshot's experiments load complete proxy/oracle arrays from CDF CSVs. | Paper Sections 4.1–4.2; [`experiment_handler.py:19`](../../../refe_repos/ARC-main/experiments/experiment_handler.py#L19) |
| Is proxy cost counted? | ARC's reported time formula includes configured proxy time for every proxy call and a clustering term. Its stopping budget `B`, however, is an oracle-call count, and the formula is evaluated after the algorithm rather than enforced as an online wall clock. | [`algorithm_handler.py:53`](../../../refe_repos/ARC-main/experiments/algorithm_handler.py#L53), [`metrics.py:47`](../../../refe_repos/ARC-main/experiments/metrics.py#L47) |
| Does a candidate pool preexist refinement? | Yes. Candidate clips are derived after the complete proxy pass and before progressive oracle sampling. | Paper Algorithms 1–2; [`arc.py:41`](../../../refe_repos/ARC-main/arc/arc.py#L41) |
| Call-count or physical budget? | The snapshot sets `B = samplingRate * number_of_frames`; the paper calls this an oracle budget, although Algorithm 2 labels it a time budget. Neither implementation path checks a deadline during execution. | [`experiment_handler.py:19`](../../../refe_repos/ARC-main/experiments/experiment_handler.py#L19), [`arc.py:56`](../../../refe_repos/ARC-main/arc/arc.py#L56) |
| Is scanning progressive? | Oracle sampling is progressive, but raw/proxy scanning is not: refinement begins only after proxy distributions for every frame exist. | Paper Section 4.2 and Algorithm 1 |
| Are candidates distinct from confirmed results? | No explicit evidence-state boundary exists. Returned clips may combine proxy, propagated, and sampled labels and carry an estimated confidence. | Paper Definitions 3.8–3.10; [`arc.py:125`](../../../refe_repos/ARC-main/arc/arc.py#L125) |
| Does it output EventRelation? | No. It returns temporal clip intervals and confidence, not the benchmark's typed relation with immutable candidate and oracle-verification provenance. | Paper problem definition; [`arc.py:131`](../../../refe_repos/ARC-main/arc/arc.py#L131) |
| Is it durable anytime? | No crash recovery, atomic visibility, prefix-valid snapshot, or durability contract was found. | Complete paper and snapshot audit |
| Are materialization and commit charged? | No explicit materialization, serialization, fsync, or commit term appears in the time equation. | [`metrics.py:47`](../../../refe_repos/ARC-main/experiments/metrics.py#L47) |
| Is intermediate fidelity query-conditioned? | Yes in a broad and consequential sense: predicate semantics transform proxy output and drive temporal clustering, candidate construction, sampling, and confidence. It remains a single exhaustive proxy tier followed by oracle refinement. | Paper Sections 4.2–4.3 |

## Paper–snapshot concordance

The inspected snapshot supports the central paper architecture:

- full proxy and oracle arrays are prepared before an experimental run;
- proxy outputs initialize per-cluster probabilities and candidate clips;
- progressive sampling alternates between candidate UCB priority and
  non-candidate importance sampling;
- an oracle sample overwrites/propagates a label within a temporal cluster;
- returned candidates and confidence are evaluated against ground-truth clips;
- reported cost combines configured model-call times and measured Python phase
  time.

These points are sufficient to reject the broad novelty claims listed above.

## Paper–snapshot discrepancies and negative evidence

### 1. Adaptive clustering is not evidenced in the snapshot

The paper says proxy unreliability can tighten the similarity threshold and
describes rollback when cluster membership changes. The snapshot computes or
loads one cluster labeling for a fixed threshold before `arc(...)` begins.
`arc(...)` receives only the resulting cluster IDs, never a threshold or raw
distributions needed to recluster, and its refinement loop contains no
reclustering or rollback operation. See
[`pruning_phase.py:63`](../../../refe_repos/ARC-main/arc/pruning_phase.py#L63),
[`experiment_handler.py:19`](../../../refe_repos/ARC-main/experiments/experiment_handler.py#L19),
and [`arc.py:20`](../../../refe_repos/ARC-main/arc/arc.py#L20).

**Interpretation:** either the snapshot is incomplete/stale, the prose describes
an omitted path, or the implementation operationalizes the idea differently.
The evidence does not identify which explanation is correct. A baseline must
not quietly claim both paper-level adaptation and snapshot-level reproduction.

### 2. Cross-cluster propagation is not evidenced in the main update path

The paper describes complete and incomplete propagation between adjacent
high-confidence clusters. The inspected `label_propagation` function samples
one frame, selects its current cluster boundaries, and copies that sample's
label within those boundaries (subject to a boundary adjustment). No explicit
adjacent-cluster interpolation path appears in that function or its caller.
See [`refinement_phase.py:78`](../../../refe_repos/ARC-main/arc/refinement_phase.py#L78).

**Interpretation:** this is negative evidence limited to the hashed snapshot,
not proof that the authors never implemented the described behavior elsewhere.

### 3. The budget is not an enforced physical deadline

The refinement loop iterates over integer `B`, while model cost is reconstructed
later from configured per-frame constants. Initialization, model loading,
warm-up, video decode/I/O, serialization, materialization, and durable commit do
not share a checked deadline. The internal `time.time()` measurements cover
selected Python phases but do not stop work based on elapsed time.

**Derived conclusion:** ARC's reported time comparison is meaningful within its
evaluation protocol, but it cannot be inserted unchanged into the strict
MF-PSVR physical table.

### 4. A likely textual unit inconsistency remains unresolved

The sensitivity section describes `tau = 180..420` frames as approximately one
second except for one dataset. At 30 frames/s, that range is 6–14 seconds. The
paper may use other effective frame rates or contain a wording error; the text
available in the audited PDF does not resolve it. This does not affect the
novelty decision but should prevent copying temporal settings without checking
source FPS.

### 5. The benchmark cannot instantiate ARC's native value domain

ARC's probability, entropy, propagation, and confidence equations share a
per-frame binary proxy/oracle domain and a frame-duration requirement `tau`.
The frozen benchmark oracle instead returns one categorical result per 10-second
unit and delegates event bridging to K3. A Y8 track/unit score is not silently
equivalent to ARC's CMDN distribution, and a unit Qwen label is not a frame
oracle distribution.

**Derived conclusion:** the physical benchmark may include the explicitly
defined `ARC-UNIT-INSPIRED` mapping in
[BASELINE_ADAPTATION_SPEC.md](BASELINE_ADAPTATION_SPEC.md), but it cannot call
that row faithful ARC or transfer ARC's native confidence guarantee. A faithful
native reproduction would require ARC's frame-level endpoint and belongs in a
separate protocol table.

## Revised novelty boundary

### Claims rejected by this audit

- first proxy-plus-oracle relevant-clip query system;
- first progressive sampling/refinement for relevant clips;
- first query-conditioned temporal clustering or intermediate evidence;
- first confidence-aware selection of clip candidates;
- superiority to ARC based on cached adapter replay.

### Claim retained only as a falsifiable hypothesis

MF-PSVR may contribute a **joint physical-anytime systems contract** in which
the candidate universe is endogenous to an incomplete scan; a selectively
invoked learned temporal semantic action competes with scan and frozen
verification; all actions, materialization, and durable commit share the same
deadline; and strict outputs are oracle-confirmed EventRelation rows.

No component in that sentence should be claimed individually as first. The
contribution is viable only if ablations show that the learned intermediate
action adds cross-video value beyond FIFO, detector-score ranking,
ExSample-like adaptive scan, Zeus-like adaptive configuration, FiGO-like
chunk/fidelity planning, and appropriately costed temporal-query controls after
all physical costs.

## Main competing explanation

Any future gain may come entirely from a simpler scheduling effect—earlier
coverage, detector confidence, or verification order—rather than learned
multi-fidelity semantics. ARC's strong proxy/refinement results make this
explanation especially plausible.

## Key uncertainty and rejection observation

The audit cannot establish whether incomplete proxy generation is beneficial
on the frozen benchmark. Reject or materially revise MF-PSVR if a full-proxy
ARC-style strategy, an ExSample-style adaptive scanner, or a simple FIFO/score
controller—or a Zeus/FiGO mechanism control—matches its paired cross-video
utility within the preregistered practical-equivalence margins once
initialization, online inference, materialization, and commit are charged to the
same clock. Also reject the semantic-refiner contribution if removing REFINE
fails the minimum causal-effect gate in the novelty boundary.

## Next action

Implement baselines under the explicit adaptation contract in
[BASELINE_ADAPTATION_SPEC.md](BASELINE_ADAPTATION_SPEC.md), then first measure
whether an independent training pool contains enough frozen-oracle-positive
opportunities to learn a source-general semantic action. No large model or
physical matrix is justified before that class-balance measurement.
