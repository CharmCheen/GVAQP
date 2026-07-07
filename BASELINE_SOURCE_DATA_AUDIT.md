# BASELINE SOURCE / DATA AUDIT — Connecting Official SUPG / ABae / ARC to G-ARC LATE-AQP

> Read-only audit. No baseline was run, no video/GPU/VLM/YOLO inference was
> performed, no large artifact was created, no file under `outputs/late_aqp_*`
> was modified. All numbers cited are oracle-relative (VLM labels), not human
> ground truth, and no formal guarantee / certificate / statistical bound is
> claimed (per `AGENTS.md`).
>
> Companion to `RC_AQP_PREFLIGHT.md`. The preflight audited the *G-ARC-side*
> SUPG/ABae adapters; this audit inspects the **official reference repos**
> and the **native task semantics** of each baseline, then judges whether they
> can be connected to the 6 LATE-AQP segments under strict replay.

============================================================
1. Environment and path audit
============================================================

- **Working directory:** `/qiuyeqing/llama_prl/G-ARC`
- **Git:** repo had "dubious ownership" → fixed once with
  `git config --global --add safe.directory /qiuyeqing/llama_prl/G-ARC`
  (same one-time workaround recorded in `FAILURES.md` line 81 and
  `RC_AQP_PREFLIGHT.md` line 534). After fix, `git status --short` shows only
  untracked preflight artifacts:
  `?? RC_AQP_PREFLIGHT.md`, `?? outputs/rc_aqp_preflight/`,
  `?? scripts/rc_aqp_mucb_feasibility.py`.
- **Python / env:** `conda` env `garc`, interpreter
  `/qiuyeqing/tools/miniconda3/envs/garc/bin/python`, Python 3.10.20.
- **Path existence:**

  | Path | Exists |
  |---|---|
  | `refe_repos/ARC-main` | yes |
  | `refe_repos/abae` | yes |
  | `refe_repos/supg` | yes |
  | `data/realcam/long_video_data/long_video_dataset3.mp4` | yes |

- **`long_video_dataset3.mp4` size:** 1.1 GB (`ls -lh` → `1.1G`). NOT
  processed in this audit.
- **Metadata near the mp4:** `data/realcam/long_video_data/` contains *only*
  the mp4. No labels, annotations, segment json/csv, oracle traces, proxy
  scores, frame indices, or query configs sit beside it. All annotation /
  proxy / oracle artifacts live under `outputs/` and `experiments/` (see §4),
  keyed by `segment_id` / `video_id`, not as siblings of the mp4.

Commands used (all read-only): `pwd`, `git status --short`, `git config
--global --add safe.directory`, `ls -lh/-la/-R`, `head`, `cat`, `find`,
`python -c "import pandas ..."` for CSV schema/shape inspection only.

============================================================
2. Source inventory for official baselines
============================================================

------------------------------------------------------------
2.1 SUPG  — `refe_repos/supg`
------------------------------------------------------------

- **Exact source path:** `refe_repos/supg/` (git repo, `.git/` present).
- **README / docs:** `refe_repos/supg/README.md` (32 lines). Cites paper
  arXiv:2004.00827. Documents `run_pt` / `run_rt` entrypoints and the
  required CSV schema (`id`, `label`, `proxy_score`).
- **Requirements / env:** `README.md` lines 10-15: python 3.x, pandas,
  numpy, feather-format. `setup.py` declares package `supg` v0.0.1
  (authors Daniel Kang, Edward Gan). Install via `pip install -e .`.
- **Main entrypoint scripts:**
  - `supg/experiments/example.py` — `run_pt(csv_fname, budget, rt)` /
    `run_rt(csv_fname, budget, rt)` (README lines 28-31; `example.py:37-42`).
  - `supg/experiments/experiment.py` — `main()` runs 22 paper experiments
    (`experiment.py:144-167`).
- **Important modules / classes:**
  - `supg/selector/base_selector.py` — `ApproxQuery(qtype∈{pt,rt,prt},
    min_precision, min_recall, delta, budget)` (`base_selector.py:8-28`).
  - `supg/selector/recall_selector.py` — `RecallSelector` (importance-sampled
    recall-target selection; `recall_selector.py:11-129`).
  - `supg/selector/importance_precision_twostage.py` — precision-target.
  - `supg/selector/joint_selector.py`, `naive_recall.py`,
    `uniform_precision.py`, etc.
  - `supg/datasource/datasource.py` — `DataSource` abstract + `DFDataSource`
    (lookup(label), get_ordered_idxs, get_y_prob; `datasource.py:52-84`).
  - `supg/datasource/csv_source.py` — `load_csv_source(csv)` → DFDataSource
    (`csv_source.py:47-51`).
  - `supg/estimator/base_estimator.py` — `Estimator.estimate(...)` +
    `calc_bernoulli_ci` / `calc_std_ci` (`base_estimator.py:6-35`).
  - `supg/sampler/imp_sampler.py` — `ImportanceSampler`.
- **Example commands:** `from supg import run_rt, run_pt; run_pt(csv, B, rt)`
  (README line 28). Or `python supg/experiments/experiment.py`.
- **Expected input format:** CSV with columns `id` (0-indexed sequential),
  `label` (True/False or 0/1), `proxy_score` (float 0-1)
  (`README.md:26`, `csv_source.py:47-51`). Internally also a feather source
  for jackson (`csv_source.py:37-45`).
- **Expected output format:** `TrialRunner.run_trials(...)` returns a
  `results_df` aggregated over `precision, recall, covered, size, nb_true,
  nb_sampled` (`experiment.py:132-141`). The selector itself
  (`RecallSelector.select()`, `recall_selector.py:129`) returns an
  **array of selected record `id`s** — i.e. a record-level index set, not
  intervals.
- **Currently runnable:** YES. Real data is vendored:
  - `data/jackson/2017-12-17.feather` (19 MB, real feather, not LFS).
  - `data/imagenet/source.csv` (1.7 MB, real CSV).
  - `data/onto/source.csv`, `data/tacred/source.csv`.
- **Missing dependencies:** none blocking. `pip install -e .` + pandas +
  numpy + feather-format. The `garc` env already imports supg via the
  G-ARC adapter (`src/garc_eval/adapters/supg_adapter.py`).
- **Budget parameter:** YES — `ApproxQuery.budget` (`base_selector.py:16`).
  Interpreted as number of oracle label lookups (sample size).
- **Oracle / proxy separation:** YES. `proxy_score` (cheap) is read freely;
  `label` (oracle) is only revealed via `DataSource.lookup(idxs)`, which
  increments `self.lookups` (`datasource.py:73-75`). This is the canonical
  oracle-cost accounting.
- **Strict replay support:** PARTIAL. SUPG uses importance sampling
  (`ImportanceSampler`) which is stochastic, but `DFDataSource` takes a
  `seed=123041` (`datasource.py:59`) and `RecallSelector` consumes the
  sampler deterministically given the seed. So per-seed replay is possible
  but it is NOT a fixed oracle-call sequence — re-running with a different
  seed changes which records are queried. An adapter would need to (a) fix
  the seed, (b) record the exact `lookup` id sequence, to make it
  strict-replay-comparable to LATE-AQP's `query_unit` ledger.
- **Output granularity:** RECORD / FRAME level. `select()` returns record
  ids. There is **no temporal grouping into clips/events** anywhere in the
  supg source. (`refe_repos/supg/supg/selector/*.py` — all return id arrays.)

------------------------------------------------------------
2.2 ABae  — `refe_repos/abae`
------------------------------------------------============

- **Exact source path:** `refe_repos/abae/` (git repo, `.git/` present).
- **README / docs:** `refe_repos/abae/README.md` (13 lines). Title:
  "Accelerating Approximate Aggregation Queries with Expensive Predicates".
- **Requirements / env:** `README.md:9`: `pip install ray scipy mystic numpy
  pandas tabulate tqdm matplotlib` then `pip install -e .`. `setup.py`
  declares package `abae` v0.0.1.
- **Main entrypoint scripts:** `refe_repos/abae/experiments/*.py`
  (`groupby_single.py`, `groupby_multiple.py`, `complex.py`, `mse.py`,
  `sensitivity.py`, `lesion.py`, `ci.py`) + `experiments/make_directories.sh`.
- **Important modules / classes:**
  - `abae/algorithm.py` — `_execute_ours(db, n1, n2)` (two-stage stratified
    importance sampling, `algorithm.py:7-42`); `_execute_uniform`
    (`algorithm.py:45-53`); `execute_ours_with_ci` (bootstrap CIs,
    `algorithm.py:76-136`); group-by variant `_execute_group_by_ours_v2`
    (`algorithm.py:177-242`).
  - `abae/data.py` — `Records(k, proxy_scores, statistics, predicates)`
    (`data.py:7-59`); concrete loaders `JacksonRecords`, `CelebARecords`,
    `Trec05PRecords`, `TaipeiRecords`, `SyntheticRecords`,
    `SyntheticComplexPredicatesRecords`, etc.
  - `abae/online.py` — online variant.
- **Example commands:** README line 13: `bash make_directories.sh` then run
  any `.py` in `experiments/`.
- **Expected input format:** a `Records` object holds three parallel arrays:
  `proxy_scores` (cheap), `statistics` (the numeric quantity to aggregate),
  `predicates` (expensive boolean). Loaded from per-dataset CSVs with
  columns `proxy_scores, statistics, predicates` (`data.py:62-127`) or from
  `.npy` files (`data.py:92-98`). Records are stratified into `k` strata by
  proxy-score rank (`data.py:22`).
- **Expected output format:** a **scalar aggregate estimate** —
  `np.sum(m * p / norm)` (`algorithm.py:42`), i.e. the stratified estimate
  of `E[statistic | predicate]`. `execute_ours_with_ci` additionally
  returns `(estimates, lower_bounds, upper_bounds)` bootstrap CIs
  (`algorithm.py:132-136`). NO intervals, NO clips, NO selected ids.
- **Currently runnable:** PARTIALLY.
  - The CelebA `.npy` arrays are real (not LFS pointers — verified magic
    bytes `\x93NUMPY`): `data/data/celeba-{black,blond,brown,gray}.npy`
    (~15 MB each) + `list_attr_celeba.txt`.
  - BUT `abae/data.py:5` hardcodes `HOME = "/future/u/jtguibas/abae/data/"`
    (an absolute path that does not exist locally), and `.gitignore`
    excludes `*.csv`, so the `jackson.csv` / `celeba.csv` / `trec05p.csv` /
    `taipei.csv` CSVs that the `*Records` loaders expect are **NOT vendored**.
    `MovieFacesV2Records` loads from `/future/u/jtguibas/aggpred/data/*.npy`
    (also absent).
  - `SyntheticRecords` / `SyntheticComplexPredicatesRecords` (`data.py:130-
    183`) need no external file and ARE runnable.
- **Missing dependencies:** `ray`, `mystic` (per README). Not checked for
  presence in the `garc` env; an adapter that calls `_execute_ours` directly
  (not the `@ray.remote` wrappers) avoids the ray dependency. `mystic` is
  only used in the group-by optimal-allocation branch
  (`algorithm.py:209-217`).
- **Budget parameter:** YES, two-stage: `(n1, n2)` = stage-1 pilot samples
  per stratum + stage-2 allocation (`algorithm.py:7,23`). Total oracle
  cost ≈ `n1*k + n2` predicate evaluations.
- **Oracle / proxy separation:** YES. `proxy_scores` is free; `predicates`
  is the expensive oracle revealed only via `Records.sample(n, k)`
  (`data.py:34-43`), which draws from the population.
- **Strict replay support:** PARTIAL. Sampling is `np.random.choice` without
  fixed seed in `Records.sample` (`data.py:36,39`). Replay needs a pinned
  seed + a recorded sample-index log.
- **Output granularity:** AGGREGATE (scalar). One number (+ CI) per query.
  No selected records are returned by the core estimator.

------------------------------------------------------------
2.3 ARC  — `refe_repos/ARC-main`
------------------------------------------------------------

- **Exact source path:** `refe_repos/ARC-main/` (NOT a git repo at this path
  — no `.git/`; extracted archive with `.gitattributes` + `.DS_Store`).
- **README / docs:** `refe_repos/ARC-main/README.md` (35 lines). Lists
  pinned deps (pandas 1.5.3, torch 1.13.1+cu117, ultralytics 8.2.51, etc.).
  Says datasets come from blazeit (Stanford) + precomputed labels; `.csv`/
  `.npy` are Git-LFS-tracked.
- **Requirements / env:** `README.md:3-17`. Python 3.x, pandas 1.5.3, numpy
  1.24.4, feather-format, matplotlib, scipy 1.9.1, tqdm, opencv-python,
  torch 1.13.1+cu117, torchvision, ultralytics 8.2.51. No `setup.py`; the
  package `arc/` is run via `sys.path.append('../arc')`
  (`experiments/algorithm_handler.py:2`).
- **Main entrypoint scripts:**
  - `experiments/experiment_main.py` — `main()` runs `overall_dataset`
    experiment (`experiment_main.py:51-70`).
  - `experiments/experiment_handler.py` — `run_experiment` /
    `overall_dataset` / `impact` (`experiment_handler.py:36-143`).
  - `experiments/algorithm_handler.py` — `run_algorithm` dispatches to
    `oracle_only` / `yolo_only` / `cmdn` / `supg` / `_arc`
    (`algorithm_handler.py:62-88`).
- **Important modules / classes:**
  - `arc/arc.py` — `arc(proxy, oracle, proxy_score, oracle_score, B, op,
    constant, tau, confidence, IOUThreshold, clusters, ...)` main loop
    (`arc.py:20-133`). Returns `{'cand_clips', 'B', 'ps_t', 'lb_t', 'ce_t',
    'tc_enabled'}` (`arc.py:131-133`).
  - `arc/cmdn_aqp.py` — `uniform()` / `importance()` simpler baselines that
    sample B frames then `findCandClips` (`cmdn_aqp.py:7-32`).
  - `arc/tools.py` — `findCandClips(score, op, constant, tau)` builds
    continuous clips where `P(score,op,constant)` holds and length ≥ tau
    (`tools.py:49-62`); `generate_oracle_proxy` loads CDF CSV
    (`tools.py:6-20`); `calculate_reliability`, `calculate_start/end`.
  - `arc/score_tools.py` — `P(score, op, constant)` predicate
    (`score_tools.py:14-19`); `entropy`, `update_scores_with_oracle`.
  - `arc/pruning_phase.py`, `arc/refinement_phase.py` — progressive sampling,
    label propagation, `calculate_confidence`.
  - `arc/supg/` — a vendored *copy* of SUPG inside ARC (used by ARC's own
    `SUPGrt+`/`SUPGpt+` handlers, `algorithm_handler.py:35-50`).
- **Example commands:** `cd experiments && python experiment_main.py`
  (README line 33). Config in `experiment_main.py:21-48`.
- **Expected input format:** per-frame arrays read from `data/CDF/<video>.csv`
  with columns `predicates` (ground-truth predicate value per frame) and a
  numeric column named by the constant (e.g. a count), plus `yolov5s` proxy
  column (`tools.py:6-35`). Clusters from
  `data/cluster/<video>/<video>-<thresh>.csv` (`tools.py:23-25`). The query
  is `(op, constant, tau)`: e.g. `op='>', constant=3, tau=300` =
  "continuous runs where per-frame count > 3, lasting ≥ 300 frames"
  (`experiment_main.py:22-31`).
- **Expected output format:** `cand_clips` = Nx2 array of `(start,end)`
  frame intervals (`tools.py:49-62`); plus `B` (oracle calls used),
  `ps_t/lb_t/ce_t` timings, `tc_enabled`. Evaluation in `metrics.py`:
  `calculate_precision_recall_iou` returns **clip-level precision, recall,
  average IoU** vs ground-truth clips (`metrics.py:20-44`).
- **Currently runnable:** **NO.** Every `.csv` and `.npy` under `data/` is a
  Git-LFS pointer (134 bytes each, e.g.
  `data/CDF/amsterdam.csv` → `size 125168543`). Verified:
  `data/CDF/amsterdam.csv`, `data/Everest/amsterdam/mu.npy`,
  `data/cluster/amsterdam/*.csv` are all LFS pointers. `git-lfs` is NOT
  installed (`git: 'lfs' is not a git command`, matches `AGENTS.md` large-
  artifact note). The 16 MB `figure.pptx` is real but irrelevant.
  → ARC's own experiments cannot load any dataset file.
- **Missing dependencies:** torch/torchvision/ultralytics (only needed by
  `preprocessing/`, not by `arc/`+`experiments/`); Git-LFS + the actual
  data blobs. The experiment layer itself only needs numpy/pandas/scipy/
  matplotlib/tqdm.
- **Budget parameter:** YES — `B = int(samplingRate * len(oracle))`
  (`experiment_handler.py:31`), interpreted as number of frame-level
  oracle lookups.
- **Oracle / proxy separation:** YES. `proxy` / `proxy_score` is the cheap
  per-frame signal; `oracle` / `oracle_score` is revealed per-frame via the
  sampling loop (`arc.py:108-114`). `oracle_calls = Algres['B']`
  (`algorithm_handler.py:57`).
- **Strict replay support:** NO (as-shipped). ARC's progressive sampling is
  adaptive (entropy + reliability + label propagation, `arc.py:81-124`),
  and there is no recorded-call-log mechanism. Replay would require pinning
  the RNG and logging each `oracle_score[max_i]` access.
- **Output granularity:** CLIP / EVENT level. `cand_clips` are temporal
  `(start,end)` intervals; metrics are clip-level P/R/IoU
  (`metrics.py:20-44`). This is the **only** of the three baselines with
  native temporal-clip output.

============================================================
3. Native task semantics
============================================================

------------------------------------------------------------
3.1 SUPG
------------------------------------------------------------

- **Record/frame-level approximate selection?** YES. Native unit is an
  individual record (a frame in jackson, an image in imagenet/onto/tacred).
  `RecallSelector.select()` returns a set of record ids
  (`recall_selector.py:125-129`).
- **Precision target, recall target, or both?** BOTH, separately. `qtype
  ∈ {pt, rt, prt}` (`base_selector.py:21-23`). `run_pt` → precision target,
  `run_rt` → recall target (`example.py:37-42`).
- **What does it output?** A selected record-id set. The trial runner also
  reports `precision, recall, covered, size, nb_true, nb_sampled`
  (`experiment.py:132-141`).
- **Temporal clips/events?** NO. No grouping logic exists in the supg
  source. (The G-ARC `try_or_no/experiments/clip_boundary/run_proxy_arc_
  supg_baselines.py` and the never-landed `supg_rt_plus`/`supg_pt_plus`
  plan in `docs/GARC_EVAL_BUILD_PLAN.md` were external attempts to add this.)
- **Residual missing-mass / RecallLCB / stop certificate?** PARTIAL. SUPG
  computes a one-sided recall-related bound: `RecallSelector` uses
  `SamplingBounds(delta)` to bound the right-tail mass and decides how many
  top-ranked records to return (`recall_selector.py:97-108`); the estimator
  layer provides `calc_bernoulli_ci` / `calc_std_ci`
  (`base_estimator.py:25-35`). This is a **selection-size calibration**, not
  a residual missing-mass estimator, not an event-level RecallLCB, and not
  a stop certificate over uncovered events.

------------------------------------------------------------
3.2 ABae
------------------------------------------------------------

- **Aggregate estimation with expensive predicates?** YES. Native task is
  estimating `E[statistic | predicate]` (the mean of a numeric statistic over
  records satisfying an expensive boolean predicate) under a budget
  (`algorithm.py:42`).
- **What aggregate does it estimate?** The conditional mean
  `Σ m_k · p_k / Σ p_k` where `p_k` = predicate positivity rate in stratum
  k, `m_k` = mean statistic among positives in stratum k
  (`algorithm.py:36-42`). Plus bootstrap CIs (`algorithm.py:76-136`).
- **Selected clips/events?** NO. Output is a scalar (+ CI). No record set,
  no intervals.
- **Could it be a residual positive-mass estimator baseline?** ONLY WITH A
  SEMANTICS CHANGE. If `statistic` is set to the constant 1 and `predicate`
  = "unit is a positive event", the ABae aggregate reduces to an estimate
  of the **total positive mass** `P(predicate)`. That is a plausible
  residual-positive-mass estimator (the residual = total mass − observed
  positives). But this is a re-purposing: ABae's native output is a mean,
  not a missing-mass, and it carries no temporal/event structure.
- **Sampling/proxy assumptions:** stratified importance sampling on
  proxy-score rank, two-stage (pilot n1 per stratum → optimal n2 allocation
  ∝ √p·σ, `algorithm.py:20-23`). Assumes proxy score is rank-correlated
  with predicate truth. Assumes records are i.i.d. (no temporal model).

------------------------------------------------------------
3.3 ARC
============================================================

- **Query grammar:** a per-frame numeric predicate `P(score, op, constant)`
  with `op ∈ {'>', '<', '='}` applied to a per-frame statistic `score`
  (e.g. object count), plus a minimum-duration `tau`
  (`score_tools.py:14-19`, `tools.py:49-62`). A "clip" = a maximal
  contiguous run of frames where the predicate holds, of length ≥ tau.
- **Frame-level predicates + duration constraints?** YES, both required.
  `constant` defines the per-frame threshold; `tau` the minimum clip
  length (`experiment_main.py:22-31`).
- **Outputs relevant clips directly?** YES. `findCandClips` returns
  `(start,end)` interval array (`tools.py:49-62`); ARC's main loop refines
  the proxy score via oracle lookups and re-derives clips
  (`arc.py:125-132`).
- **Oracle/proxy overhead counting?** YES. `oracle_calls = B` (frames
  queried), `proxy_calls = len(proxy)` (all frames, cheap)
  (`algorithm_handler.py:57-59`); end-to-end time via
  `calculate_time(oracle_calls, proxy_calls, ...)` + a per-video
  `oracle_time`/`proxy_time` table (`experiment_config.py:11-29`,
  `metrics.py:47-53`).
- **Confidence only, or recall/residual estimates too?** CONFIDENCE ONLY.
  ARC targets a `confidence` level on clip-level IoU
  (`arc.py:66-70`, `calculate_confidence`) and stops when both
  `tau_confidence` and `tau_rel_confidence` ≥ target (`arc.py:66-70`). It
  outputs **clip-level precision/recall/IoU** as evaluation metrics
  (`metrics.py:20-44`) but does NOT output a residual missing-mass, an
  event-level RecallLCB, or a stop certificate over uncovered events.
- **Can current LATE-AQP semantic event queries be expressed in ARC's query
  format?** **NO, not without changing query semantics.** LATE-AQP queries
  are **semantic events** ("enter_ego_path" by a vehicle/pedestrian/
  cyclist — see `center10_vlm_oracle_events.csv` `event_type_majority`,
  `reference_events.csv` `event_type`) defined by a **clip-level VLM
  oracle** over intervals. ARC's query grammar is a **per-frame numeric
  threshold** (`P(score, op, constant)`) on a cheap detector count. A
  semantic event is not expressible as `count > c` on a single per-frame
  statistic — it requires the VLM predicate over a temporal window.
  → ARC is **conditionally applicable**: it can run on the LATE-AQP
  videos ONLY IF the semantic query is first reduced to a per-frame proxy
  score + a per-frame oracle predicate (i.e. the VLM clip label is
  projected down to a frame-level boolean). That projection is exactly the
  representation LATE-AQP does NOT have (LATE-AQP's oracle is bin/clip-level,
  see §4). So ARC validates the "relevant clip query" role on a
  **predicate-defined restricted subset**, not on the full semantic-event
  task.

============================================================
4. Current benchmark / data compatibility
============================================================

- **Where the 6 LATE-AQP segments are defined:**
  `outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv` (and
  `outputs/late_aqp_d3_accounting_fix_v1/segment_info.csv`). Columns:
  `segment_id, video_id, time_start, time_end, duration, atomic_bin_size,
  num_units, num_positive_units, ..., num_events, ..., is_dev`. The 6
  segments:

  | segment_id | video_id | duration_s | num_units(10s) | num_events |
  |---|---|---|---|---|
  | realcartest_0_1570 | realcartest | 1570 | 157 | 20 |
  | realcartest_2000_3200 | realcartest | 1200 | 120 | 20 |
  | realcartest_3200_3830 | realcartest | 630 | 63 | 7 |
  | dataset3_0_1200 | long_video_dataset3 | 1200 | 120 | 6 |
  | dataset3_1200_2400 | long_video_dataset3 | 1200 | 120 | 12 |
  | dataset3_2400_3462 | long_video_dataset3 | 1063 | 107 | 9 |

  `realcartest_2000_3200` is the `is_dev=True` segment
  (`segment_info.csv` row 2).
- **Where ground-truth / full-VLM reference intervals are stored:**
  - Non-dev (realcartest + dataset3): `experiments/v13/v13_8_full_oracle/
    tables/center10_vlm_oracle_events.csv` — columns `event_id, video_id,
    event_start, event_end, event_duration, event_type_majority,
    involved_object_majority, ...` (VLM_ORACLE_RELATIVE).
  - Dev segment: `src/garc_eval/outputs/clean_interval_aqp_full_reference_
    v2_clean_no_leak/reference_events.csv` — columns `event_id, video_id,
    t_start, t_end, ..., event_type, involved_object, ...`
    (VLM_ORACLE_RELATIVE_REUSED_FOR_MINI_FULL_REFERENCE).
  - Per-segment ref files: `outputs/late_aqp_frozen_cross_segment_v1/
    ref_events_realcartest_{0_1570,1630_2000,2000_3200,3200_3830}.csv`.
  - Manifest: `outputs/late_aqp_limited_oracle_frontier_v1/input_manifest.csv`
    rows 2-3.
  - **All labels are VLM-oracle-relative (qwen3_vl_32b), NOT human ground
    truth** (per `AGENTS.md`).
- **Where B7-core / D3-norepair-core outputs are stored:**
  - `outputs/late_aqp_d3_accounting_fix_v1/d3_fixed_frontier_raw.csv` —
    methods `B7-core`, `D3-norepair-core-chunk120`, `D3-core-chunk120-fixed`,
    `LATE-D3-core-chunk120`; per (segment, budget, seed) with
    `event_precision, event_recall, ..., oracle_calls_total,
    strict_replay_or_posthoc` (posthoc_eval for B7-core, strict_replay for
    D3-norepair-core).
  - `outputs/late_aqp_event_diverse_discovery_v1/event_diverse_frontier_
    raw.csv` — all 6 segments, full frontier.
  - `outputs/late_aqp_limited_oracle_frontier_v1/limited_oracle_frontier_
    raw.csv` — realcartest-only frontier.
- **Where oracle replay traces are stored:**
  - `outputs/late_aqp_algorithm_v3_oracle_relative/oracle_call_manifest.csv`
    (per-call manifest; `source_action` mostly `unknown_not_logged` per
    `RC_AQP_PREFLIGHT.md` line 142).
  - `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_calls.csv` +
    `repair_trace_selected_intervals.csv` (clean schema).
  - `outputs/late_aqp_limited_oracle_frontier_v1/oracle_usage_report.md`
    + `oracle_replay_isolation_audit.md` + `oracle_adapter_spec.md`
    (defines `query_unit(bin_idx)` / `query_interval(t_start,t_end)`,
    each = 1 oracle call, never returns `event_id`).
- **Where proxy scores are stored:**
  - `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv` —
    **5-second clip-level** RoadClip proxy + kinematic features
    (`score_naive, score_kinematic, mean_vehicle_count, ...`). **Covers
    only `realcartest`** (segments seg001..seg008 + realcartest_5k + test,
    500 clips, start 0–3932 s). **NO `long_video_dataset3` / dataset3
    proxy scores in this file.**
  - `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
    — interval-level fused cheap signal (`fused_score, cheap_fused_score,
    primary_score, ...`, 11939 rows, 130 cols). Per-interval, not per-frame.
  - `outputs/exsample_aware_replay/atomic_grid_10s.csv` — **10s atomic-bin
    level** with `label (positive/negative), event_id, prior_score_max,
    prior_score_mean` (the bin-level proxy used by LATE-AQP selection).
  - `outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_*.csv` —
    per-segment bin grid with `is_positive, event_id, prior_score_max/
    mean` (realcartest only).
- **Is `long_video_dataset3.mp4` alone sufficient to run baselines?** **NO.**
  The mp4 has no sibling annotations / proxy / oracle. Every baseline needs
  precomputed per-frame or per-bin proxy scores + per-unit oracle labels,
  all of which live in the CSVs listed above (generated in prior dev
  phases), not derivable from the mp4 without GPU/YOLO/VLM runs (which are
  not authorized per `AGENTS.md`).
- **Frame-level labels exist?** **NO.** LATE-AQP's oracle unit is the
  **10-second atomic bin** (`oracle_adapter_spec.md`: `query_unit(bin_idx)`
  → positive/negative). No per-frame boolean label exists for the semantic
  event predicate. (The legacy `reports/evidence_audit_strategy7_budget_
  certificate_cost_v1/EVIDENCE_AUDIT.md` used an older 94-frame-positive
  realcartest oracle, not the current event set — per preflight §4.2.)
- **Frame-level proxy scores exist?** **NO.** The cheapest signal is
  clip-level (5 s RoadClip) or bin-level (10 s `prior_score`). There is no
  per-frame numeric statistic array of the kind ARC's `generate_oracle_proxy`
  consumes.
- **Event-level labels exist?** **YES** — `center10_vlm_oracle_events.csv`
  and `reference_events.csv` (VLM-oracle-relative, not human).
- **Query definitions exist?** PARTIALLY. Event semantics are encoded in
  the `event_type` / `event_type_majority` column (e.g. `enter_ego_path`
  with `involved_object ∈ {vehicle, pedestrian, cyclist}`). There is no
  formal query DSL; the "query" is implicitly "all enter_ego_path events".

**Exact missing items for baseline connection:**
1. No per-frame proxy score array for any of the 6 segments (ARC needs this).
2. No per-frame oracle predicate array (ARC needs this; LATE-AQP only has
   bin/clip-level).
3. No proxy score of any granularity for the 3 `dataset3_*` segments (the
   RoadClip proxy covers realcartest only).
4. No human ground truth — all labels are VLM-oracle-relative.
5. ARC's own reference datasets are LFS pointers (un-fetchable here).

============================================================
5. Applicability matrix
============================================================

| Baseline | Native task | Output unit | Fits current 6 LATE-AQP segments? | Needs adapter? | Valid comparison role |
|---|---|---|---|---|---|
| SUPG | record/frame approximate selection (precision/recall target) | record-id set | Conditionally — if 10s bin = record | Yes (bin→record + temporal grouping) | frame/record selection baseline; **not** event-level residual |
| ABae | aggregate estimation of E[stat\|pred] with expensive predicate | scalar + CI | Conditionally — only as aggregate/mass estimator | Yes (semantic = total positive mass) | aggregate estimation baseline; **not** event-level coverage |
| ARC | predicate-defined continuous-clip query | clip (start,end) intervals | Conditionally — requires per-frame predicate; LATE-AQP query is clip-level VLM semantic | Yes (semantic→per-frame predicate projection) | relevant clip query baseline; **conditional** on predicate redefinition |

Strictness notes (per `AGENTS.md`):
- SUPG: source confirms record-level selection; no clip/event grouping
  exists in `refe_repos/supg/supg/selector/*.py`. Role = frame/record
  selection baseline only.
- ABae: source confirms scalar aggregate output (`algorithm.py:42`); no
  temporal/event output. Role = aggregate estimation baseline only; usable
  as residual-mass estimator only after re-purposing statistic≡1.
- ARC: source confirms it IS a relevant-clip-query system (`findCandClips`,
  clip-level P/R/IoU in `metrics.py`). But its query grammar is a per-frame
  numeric predicate (`P(score,op,constant)`), not a clip-level VLM semantic
  predicate. Marked **conditionally applicable**, not failed: it is the
  correct baseline role, but the current LATE-AQP semantic queries cannot
  be expressed in ARC's grammar without projecting the VLM clip label down
  to a per-frame boolean (a semantics change).

============================================================
6. Adapter design (no implementation)
============================================================

Common target schema (all adapters emit one row per segment×baseline×query×
budget×seed):

```
segment_id, baseline_id, query_id, budget_abs, budget_ratio, oracle_calls,
proxy_cost, returned_intervals, event_precision, event_recall,
unique_event_coverage, duplicate_rate_if_available, B_90_90_if_computable,
residual_estimate_available, recall_lcb_available,
stop_certificate_available, applicability_note
```

------------------------------------------------------------
6.1 SUPG adapter
------------------------------------------------------------

- **Record↔interval mapping:** treat each 10s atomic bin (from
  `segment_info.csv` / `atomic_grid_10s.csv`) as one SUPG record (`id` =
  bin_idx, `label` = `is_positive`, `proxy_score` = `prior_score_max` or
  `fused_score`). This matches the existing
  `src/garc_eval/adapters/supg_adapter.py` `_prepare_source` which already
  accepts a DataFrame with `id,label,proxy_score`.
- **Oracle replay input:** the bin-level `OracleAdapter.query_unit(bin_idx)`
  from `oracle_adapter_spec.md` is the SUPG `DataSource.lookup`. Each
  lookup increments `oracle_calls`; cap at `budget`.
- **Temporal grouping (the missing `supg_rt_plus`):** after SUPG returns a
  set of positive bins, merge temporally adjacent positive bins (gap ≤ one
  bin = 10 s) into intervals using the same merge rule LATE-AQP uses
  (documented in `late_aqp_frozen_cross_segment_v1/repair_trace_logging_
  spec.md`).
- **Oracle-call counting:** `DFDataSource.lookups` already counts
  (`datasource.py:74`). Map directly to `oracle_calls`. SUPG also reads
  `proxy_score` freely → `proxy_cost = num_bins` (cheap, full scan).
- **Event P/R:** computed by the shared evaluator against
  `center10_vlm_oracle_events.csv` / `reference_events.csv` at IoU ≥ 0.3
  (the LATE-AQP threshold, per `RC_AQP_PREFLIGHT.md` line 421).
- **residual_estimate_available:** **false** for SUPG.
- **recall_lcb_available:** **false** (SUPG's `SamplingBounds` calibrates
  selection size, not event-recall LCB — do not relabel it).
- **stop_certificate_available:** **false**.
- **applicability_note:** "frame/record selection baseline; bin=record;
  temporal grouping added by adapter (not in upstream SUPG)."

------------------------------------------------------------
6.2 ABae adapter
------------------------------------------------------------

- **Can it estimate total positive mass / residual positive mass?** YES, if
  re-purposed: set `statistic ≡ 1` for all records and `predicate` =
  bin-positive. Then ABae's aggregate `Σ m_k p_k / Σ p_k` collapses to an
  estimate of `P(predicate)` = total positive-mass fraction
  (`algorithm.py:42` with m_k≡1). Residual = estimated_total_mass −
  observed_positive_mass.
- **Unit:** the record = the 10s bin (same as SUPG adapter). `k` strata by
  `prior_score` rank. NO event-level / temporal unit in ABae natively.
- **Residual-estimation baseline role:** valid AS A SCALAR ESTIMATOR of
  uncovered positive bin mass, reported as `residual_estimate_available =
  true`. It does NOT produce intervals, so `returned_intervals` = [] and
  `event_precision / event_recall / unique_event_coverage` are NOT
  computable from ABae alone — they would require pairing ABae's mass
  estimate with a separate selector's intervals.
- **Why it cannot be evaluated on event-level coverage directly:** ABae
  outputs a scalar over bins, not a set of intervals. Event coverage
  requires hitting reference events with returned intervals, which ABae
  does not produce. It can only be a **residual-estimation baseline**
  feeding a coverage metric computed by another component.
- **applicability_note:** "aggregate estimation baseline; re-purposed as
  total-positive-mass estimator (statistic≡1); no interval output;
  residual_estimate_available=true; event P/R N/A without external selector."

------------------------------------------------------------
6.3 ARC adapter
------------------------------------------------------------

- **Can the current LATE-AQP query be expressed?** NO directly. LATE-AQP
  query = clip-level VLM semantic predicate ("enter_ego_path"). ARC query =
  per-frame numeric predicate `P(score, op, constant)` + `tau`. The
  semantic event cannot be written as `count > c` on a per-frame statistic.
- **Restricted predicate-query subset where ARC IS valid:** define a
  per-frame proxy score = the bin's `prior_score_max` broadcast to frames
  (or the RoadClip 5s clip score broadcast to frames), and a per-frame
  oracle predicate = "frame falls in a positive bin". Then ARC's query
  `op='>', constant=θ, tau=T_frames` becomes "continuous runs of frames
  whose broadcast proxy > θ, length ≥ T" — a **proxy-driven clip query**
  that is comparable to LATE-AQP's proxy-driven bin selection, evaluated on
  the same reference events. This is a faithful comparison of ARC's
  clip-query machinery on the LATE-AQP segments, but it is NOT the same
  query semantics as the VLM semantic event.
- **ARC returned clips → event metrics:** `cand_clips` (frame intervals)
  are mapped to event P/R via the same IoU≥0.3 evaluator
  (`metrics.py:calculate_precision_recall_iou` already does exactly this).
- **Confidence/overhead → common ledger:** `oracle_calls = B` (frames),
  `proxy_cost = len(proxy)` (all frames, cheap) per `algorithm_handler.py:
  57-59`. `confidence` target maps to a calibration field but NOT to
  `recall_lcb_available` (ARC confidence is clip-IoU confidence, not event-
  recall LCB). `stop_certificate_available` = **false** (ARC stops on
  confidence, but per `RC_AQP_PREFLIGHT.md` Gate 2, per-segment safe
  stopping is statistically weak; do not relabel ARC's stop as a
  certificate).
- **residual_estimate_available:** **false**.
- **applicability_note:** "relevant clip query baseline; runs only on a
  restricted per-frame-predicate projection of the semantic query; not
  equivalent to the VLM semantic event query; confidence is clip-IoU, not
  event-recall LCB."

============================================================
7. Smoke-run feasibility (only)
============================================================

No full experiments. For each repo, decision on a tiny smoke run:

------------------------------------------------------------
7.1 SUPG — SAFE to smoke
------------------------------------------------------------

- One segment, one query, one budget, no GPU/video, official code only.
- Feasible on the **existing small real CSV** `refe_repos/supg/data/
  imagenet/source.csv` (1.7 MB, real): `from supg import run_rt;
  run_rt('../../data/imagenet/source.csv', budget=100, rt=0.9)`.
- This uses official code, produces a small `results_df`, no video, no
  oracle/VLM. Strict replay is per-seed (fix `seed`).
- **Not attempted in this audit** (read-only mandate; would create a small
  output). Recommended as the first safe smoke if execution is authorized.

------------------------------------------------------------
7.2 ABae — conditionally safe to smoke
------------------------------------------------------------

- The native CSV datasets are **gitignored and absent** (`.gitignore`
  `*.csv`); `HOME = "/future/u/jtguibas/abae/data/"` is a dead path.
  → Cannot smoke `JacksonRecords` etc. without first vendoring CSVs.
- `SyntheticRecords(k, alpha, beta, N)` (`data.py:130-137`) needs no
  external file and IS runnable: instantiate, call `_execute_ours(db, n1,
  n2)` directly (bypasses `@ray.remote`, avoids the `ray`/`mystic` deps).
- **Not attempted in this audit.** If authorized, the safe smoke is:
  instantiate `SyntheticRecords(k=10, alpha=0.1, beta=0.5, N=100000)`,
  call `abae.algorithm._execute_ours(db, n1=50, n2=200)` — pure numpy,
  small output, official code only.
- Missing precomputed inputs for a LATE-AQP-segment smoke: a bin-level
  `(proxy_score, statistic≡1, predicate)` Records object for one segment,
  which is cheap to build from `atomic_grid_10s.csv` but is an adapter, not
  a native smoke.

------------------------------------------------------------
7.3 ARC — NOT smokeable as-shipped
------------------------------------------------------------

- Every dataset file under `data/` is a Git-LFS pointer (134 bytes).
  `git-lfs` is not installed (`git: 'lfs' is not a git command`).
  → `experiments/experiment_main.py` cannot load any CDF/cluster CSV.
- A native smoke therefore requires either (a) `git lfs install && git lfs
  pull` (needs network + LFS install — not done, per `AGENTS.md` large-
  artifact + no-download rules), or (b) constructing a tiny synthetic
  `proxy / oracle / proxy_score / oracle_score / clusters` numpy array in
  memory and calling `arc.arc(...)` directly. Option (b) uses official code
  only, no video, no LFS, small output — **feasible but not attempted in
  this audit** (would be a synthetic-input smoke, not a LATE-AQP-segment
  smoke).
- **Exact command plan for a future ARC-on-LATE-AQP smoke (not run here):**
  1. Build per-frame arrays for one realcartest segment from
     `grid_realcartest_<seg>.csv` (bin→frame broadcast of `prior_score_max`
     as proxy, `is_positive` as oracle predicate), choose `op='>'`,
     `constant`=median prior score, `tau`=30 frames (3 bins).
  2. `from arc.tools import generate_cluster` substitute the broadcast
     cluster labels.
  3. `from arc.arc import arc; res = arc(proxy, oracle, proxy_score,
     oracle_score, B=30, op='>', constant=θ, tau=30, confidence=0.9,
     IOUThreshold=0.3, clusters=clusters)`.
  4. Evaluate `res['cand_clips']` against `ref_events_<seg>.csv` with the
     shared IoU≥0.3 evaluator.
  - **Missing precomputed inputs:** per-frame proxy + per-frame oracle
    predicate arrays for the 6 segments (do not exist — see §4). Building
    them is an adapter action, not a metadata-only command.

============================================================
8. Claim implications
============================================================

Wording discipline (per `AGENTS.md` `never` list and `RC_AQP_PREFLIGHT.md`
§6):

- SUPG source **exists and is runnable** (`refe_repos/supg`, real data).
  It is a **frame/record selection** method with a recall-target selection-
  size calibration (`SamplingBounds`), NOT an event-level residual / Recall
  LCB / stop-certificate system. Saying "SUPG is absent" is **false**.
  Saying "SUPG provides event-level residual missing-mass" is **false**.
- ABae source **exists** and its native task is **aggregate estimation with
  expensive predicates** (`algorithm.py:42` scalar). Calling it "irrelevant"
  is **wrong** — it is the correct **aggregate-estimation / residual-mass**
  baseline role, but only after re-purposing `statistic≡1`. It does NOT
  output temporal events.
- ARC is a **relevant clip query** system (`findCandClips` + clip-level P/R
  /IoU). Saying "ARC cannot handle clips" is **false**. ARC **handles
  predicate-defined continuous clips** by design (`tools.py:49-62`,
  `metrics.py:20-44`). However, the current LATE-AQP **semantic** event
  queries (clip-level VLM predicate) **cannot** be expressed in ARC's
  per-frame numeric predicate grammar without a semantics-changing
  projection. So ARC is **conditionally applicable**, not failed.
- None of SUPG / ABae / ARC provide an **event-level residual missing-mass
  / RecallLCB / stop certificate** (confirmed by source: SUPG has selection-
  size bounds only; ABae has bootstrap CIs on a scalar mean; ARC has clip-
  IoU confidence). This is consistent with `RC_AQP_PREFLIGHT.md` Gate 2
  (per-segment safe stopping statistically weak) — do **not** claim safe
  stopping as the main RC-AQP contribution.

**Implication for RC-AQP:** the three official baselines cover three
distinct roles (record selection / aggregate estimation / clip query) but
**none** covers event-level residual certification on the LATE-AQP
semantic-event task. A faithful comparison therefore requires (a) a SUPG
bin-adapter with temporal grouping, (b) an ABae total-mass re-purpose, and
(c) an ARC restricted-predicate projection — all three are **adapters**,
not native runs, and all three will report `residual_estimate_available =
false` (except ABae-as-mass-estimator) and `stop_certificate_available =
false`.

**Final recommendation: C — some baselines are not applicable to the
current query semantics without changing query semantics.**

- SUPG: applicable as a record-selection baseline via a bin adapter (no
  semantics change, just granularity).
- ABae: applicable as an aggregate/residual-mass baseline via a statistic≡1
  re-purpose (no temporal output).
- ARC: **conditionally applicable** — its clip-query machinery is relevant,
  but the LATE-AQP semantic-event query cannot be expressed in ARC's per-
  frame predicate grammar without projecting the VLM clip label to a per-
  frame boolean. ARC therefore defines a **restricted predicate-query
  subset** comparison, not a full semantic-event comparison.
- Because ARC (the only clip-level baseline) requires a semantics change to
  run on the full LATE-AQP task, RC-AQP claims that compare against "ARC on
  the same semantic-event query" are **not valid** without explicitly
  scoping ARC to the restricted predicate-defined subset. This is
  recommendation C, not B (the data/adapters exist) and not A (do not
  proceed to a wrapper that claims full semantic-task parity for ARC).

============================================================
Appendix — execution record
============================================================

**Files created:** `BASELINE_SOURCE_DATA_AUDIT.md` (this file) only.
**Files modified:** none. No `outputs/late_aqp_*`, `PROJECT_STATE.md`,
`HANDOFF.md`, `CLAIMS_LEDGER.md`, `FAILURES.md`, `EXPERIMENT_REGISTRY.csv`,
`TASK_QUEUE.yaml`, or `AGENTS.md` was touched.

**Commands run (all read-only):**
- `pwd`, `git status --short`, `git config --global --add safe.directory`
- `which conda/python`, `python --version`
- `ls -lh/-la/-R` on `refe_repos/{ARC-main,abae,supg}`,
  `data/realcam/long_video_data/`, `outputs/late_aqp_*`,
  `experiments/roadclip_budget_v2/...`
- `head` / `cat` on README.md, setup.py, .gitattributes, .gitignore,
  source files, CSV headers
- `find` for CSV/proxy/oracle/segment files
- `python -c "import pandas as pd; pd.read_csv(...)"` for schema/shape/
  segment-coverage inspection only (no writes, no model inference)
- `git lfs version` (confirmed not installed)
- `xxd`/`head -c` on `.npy` magic bytes to distinguish real arrays from
  LFS pointers

**Commands NOT run (per hard constraints):** no `git push/commit/add`, no
oracle/VLM/YOLO/GPU, no `git lfs pull`, no processing of the 1.1 GB mp4,
no full baseline run, no new experiment under `outputs/late_aqp_*`.

**Source paths inspected:**
- `refe_repos/supg/` — README, setup.py, `supg/__init__.py`,
  `supg/selector/{base_selector,recall_selector}.py`,
  `supg/estimator/base_estimator.py`, `supg/datasource/{datasource,
  csv_source}.py`, `supg/experiments/{example,experiment}.py`,
  `data/{jackson,imagenet,onto,tacred}/`
- `refe_repos/abae/` — README, setup.py, `.gitignore`,
  `abae/{algorithm,data}.py`, `experiments/`, `data/data/`
- `refe_repos/ARC-main/` — README, `.gitattributes`,
  `arc/{arc,arc_config,cmdn_aqp,tools,score_tools,pruning_phase,
  refinement_phase}.py`, `experiments/{experiment_main,experiment_config,
  experiment_handler,algorithm_handler,metrics,results_io}.py`,
  `data/{CDF,cluster,Everest,SUPG+,YOLOv5s}/`, `preprocessing/`

**Data paths inspected:**
- `data/realcam/long_video_data/long_video_dataset3.mp4` (1.1 GB, untouched)
- `outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv`,
  `event_diverse_frontier_raw.csv`, `FINAL_REPORT.md`
- `outputs/late_aqp_limited_oracle_frontier_v1/{input_manifest.csv,
  FINAL_REPORT.md, oracle_adapter_spec.md, oracle_usage_report.md,
  oracle_replay_isolation_audit.md, limited_oracle_frontier_raw.csv}`
- `outputs/late_aqp_d3_accounting_fix_v1/d3_fixed_frontier_raw.csv`
- `outputs/late_aqp_frozen_cross_segment_v1/{grid_realcartest_*.csv,
  ref_events_*.csv, repair_trace_calls.csv}`
- `outputs/late_aqp_algorithm_v3_oracle_relative/oracle_call_manifest.csv`
- `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv`
- `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- `outputs/exsample_aware_replay/atomic_grid_10s.csv`
- `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/
  reference_events.csv`
- `src/garc_eval/adapters/{supg_adapter,abae_adapter}.py`,
  `src/garc_eval/baselines/{u_ci,u_noci,uniform_aggregation}.py`
- `RC_AQP_PREFLIGHT.md`

**Are the official SUPG / ABae / ARC runnable?**
- SUPG: **YES** (real data vendored; `pip install -e .` already wired via
  G-ARC adapter).
- ABae: **PARTIALLY** (Synthetic records runnable; native CSV datasets
  gitignored/absent; `HOME` path dead; `ray`/`mystic` may be missing).
- ARC: **NO as-shipped** (all data are LFS pointers; `git-lfs` absent).
  The `arc/` + `experiments/` code layer is importable but has no data to
  load.

**Was any smoke run attempted?** **NO.** This audit is strictly read-only.
The smoke-run plans in §7 are documented for a future authorized session.

**Missing evidence (registered, not invented):**
- Per-frame proxy score + per-frame oracle predicate arrays for the 6
  LATE-AQP segments (needed for ARC; do not exist).
- Any proxy score for the 3 `dataset3_*` segments (RoadClip proxy covers
  realcartest only).
- Human-validated labels (all labels here are VLM-oracle-relative).
- A clean per-call unified oracle ledger with `source_action` lineage
  (gap noted in `RC_AQP_PREFLIGHT.md` line 141).
- ARC reference datasets (LFS, un-fetchable here).

**Recommended next task:** implement the three read-only **adapter designs**
of §6 as design-only specs (not code), scoped as: (1) SUPG bin-adapter
(record selection, no semantics change), (2) ABae total-mass re-purpose
(aggregate, no temporal output), (3) ARC restricted-predicate projection
(semantics-changing — must be explicitly scoped as a predicate-defined
subset, not full semantic-event parity). Do NOT proceed to a wrapper that
claims ARC runs on the full LATE-AQP semantic-event query. This is
recommendation **C**.
