# AGENTS.md

## Project Scope

This repository studies G-ARC: Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories.

The core research contribution is **AQP-side** (database / approximate query processing):
given a universe of variable-length semantic clips over long videos, an expensive oracle,
a cheap candidate generator, a budget B, a target recall γ and a failure probability δ,
return a clip set together with a **conservative clip-level oracle-relative recall
certificate** `Pr[R̂ ≥ γ] ≥ 1 − δ`. The deliverable is a query system (paper landing form)
with formal guarantees, budget allocation, and statistical certification.

The current stage has an established single-video evaluation stack (V13.5–V13.10) and one
DB-side positive result (budget-decomposition, see Findings). The remaining work is
AQP-method and AQP-theory, not perception engineering.

## Research Framing — AQP-core, Driving-workload, VLM/Proxy-mechanism

This ordering is binding. When actions or claims could be read in two ways, choose the
reading that prioritizes the higher layer.

1. **AQP is the contribution.** What is novel is the query-side machinery:
   budget decomposition under expensive oracles, adaptive allocation with posterior
   updates, statistical guarantees on temporally-correlated variable-length units,
   proxy-agnostic feasibility bounds, and certificate construction. These are
   database/query-processing questions, not perception questions.
2. **Driving danger events are the representative workload**, chosen because long
   dashcam videos give a large clip universe, a genuinely expensive VLM oracle, a
   non-i.i.d. temporal structure, and variable-length events — exactly the conditions
   that make a clip-level guarantee non-trivial. Driving is *representative*, not
   *the contribution*; the framework must remain workload-portable in principle.
3. **VLM / agent / proxy are execution mechanisms and are substitutable.** A cheap
   proxy could be handcrafted YOLO counts, CLIP/SigLIP embeddings, an 8B VLM cascade,
   or a future geometric scorer. The oracle could be a 32B VLM or a human. The AQP
   contribution must hold *for any candidate generator with non-trivial AUC* and
   *for any expensive oracle*, not only for the specific YOLO/Qwen3-VL pair used in
   the V13 experiments.

### Anti-drift rules

- Do **not** spend effort on building a better driving-event detector as an end in
  itself. Any proxy improvement must be motivated as "producing a stronger empirical
  instance of a candidate generator to test the AQP framework," not as the paper claim.
- Do **not** treat VLM prompt engineering, lane/path estimation, or object tracking as
  research contributions. They are execution instantiations.
- Do **not** collapse AQP feasibility into proxy quality. If a method fails, disentangle
  "proxy too weak" from "budget framing too narrow" before drawing conclusions
  (the diversity-prefilter experiment shows this disentanglement is necessary and
  productive — see Findings).
- When a new perception-side signal is proposed, it must be accompanied by an AQP-side
  research question it enables (e.g., "enables testing proxy-agnostic bounds when
  proxy AUC rises from 0.74 to >0.9"), not by a perception-side benchmark target.

## AQP-Core Research Questions (current)

These are the questions the project should push on. Each is a DB/AQP question, not a
perception question. They are open unless noted.

1. **Budget decomposition.** Split `proxy_top(P)` from `oracle_examine(B)` and choose
   oracle targets by coverage/diversity, not by raw proxy score. **Status:** one
   positive result on V13.8 oracle — see Findings. Open: set-cover vs. α-penalty,
   second-video replication, theoretical bound on reachable recall as a function of (P, B, proxy AUC).
2. **Clip-level guarantee under non-i.i.d. structure.** SUPG assumes i.i.d. frame
   sampling; clips are temporally clustered (`P(1→1)=0.457` vs base 0.236 on
   realcartest). How to construct a valid CI / Wilson bound when selection units
   are correlated. Open and central.
3. **Adaptive allocation with posterior updates.** V13.10 showed naive local
   boost/expand fails; the principled variants (Thompson sampling / UCB over event
   clusters, disagreement-driven exploration) are untested. Open.
4. **Multi-fidelity oracle cascade.** 8B-first → 32B-confirm is a cost-aware query
   optimization problem (which anchors to escalate), not a model benchmarking
   problem. Open, requires explicit authorization for new VLM calls.
5. **Coverage-vs-precision tradeoff in certificate.** Phase-0.6 simulation demands
   ~500 events for non-vacuous certificate; V13.8 has 51. What is the minimum `B` for
   a non-vacuous `Pr[R̂ ≥ γ] ≥ 1 − δ` as a function of positive rate, cluster
   structure, and budget-allocation policy? This is the theory bridge between proxy
   quality and AQP feasibility. Open and central.
6. **Proxy-agnostic feasibility bound.** Given any proxy with `AUC > 0.5 + ε`, derive
   the `B` required for `γ`-recall certificate. This connects mechanism (proxy) to
   contribution (guarantee) and is the cleanest "proxy-agnostic" claim. Open.

## Environment

- Repository path: `/qiuyeqing/llama_prl/G-ARC`
- Typical setup: `cd /qiuyeqing/llama_prl/G-ARC && source env_garc.sh`
- Conda environment: `garc`
- YOLO model paths:
  - `models/yolo/yolov8n.pt`
  - `models/yolo/yolov8x.pt`
- Default proxy model: YOLOv8n
- Default pseudo-oracle model: YOLOv8x
- VLM oracle used in V13: Qwen3-VL-32B (weights under `models/vlm/`)

## Repository Layout

- `garc_eval/`: main benchmark, reproduction, metric, adapter, dataset, config, and experiment code.
- `garc_eval/outputs/`: lightweight reports and experiment summaries.
- `garc_eval/configs/`: lightweight experiment configuration files.
- `garc_eval/outputs/diversity_prefilter_replay_v1/`: the budget-decomposition
  positive result — read this report first when onboarding to the AQP-core line.
- `data/`: local datasets and derived frame/table assets; treat as large local state.
- `models/`: local model weights; treat as large local state.
- `refe_repos/`: reference repositories; read-only for normal work.
- `test_vlm/outputs/v13_*`: the V13 single-video evaluation stack (realcartest.mp4).
  Primary evidence for clip-level oracle and budgeted-AQP simulation.

- `garc_eval/outputs/CURRENT_PROJECT_STATE_READONLY_AUDIT.md`: read-only交接报告；start here for any new session.
- `repo_audit_for_codex_v1/`, `codex_research_analysis_v1/`: full artifact inventory + decision log + research assessment. Start here when onboarding.

## Do-Not-Modify Rules

- Do not modify `refe_repos/`.
- Do not commit or stage large files.
- Do not commit or stage `data/`, `models/`, `*.pt`, `*.zip`, `*.png`, `*.parquet`, or `*.csv`.
- Lightweight markdown reports under `garc_eval/outputs/` may be created or modified.
- Lightweight config files may be created or modified.

## Current Validated Findings

### AQP-side (the contribution line)

- **Budget decomposition works** (diversity_prefilter_replay_v1, WEAK_GO):
  on the V13.8 oracle (single video), splitting `proxy_top(P=2B)` from
  `oracle_examine(B)` with mild temporal-spread diversity raises event-recall at
  B=40 from 0.216 (V13.9 best static) to 0.314 (+0.098 abs, +45% rel), Bonferroni-
  significant over 25 H-configs × 200 random repeats. This is a **DB-side
  contribution that does not require a better detector** — it falsifies the
  V13.10 implication that "static methods far below upper bound" is purely a
  proxy-quality problem.
- V13.9/V13.10 single-axis-`B` proxy-top-B methods fail at B=20 (delta vs random
  < +0.10). This holds for the single-axis framing; budget decomposition partly
  reopens it.
- V13.10 adaptive local boost/expand fails (11/15 same-base combos hurt). This
  holds even with a principled confirmed-positive refine rule (H3 in diversity
  prefilter replay). The failure is attributable to event clustering structure,
  not only to proxy weakness — adaptive refine is untested only under better base
  proxies.
- Certificate layer is unproven on the valid V13.8 oracle. The only certificate
  run (v12_1_completion_v1) on a sampled benchmark returned UNDERPOWERED
  (reserved pool < 30 oracle positives). Phase-0.6 power simulation estimates
  ~500 events needed for non-vacuous certificate; V13.8 has 51.

### Workload / mechanism status (the execution side)

- V13.8 full center10 oracle reference is ready: 399 anchors / 94 positive /
  51 stitched events / 0% abstain / 100% complete, on `realcartest.mp4` (~66.5 min),
  Qwen3-VL-32B, ~74 min GPU. Single video, VLM-oracle-relative, no human truth.
- V13.6 center_10s > fixed_5s clip construction on this video: 56% vs 44% positive
  rate, halved oracle calls.
- V13.10 OracleBest@B = min(B,51)/51 (anchor→event 1:1 on this video).
- Hand-crafted cheap proxies (YOLO count, motion energy, center-ROI) plateau at
  AUC ~0.74; `object_count_mean` is the strongest single feature (AUC 0.738) and
  was omitted from V13.9's method enumeration. `center_roi_vehicle_count_mean`
  (AUC 0.535, top-5 precision 0.20) is effectively random — the "ego-corridor"
  design in the handmade proxy is broken at the feature level, not at tuning.
- Predicate `O_enter_ego_path_v0` is object-type-heterogeneous: positives split
  vehicle=67 / pedestrian=13 / cyclist=13. Per-class AUCs differ (motion energy
  AUC 0.704 for pedestrian vs 0.498 for vehicle). A unified cheap proxy cannot
  cover the predicate across object classes.
- Nexar-200 derived-boundary labels are UNRELIABLE for this predicate (VLM positive
  agreement 16%). Do not reuse Nexar-200 for oracle-relative claims.
- SUPG synthetic reproduction is complete at the algorithm level (not full paper).
- KITTI 0005 / combined KITTI are degenerate for SUPG-RT (too small, too positive).
  KITTI is only a pipeline smoke benchmark. Do not present as non-degenerate.
- BDD100K is a valid non-vacuous frame-level SUPG-RT benchmark (image-level only).
- UA-DETRAC is a valid temporal smoke/pipeline benchmark; SUPG-RT often selects all.
- DRIV100 was blocked (no raw videos in the accessible record).
- Do not claim G-ARC theory is complete or formal guarantees beyond what has been
  implemented and tested.
- Do not spend more time tuning KITTI unless explicitly asked.

## Current Target

The deliverable is an AQP method with a clip-level recall certificate. The
immediate priority order:

1. **Budget decomposition variants** — set-cover greedy (not just α-penalty),
   replication on a second long video, theoretical bound on reachable recall as
   a function of (P, B, proxy AUC).
2. **Certificate on V13.8 oracle** — minimal B1 no-repair simulation even if
   recall is low; the goal is to demonstrate the guarantee-layer mechanics, not
   to claim non-vacuous certificate yet.
3. **Second long-video validation** — required before any generalization claim.
   A second diverse driving video needs a small center10 pilot first (avoid
   full 32B scan until non-degenerate).
4. **Proxy-agnostic feasibility bound (theory)** — connect proxy AUC to minimum
   B for γ-recall certificate; this is the cleanest "for any candidate generator"
   claim and is the bridge between mechanism and contribution.
5. **Stronger candidate generator (optional, mechanism)** — ego-path-conditioned
   geometric proxy / CLIP / 8B cascade, framed as producing a higher-AUC
   instance of a candidate generator to test AQP behavior, NOT as a detector
   contribution. Requires new compute (GPU / VLM) and explicit authorization.

Preferred second-video dataset properties, when acquired:

- `N >= 10,000` frames or >= 30 min continuous.
- Positive rate 1–25% under the same V13.6 center10 protocol.
- `proxy AUC` in 0.6–0.85 range (so budget-decomposition is testable, not
  trivially solved by a perfect proxy).
- Different scene type (highway / night / weather) from realcartest to test
  V13.6 prompt stability.

## Query Setting

- Active clip-level predicate: `O_enter_ego_path_v0` (an object starts outside
  the ego future path, then enters or overlaps it, creating potential spatial
  conflict requiring ego attention). All labels VLM-oracle-relative unless a
  human-adjudicated set is built.
- Frame-level fallback predicate (garc_eval line only): `count_car(frame) >= K`.
- Default proxy score rule: `object_count_mean` (best single-feature AUC 0.738 on
  V13.8); `score_fusion_geometry_motion` for ablation. `count_conf_hybrid` if
  available for the frame-level line.
- Do not claim the YOLOv8x pseudo-oracle or Qwen3-VL-32B labels are human truth.
  No human-adjudicated label set currently exists.

## Experiment Policy

Use staged evaluation:

1. Dataset acquisition audit.
2. Controlled subset download.
3. Frame extraction or image sequence loading.
4. Proxy/oracle materialization.
5. `K` calibration.
6. 5-trial smoke.
7. Only if non-degenerate, suggest a 20-trial next step.
8. Do not run 100-trial formal experiments unless explicitly authorized.

Do not run experiments or download datasets unless the user explicitly asks.

## AQP / VLM Budget Experiment Constraints

- Any new experiment must write to a new independent output directory. Do not overwrite existing CSV files, videos, VLM labels, or formal results.
- Conservative VLM full-scan labels are evaluation-only pseudo-oracle labels. Do not use them for ranking, candidate cluster construction, hyperparameter selection, feature training, or learned proxy training.
- Learned proxy train/validation/test splits must be grouped by source video or original video group. Do not randomly split adjacent clips from the same source video across splits.
- Current-stage results must be described as pseudo-oracle or VLM-defined evaluation. Do not describe them as real risk-event ground truth.
- Before implementing a new method, search for and reuse existing scripts, CSV schemas, budget simulation code, and temporal NMS implementations.
- Every experiment must run a smoke test before a full run and must record commands, random seeds, input files, runtime, and failure reasons.
- Random baselines must run at least 100 repeats and report mean, standard deviation, and 95% intervals.
- Every newly added algorithm must include sanity checks. If sanity checks fail, fix the implementation before interpreting results.
- The current stage does not require human audit, audit package generation, or new large-scale VLM inference.
- Final experiment outputs must include a Markdown report, CSV tables, figures, reproducible commands, and a clear `GO`, `WEAK GO`, or `NO-GO` decision.

## Reporting Requirements

- Always write lightweight markdown reports under `garc_eval/outputs/`.
- Reports must distinguish engineering smoke results from research-valid conclusions.
- Reports must explicitly document failed hypotheses, limitations, and uncertainty.
