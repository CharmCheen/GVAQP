# G-ARC Evaluation Framework Build Plan

## 1. Scope and Non-Goals

This document is an implementation plan for a future `garc_eval` experiment framework. It is written for Claude Code to execute later.

Scope:
- Statically audit three third-party repositories under `D:\FDU\PRE-Learn\project\refe_repos`: `supg`, `abae`, and `CS2-insight-agent`.
- Plan adapters, mock data, metrics, experiments, outputs, and staged implementation.
- Use only mock data in the first phase.
- Preserve third-party repositories as read-only dependencies.

Non-goals for this planning round:
- Do not modify files under `refe_repos\supg`, `refe_repos\abae`, or `refe_repos\CS2-insight-agent`.
- Do not implement `garc_eval` code in this round.
- Do not connect real video models.
- Do not run large experiments.
- Do not claim guarantees from CS2 outputs.

## 2. Third-Party Repository Audit

### 2.1 Summary Table

| Repo | Path | Commit | Dirty Worktree | Python Requirement | Dependency Management | Main Entrypoints | Tests / Examples / Notebooks |
|---|---|---:|---|---|---|---|---|
| SUPG | `refe_repos\supg` | `cff4e7eb9b657e79a8f1d8e245e23bcad543126c` | No uncommitted changes observed via `git status --porcelain=v1` | README says Python 3.x; `setup.py` has no `python_requires` | `setup.py`; README lists `pandas`, `numpy`, `feather-format`; code also imports `scipy`, `tqdm` | `supg\experiments\example.py` exposes `run_rt`, `run_pt`; `supg\experiments\experiment.py` has batch experiment runner | Example script exists; no `tests`; no notebooks observed |
| ABae | `refe_repos\abae` | `a9a347263851b5ca510e9632f1c394257f3e343a` | No uncommitted changes observed via `git status --porcelain=v1` | `setup.py` says `python_requires='>=3.7'` | `setup.py`; README says install `ray scipy mystic numpy pandas tabulate tqdm matplotlib` | `abae\algorithm.py`, `abae\online.py`, experiment scripts under `experiments\` | Experiment scripts exist; no `tests`; no notebooks observed |
| CS2-insight-agent | `refe_repos\CS2-insight-agent` | `8edb9abb45abf83be876bc0e81b1078fa9ff544b` | No uncommitted changes observed via `git status --porcelain=v1` | README says backend Python 3.10; frontend Node/Vite | `backend\requirements.txt`; `frontend\package.json` / `package-lock.json` | `backend\app\main.py` FastAPI app; `backend\app\demo_parser.py`; `frontend\src\main.jsx` | Backend tests exist; no notebooks observed |

### 2.2 External Adapter Friendliness

SUPG:
- Easy to call by import if `refe_repos\supg` is added to `PYTHONPATH` or installed editable.
- Best reusable unit is selector classes plus `DFDataSource` / `RealtimeDataSource`.
- README suggests `from supg import run_rt, run_pt`, but `supg\__init__.py` is empty in this checkout. Treat README import as stale.
- Avoid CLI. Use imports inside `garc_eval.adapters.supg_adapter`.

ABae:
- Importable package with `abae\__init__.py` exporting `algorithm`, `data`, and `online`.
- Good for direct import, but code uses global `np.random` and does not return sampled ids or oracle counts cleanly.
- `abae.online.abae` accepts an `oracle_fn`, making it the most adapter-friendly function for first use.
- Precomputed experiment classes in `abae\data.py` contain hard-coded `/future/u/...` paths and should not be used for `garc_eval`.

CS2-insight-agent:
- Main app is a productized FastAPI + React CS2 demo parsing/recording tool, not a generic video retrieval library.
- It can produce reusable highlight-like clip dictionaries from CS2 `.dem` files through `DemoAnalyzer(...).analyze(...)` or the isolated worker.
- It depends on `demoparser2`, Windows/CS2/OBS/FFmpeg paths for recording workflows, and optional LLM provider config.
- For first-stage G-ARC work, use only precomputed or mock CS2-like segment JSON. Do not run CS2, OBS, FFmpeg, or LLM.

### 2.3 Hard-Coded Paths, Environment Variables, and GPU Assumptions

SUPG:
- `supg\datasource\csv_source.py` includes relative dataset paths like `../../data/jackson/2017-12-17.feather` and `../../data/imagenet/source.csv`.
- `DFDataSource` assumes columns named `id`, `label`, `proxy_score`.
- `RealtimeDataSource` accepts arrays and has a seed argument.
- No GPU assumption observed.

ABae:
- `abae\data.py` has `HOME = "/future/u/jtguibas/abae/data/"` and additional `/future/u/jtguibas/aggpred/...` NumPy paths.
- `Records` assumes arrays named `proxy_scores`, `statistics`, `predicates`.
- Sampling uses `np.random.choice(..., replace=False)` and can fail if requested samples exceed stratum size.
- No GPU assumption observed.

CS2-insight-agent:
- Uses config/env variables including `CS2_INSIGHT_LOG_DIR`, `CS2_INSIGHT_WEB_DIR`, `CS2_INSIGHT_PARSE_WORKER_TIMEOUT_SEC`, `CS2_SPEC_PLAYER_SLOT_OFFSET`, `CS2_SPEC_SLOT_ZERO_BASED`, and several recording/clip timing variables.
- Requires `.dem` files for parsing; recording path assumes CS2 executable, OBS WebSocket, GSI, FFmpeg, and Windows-specific behavior in several endpoints.
- AI reviewer uses OpenAI-compatible SDK and provider config, but this must not be used in first-stage probe.
- No explicit GPU ML assumption; hardware H.264 encoders are probed for montage export, but that is outside first-stage probe.

## 3. SUPG Reuse Plan

### 3.1 Core Algorithm Entrypoints

Relevant files:
- `supg\selector\recall_selector.py`: `RecallSelector.select()` implements recall-target selection.
- `supg\selector\importance_precision_twostage.py`: `ImportancePrecisionTwoStageSelector.select()` implements precision-target selection.
- `supg\selector\base_selector.py`: `ApproxQuery(qtype, min_precision, min_recall, delta, budget)`.
- `supg\sampler\imp_sampler.py`: `ImportanceSampler(seed=0, mixing_eps=0.10)` and `SamplingBounds`.
- `supg\datasource\datasource.py`: `DFDataSource` and `RealtimeDataSource`.
- `supg\experiments\example.py`: thin helper `run_rt` / `run_pt`, but it runs 100 trials and has stale import ergonomics.

RT/PT mapping:
- RT query: `RecallSelector(query, source, sampler, sample_mode='sqrt')` with `ApproxQuery(qtype='rt', min_recall=gamma_or_target, delta=delta, budget=budget)`.
- PT query: `ImportancePrecisionTwoStageSelector(query, source, sampler)` with `ApproxQuery(qtype='pt', min_precision=gamma_or_target, delta=delta, budget=budget)`.
- The repo does not expose tau directly. Selectors return selected ids.

### 3.2 Input Format and Naming

Expected input for `DFDataSource`:
- `id`: 0-indexed sequential record id.
- `label`: truth label, cast to `float32` in CSV loader.
- `proxy_score`: score sorted descending internally.

Mapping to `garc_eval` schema:
- `proxy_score` maps to SUPG `proxy_score`.
- `oracle_label` maps to SUPG `label`.
- `frame_id` should be represented by `id`; if no explicit frame id exists, use dataframe row index after sorting by `(video_id, frame_idx)`.

### 3.3 Parameters

SUPG parameters:
- `budget`: `ApproxQuery.budget`.
- `gamma`: use as `min_recall` for RT and `min_precision` for PT. Name in adapter should remain `gamma` for G-ARC consistency.
- `delta`: `ApproxQuery.delta`.
- `seed`: pass to `RealtimeDataSource(seed=seed)` or custom adapter data source; pass to `ImportanceSampler(seed=seed)`. Note `ImportanceSampler.__init__` currently assigns `self.seed = 0` but initializes `RandomState(seed)`, so the random behavior still follows constructor seed.

### 3.4 Outputs

Selector-level output:
- `selected ids`: returned by `.select()`.
- `oracle call count`: `DFDataSource.lookups` can track labels looked up, but current `TrialRunner` calls extra lookups for metric evaluation. Adapter should count only selector lookups by using a fresh source and recording before external metric computation.
- `precision` / `recall`: `TrialRunner` computes record-level precision/recall, but adapter should compute once in `garc_eval.metrics.frame_metrics`.

Not directly returned:
- `threshold_tau`: not explicitly returned. Adapter can infer a proxy threshold after selection:
  - if selected ids are non-empty, `tau = min(proxy_score[selected_ids])`;
  - if selected ids empty, `tau = None`;
  - Risk: selected ids include sampled positives below the threshold, so inferred tau is diagnostic only, not a formal SUPG internal threshold.

### 3.5 Minimal Reuse Strategy

Do not call `supg\experiments\example.py` directly because:
- It runs `nb_trials=100`, which is too heavy for adapter smoke tests.
- It returns aggregated trial rows, not one normalized result.
- It fixes some options and ignores passed `delta` in `run_helper` by setting `delta=0.05` inside `ApproxQuery`.

Recommended:
- Import selectors and sampler directly.
- Build an adapter-owned dataframe with `id`, `label`, `proxy_score`.
- Use `DFDataSource` only if ids are 0-indexed and sequential. Otherwise implement a small adapter-owned source class inside `garc_eval.adapters.supg_adapter` that implements `lookup`, `filter`, `get_ordered_idxs`, `get_y_prob`, `lookup_yprob`.
- Keep third-party source untouched.

### 3.6 `supg_adapter.py` Design

Class: `SupgAdapter`

Responsibilities:
- Load dataframe from in-memory `pd.DataFrame` or parquet path.
- Normalize columns to SUPG naming.
- Validate `budget <= N`, `0 < gamma <= 1`, `0 < delta < 1`.
- Run one selection per call, not the repo's 100-trial helper.
- Return normalized output.

Methods:
- `run_rt(data, proxy_score_col, oracle_label_col, budget, gamma, delta, seed)`.
- `run_pt(data, proxy_score_col, oracle_label_col, budget, gamma, delta, seed)`.

Return:
- `selected_frame_ids`: list of original frame ids or `(video_id, frame_idx)` records.
- `threshold_tau`: diagnostic inferred threshold.
- `frame_precision`: computed from selected frames and `oracle_label`.
- `frame_recall`: computed from selected frames and `oracle_label`.
- `oracle_calls`: selector lookup count only.
- `runtime`: wall-clock seconds.
- `raw_output`: selector class name, selected SUPG ids, inferred tau, source lookup count, any warnings.

Do not modify:
- `supg\__init__.py`.
- `supg\experiments\example.py`.
- selector internals.

## 4. ABae Reuse Plan

### 4.1 Core Algorithm Entrypoints

Relevant files:
- `abae\algorithm.py`: precomputed-data implementation for `Records` objects. Functions include `_execute_ours`, `_execute_uniform`, `execute_ours_with_ci`, and `execute_uniform_with_ci`.
- `abae\online.py`: real-world-style `abae(data_records, proxy_scores, oracle_fn, n1, n2, k=5)` plus `bootstrap`.
- `abae\data.py`: `Records(k, proxy_scores, statistics, predicates)` and dataset-specific subclasses.

Best first-stage entrypoint:
- Use `abae.online.abae(...)` for adapter smoke tests because it accepts data records and an oracle function.
- Alternatively use `abae.data.Records` plus `abae.algorithm._execute_ours(..., return_samples=True)` if all predicates/statistics are precomputed.

### 4.2 Aggregate Support

Native support observed:
- AVG-like aggregate over records satisfying an expensive predicate: code estimates `mean(statistics[predicates])`.

Not directly native:
- SUM is not a first-class function.
- COUNT is not a first-class function.

Adapter policy:
- `run_avg`: direct mapping to ABae estimate.
- `run_count`: adapter-level derived estimate. For first-stage mock tests, estimate count as `N * estimated_predicate_rate`, or use a separate stratified predicate-rate estimator. Mark as ABae-inspired, not native ABae aggregate unless implemented carefully.
- `run_sum`: adapter-level derived estimate. Possible formula: `estimated_avg_positive_statistic * estimated_count_positive`, but this compounds uncertainty. Mark CI semantics as TODO unless a bootstrap over the derived sum is implemented.

### 4.3 Proxy Stratification, Pilot Sampling, Allocation, Bootstrap

Where implemented:
- Proxy stratification: `Records.__init__` sorts by `np.argsort(proxy_scores)` and creates `np.array_split(..., k)`. `online.abae` currently creates `strata = np.array_split(data_records, k)` but does not sort by `proxy_scores`; adapter should sort records by proxy before calling or prefer `Records`.
- Pilot sampling: first loop in `_execute_ours` / `online.abae`, `db.sample(n1, i)` or sample `n1` per stratum.
- Allocation: `weights = np.sqrt(p) * s`, then `allocation = floor(n2 * weights)`.
- Bootstrap CI: `execute_ours_with_ci` in `algorithm.py`, and `bootstrap` in `online.py`.

Risk:
- `online.abae` receives `proxy_scores` but does not use them to order `data_records`. Adapter must sort `data_records` by proxy score descending or ascending consistently before passing them into `online.abae`.

### 4.4 Input Format and Naming

ABae code terms:
- `proxy_scores`: proxy score array.
- `statistics`: statistic values.
- `predicates`: oracle predicate booleans.

Mapping to `garc_eval`:
- `proxy_score_col` -> `proxy_scores`.
- `statistic_value_col` -> `statistics`.
- `oracle_label_col` -> `predicates` as `bool`.

For `online.abae`:
- `data_records` can be tuples or dicts containing statistic and predicate.
- `oracle_fn(record)` must return `(statistic, predicate)`.

### 4.5 Parameters

ABae parameters:
- `budget`: convert into `n1` and `n2`.
  - Recommended default split: `C = 0.5`; `n1 = max(1, floor((budget * C) / num_strata))`; `n2 = budget - n1 * num_strata`.
  - Ensure per-stratum sample sizes do not exceed stratum sizes for replace-free sampling.
- `probability`: confidence level, e.g. `0.95`; maps to `confidence` in bootstrap.
- `seed`: ABae uses global `np.random`; adapter must set and restore or use deterministic wrapper. TODO: decide whether to use `np.random.seed(seed)` inside a local reproducibility guard.
- `num_strata`: maps to `k`.

### 4.6 Outputs

Native outputs:
- `estimate`: aggregate estimate.
- `ci`: `(lower_bound, upper_bound)` for `online.abae`.
- `execute_ours_with_ci` returns arrays of estimates/lower/upper for many trials.

Not returned:
- sampled ids.
- oracle call count.
- per-stratum allocation.

Adapter needs:
- Count oracle calls by wrapping `oracle_fn` and incrementing a counter.
- Capture sampled ids by making `data_records` include stable ids and recording each oracle call.
- Return `raw_output` with `n1`, `n2`, `num_strata`, selected sample ids, and ABae estimate/CI.

### 4.7 `abae_adapter.py` Design

Class: `AbaeAdapter`

Methods:
- `run_avg(data, proxy_score_col, oracle_label_col, statistic_value_col, budget, probability, seed, num_strata)`.
- `run_sum(...)`.
- `run_count(...)`.

Common responsibilities:
- Load dataframe or parquet.
- Validate columns and numeric ranges.
- Sort by proxy score before stratification.
- Build records with stable `record_id`, `statistic_value`, `oracle_label`.
- Wrap oracle function for call count and sampled ids.
- Convert `budget` into `n1/n2`.
- Return normalized result.

Return:
- `estimate`.
- `ci_lower`.
- `ci_upper`.
- `oracle_calls`.
- `runtime`.
- `raw_output`.

Important caveats:
- First implementation should make `run_avg` the canonical ABae path.
- `run_sum` and `run_count` should be explicitly labeled as adapter-derived baselines unless implementation derives mathematically correct CIs.
- Do not use dataset subclasses with hard-coded `/future/u/...` paths.

## 5. CS2 Probe Plan

### 5.1 Main Functionality

CS2-insight-agent is primarily a CS2 demo analysis and recording assistant:
- Parses `.dem` files using `demoparser2`.
- Generates highlight, fail, meme death, and compilation clip dictionaries.
- Optionally enriches clips with LLM commentary and score.
- Controls OBS and CS2 replay recording.
- Provides a montage workbench and FFmpeg export pipeline.

Core parsing files:
- `backend\app\demo_parser.py`: `DemoAnalyzer(...).analyze(...)` returns `ParseResult` with `match_meta`, `clips`, `timeline`, and `round_timeline`.
- `backend\app\demo_parse_isolation.py` and `parse_worker.py`: child-process wrapper around parsing.
- `backend\app\main.py`: FastAPI endpoints `/api/demo/upload`, `/api/demo/parse`, `/api/demo/parse-multi`, `/api/demo/parse-batch`, `/api/demos/{id}/analyze`.

### 5.2 Inputs

Native inputs:
- CS2 `.dem` file.
- `target_player`.
- optional `freeze_to_death_rounds`.
- For recording: CS2 executable/config, OBS WebSocket, GSI, FFmpeg output paths.
- For LLM reviewer: provider API key/base URL/model config.

It does not take:
- generic video files as retrieval input for highlight detection.
- frame directory.
- embeddings.
- natural-language prompt as primary retrieval query.

### 5.3 Outputs

Parsing output:
- `clips`: list of dicts from `Clip.to_dict()`.
- Main clip fields include `clip_id`, `round`, `category`, `weapon_used`, `kill_count`, `start_tick`, `end_tick`, `map_name`, `context_tags`, `killer_name`, `victims`, `killers`, `kill_ticks`, `score_own`, `score_opp`, `round_won`, `clip_min_tick`, `death_tick`, `clip_max_tick`, `source_ticks`, `source_rounds`, `compilation_kind`, and optional AI fields.
- `timeline` and `round_timeline`: round/event metadata with suggested clips and related clip ids.
- Recording output can include local file paths and `recorded_clips` DB rows, but this is outside first-stage probe.

No guaranteed outputs:
- It does not produce calibrated proxy scores for arbitrary G-ARC retrieval.
- It does not produce formal guarantee metrics.
- It does not know target G-ARC recall gamma.

### 5.4 Role in G-ARC

CS2 can be used as:
- candidate generator: yes, for CS2 demo-derived highlight candidates.
- clip-level proxy: maybe, if clip category/tags/kill_count/AI score are converted to a heuristic score.
- reranker: maybe, after another candidate generator.
- auxiliary exploration module: yes, safest first-stage role.

CS2 should not be placed directly in the guarantee main chain because:
- It is domain-specific to CS2 `.dem` event logs.
- Outputs are heuristic clips, not uncertainty-calibrated selections.
- It may miss relevant clips outside its handcrafted highlight/fail categories.
- It depends on parser correctness, target-player choice, and recording settings.
- Its optional LLM reviewer is non-deterministic and external-provider dependent.
- It has no built-in guarantee statement comparable to SUPG recall/precision targets.

### 5.5 First-Stage CS2 Probe

Do not run real CS2 parsing initially. Use mock or precomputed segment JSON.

Input:
- mock ground-truth clips: list of `{video_id, gt_clip_id, start_time, end_time}`.
- mock CS2-like predicted segments: list of `{video_id, segment_id, start_time, end_time, score, category, raw}`.
- `iou_threshold`.

Output metrics:
- `Highlight Recall`: fraction of ground-truth clips hit by at least one predicted segment at IoU threshold.
- `Highlight Precision`: fraction of predicted segments that hit at least one ground-truth clip.
- `Candidate Reduction Ratio`: total predicted candidate duration or count divided by full video duration or full clip universe.
- `IoU Coverage`: mean best IoU over ground-truth clips.
- `Missed Relevant Clip Rate`: `1 - Highlight Recall`.

`cs2_adapter.py` should support:
- real mode later: read precomputed CS2 parse JSON only.
- mock mode first: read synthetic predicted segment JSON.
- no LLM, no OBS, no FFmpeg, no `.dem` parsing in Phase 7 smoke test.

## 6. garc_eval Target Directory Structure

Target root:

```text
garc_eval\
  adapters\
    supg_adapter.py
    abae_adapter.py
    cs2_adapter.py

  baselines\
    proxy_only.py
    oracle_only.py
    supg_rt_plus.py
    supg_pt_plus.py
    abae_record.py
    abae_clip_stress.py
    arc_simplified.py

  data\
    raw\
    processed\
    mock\
    frames.parquet

  metrics\
    frame_metrics.py
    clip_metrics.py
    guarantee_metrics.py

  experiments\
    run_supg_frame.py
    run_supg_clip.py
    run_abae_record.py
    run_abae_clip_stress.py
    run_cs2_probe.py
    run_gvr_sweep.py

  outputs\
    tables\
    figures\
    logs\
    repo_versions.json

  docs\
    data_schema.md
    experiment_protocol.md
```

Responsibilities:
- `adapters\supg_adapter.py`: normalize dataframe/parquet to SUPG inputs; run RT/PT; return standard dict.
- `adapters\abae_adapter.py`: normalize dataframe/parquet to ABae records; run AVG/SUM/COUNT facade; return standard dict.
- `adapters\cs2_adapter.py`: consume mock/precomputed CS2-like segments; compute probe metrics.
- `baselines\proxy_only.py`: select top-k/top-threshold frames or clips by `proxy_score`.
- `baselines\oracle_only.py`: upper-bound baseline using `oracle_label`; used only for sanity checks.
- `baselines\supg_rt_plus.py`: run frame-level SUPG RT, then merge selected frames to candidate clips.
- `baselines\supg_pt_plus.py`: run frame-level SUPG PT, then merge selected frames to candidate clips.
- `baselines\abae_record.py`: record-level aggregate baseline around ABae AVG/COUNT.
- `baselines\abae_clip_stress.py`: stress test ABae when records are frames but evaluation target is clip coverage.
- `baselines\arc_simplified.py`: simple ARC-inspired baseline; likely proxy candidates plus bounded oracle verification. TODO define after metrics are stable.
- `data\raw`: placeholder for future real or external data. Do not require in Phase 1.
- `data\processed`: processed experiment inputs.
- `data\mock`: generated mock datasets and mock predicted segments.
- `data\frames.parquet`: canonical first-stage frame table, generated by mock pipeline.
- `metrics\frame_metrics.py`: frame precision/recall and confusion stats.
- `metrics\clip_metrics.py`: frame-to-clip merge, temporal IoU, clip precision/recall, mIoU.
- `metrics\guarantee_metrics.py`: GVR, multi-seed aggregation, oracle/runtime summaries.
- `experiments\run_supg_frame.py`: smoke and batch runner for frame-level SUPG RT/PT.
- `experiments\run_supg_clip.py`: SUPG-RT+/PT+ runner with frame-to-clip merge.
- `experiments\run_abae_record.py`: ABae record aggregate runner.
- `experiments\run_abae_clip_stress.py`: ABae on clip-stress scenarios.
- `experiments\run_cs2_probe.py`: mock/precomputed CS2 segment coverage probe.
- `experiments\run_gvr_sweep.py`: multi-seed, multi-budget, multi-noise GVR aggregation.
- `outputs\tables`: CSV/JSON result tables.
- `outputs\figures`: optional generated plots.
- `outputs\logs`: run logs, warnings, config snapshots.
- `outputs\repo_versions.json`: third-party repo commit/dirtiness snapshot.
- `docs\data_schema.md`: frozen schema contract.
- `docs\experiment_protocol.md`: how to reproduce smoke and sweep runs.

## 7. Unified Data Schema

First-stage canonical file:

```text
garc_eval\data\frames.parquet
```

Required fields:

| Field | Type | Range / Values | Meaning | Used By |
|---|---|---|---|---|
| `video_id` | str | non-empty | Video or mock sequence id | all clip grouping, CS2 probe |
| `frame_idx` | int | `>= 0`, monotonic per video | Frame index within video | SUPG id mapping, clip merge |
| `timestamp` | float | `>= 0`, seconds | Frame time | clip metrics, CS2 probe |
| `proxy_score` | float | recommended `[0, 1]` | Cheap model/proxy confidence | SUPG, ABae stratification, proxy baselines |
| `oracle_label` | int | `0` or `1` | Expensive truth predicate; positive if frame belongs to relevant target | SUPG labels, ABae predicate, frame/clip metrics |
| `statistic_value` | float | finite numeric | Value to aggregate when predicate is true | ABae AVG/SUM |
| `gt_clip_id` | int or null | positive/zero id or null | Ground-truth clip id for positive frames | clip metrics, CS2 probe |

Recommended fields:

| Field | Type | Range / Values | Meaning | Used By |
|---|---|---|---|---|
| `split` | str | `train`, `val`, `test`, `mock`, etc. | Experiment split | all runners |
| `fps` | float | `> 0` | Frames per second | frame-to-time conversion, merge |
| `proxy_label` | int | `0` or `1` | Thresholded proxy label, optional | proxy-only baselines |
| `oracle_source` | str | `mock`, `human`, `model`, etc. | Where oracle labels came from | reports |
| `dataset_name` | str | non-empty | Dataset/scenario id | output tables, sweeps |

Column use:
- SUPG uses `id` derived from `(video_id, frame_idx)`, `proxy_score`, and `oracle_label`.
- ABae uses `proxy_score`, `oracle_label` as predicate, and `statistic_value`.
- Clip metrics use `video_id`, `frame_idx`, `timestamp`, `oracle_label`, `gt_clip_id`, and `fps`.
- CS2 probe uses ground-truth clips derived from `video_id`, `gt_clip_id`, `timestamp`, plus predicted mock/precomputed segments.

Validation rules:
- No nulls in required fields except `gt_clip_id`.
- `oracle_label=1` should imply `gt_clip_id` is not null in clip experiments. Allow exceptions only for pure frame-level tests.
- `gt_clip_id` should be null when `oracle_label=0`.
- Within each `video_id`, `frame_idx` and `timestamp` should be non-decreasing.
- `proxy_score` should be finite; clip stress tests may include adversarial noise but should still avoid NaN.

## 8. Adapter Interface Design

### 8.1 SupgAdapter

Interface:

```python
class SupgAdapter:
    def run_rt(
        self,
        data,
        proxy_score_col: str,
        oracle_label_col: str,
        budget: int,
        gamma: float,
        delta: float,
        seed: int,
    ) -> dict: ...

    def run_pt(
        self,
        data,
        proxy_score_col: str,
        oracle_label_col: str,
        budget: int,
        gamma: float,
        delta: float,
        seed: int,
    ) -> dict: ...
```

Input:
- `data`: `pd.DataFrame` or parquet path.
- `proxy_score_col`: usually `proxy_score`.
- `oracle_label_col`: usually `oracle_label`.
- `budget`: number of oracle samples/label lookups.
- `gamma`: recall target for RT, precision target for PT.
- `delta`: failure probability.
- `seed`: random seed.

Output:

```python
{
    "selected_frame_ids": [...],
    "threshold_tau": float | None,
    "frame_precision": float,
    "frame_recall": float,
    "oracle_calls": int,
    "runtime": float,
    "raw_output": {...},
}
```

### 8.2 AbaeAdapter

Interface:

```python
class AbaeAdapter:
    def run_avg(
        self,
        data,
        proxy_score_col: str,
        oracle_label_col: str,
        statistic_value_col: str,
        budget: int,
        probability: float,
        seed: int,
        num_strata: int,
    ) -> dict: ...

    def run_sum(...same args...) -> dict: ...
    def run_count(...same args...) -> dict: ...
```

Input:
- `data`: `pd.DataFrame` or parquet path.
- `proxy_score_col`: usually `proxy_score`.
- `oracle_label_col`: usually `oracle_label`.
- `statistic_value_col`: usually `statistic_value`.
- `budget`: total oracle budget.
- `probability`: confidence level, e.g. `0.95`.
- `seed`: random seed.
- `num_strata`: number of proxy strata.

Output:

```python
{
    "estimate": float,
    "ci_lower": float,
    "ci_upper": float,
    "oracle_calls": int,
    "runtime": float,
    "raw_output": {...},
}
```

### 8.3 Cs2Adapter

Interface:

```python
class Cs2Adapter:
    def run_highlight_probe(
        self,
        source,
        ground_truth_clips,
        iou_threshold: float,
    ) -> dict: ...
```

Input:
- `source`: mock segment file, precomputed CS2 output JSON, or later optional `.dem` path. Phase 7 should support only mock/precomputed JSON.
- `ground_truth_clips`: list/dataframe of `{video_id, gt_clip_id, start_time, end_time}`.
- `iou_threshold`: threshold for clip hit.

Output:

```python
{
    "predicted_segments": [...],
    "highlight_recall": float,
    "highlight_precision": float,
    "candidate_reduction_ratio": float,
    "iou_coverage": float,
    "missed_relevant_clip_rate": float,
    "runtime": float,
    "raw_output": {...},
}
```

## 9. Metrics Design

### 9.1 Frame Metrics

`frame_precision`:
- Definition: `TP_selected / max(1, selected_count)`.
- `TP_selected` is number of selected frames with `oracle_label == 1`.
- If no frames selected, return `0.0` and include warning in raw output.

`frame_recall`:
- Definition: `TP_selected / max(1, total_positive_frames)`.
- If no positive frames exist, return `1.0` only for explicitly empty-positive tests; otherwise warn.

### 9.2 Frame-to-Clip Merge

Input:
- selected frame rows sorted by `video_id`, `frame_idx`.

Algorithm:
- Group selected positive/candidate frames by `video_id`.
- Sort by `frame_idx`.
- Start a new predicted clip when the next selected frame is not contiguous within `gap_tolerance`.
- Convert merged frame intervals to time intervals using `timestamp` or `fps`.

Default:
- `gap_tolerance = 0` in Phase 1.
- A later sweep may test `gap_tolerance > 0` to handle sparse selected frames.

For SUPG-RT+ / SUPG-PT+:
- Run frame-level SUPG to get `selected_frame_ids`.
- Map ids back to frame rows.
- Merge selected frames into candidate clips.
- Evaluate candidate clips against ground-truth clips using temporal IoU.

### 9.3 Clip Metrics

`temporal IoU`:
- For intervals `[a_start, a_end]` and `[b_start, b_end]`:
  - `intersection = max(0, min(a_end, b_end) - max(a_start, b_start))`
  - `union = max(a_end, b_end) - min(a_start, b_start)`
  - `IoU = intersection / union` if union > 0 else 0.

`candidate clip hit`:
- A predicted clip hits a ground-truth clip if same `video_id` and temporal IoU >= `iou_threshold`.
- Default first-stage `iou_threshold = 0.5`.

`clip_precision`:
- Fraction of predicted clips that hit at least one ground-truth clip.

`clip_recall`:
- Fraction of ground-truth clips hit by at least one predicted clip.

`mIoU`:
- Mean best IoU over ground-truth clips.
- For each GT clip, compute max IoU with predicted clips from same video; use 0 if none.

### 9.4 Guarantee Metrics

`GVR`:
- Guarantee Violation Rate.
- Definition: fraction of runs where `clip_recall < gamma`.
- For a sweep over seeds: `GVR = mean(clip_recall_seed < gamma)`.

Why GVR is central for G-ARC:
- Frame-level precision/recall can look good while missing entire relevant clips.
- G-ARC's goal is retrieval with guarantees at the clip/task level, not just record-level label efficiency.
- GVR directly measures how often the system violates the target guarantee across stochastic runs, budgets, and proxy noise regimes.

`oracle_calls`:
- Count expensive predicate calls only.
- SUPG: count data source label lookups inside selector, excluding post-hoc metric computation.
- ABae: count wrapped `oracle_fn` calls.
- CS2 probe: for mock/precomputed segments, `oracle_calls = 0` unless evaluating against labels is counted separately. Keep evaluation labels separate from oracle budget.

`runtime`:
- Wall-clock seconds around adapter/baseline call.
- Exclude data generation unless the experiment explicitly measures pipeline runtime.

## 10. Mock Data Pipeline

### 10.1 Mock Frame Generation

Inputs:
- `num_videos`.
- `frames_per_video` or total `N`.
- `fps`.
- number of ground-truth clips per video.
- clip length distribution.
- proxy noise.
- positive rate target.
- seed.

Procedure:
1. Create rows for every `(video_id, frame_idx)`.
2. Set `timestamp = frame_idx / fps`.
3. Sample non-overlapping ground-truth clips per video.
4. Set `gt_clip_id` for frames inside a GT clip; null otherwise.
5. Set `oracle_label = 1` iff frame belongs to a GT clip.
6. Generate `proxy_score`:
   - positive frames: high mean plus noise.
   - negative frames: low mean plus noise.
   - clip boundaries can receive lower confidence to simulate boundary noise.
7. Generate `statistic_value`:
   - simple first version: `normal(mu_pos, sigma)` for positives and `normal(mu_neg, sigma)` for negatives.
   - AVG target can be mean statistic among oracle positives.
8. Optionally create `proxy_label = int(proxy_score >= threshold)`.
9. Write `garc_eval\data\mock\...parquet` and optionally copy/symlink canonical small one to `garc_eval\data\frames.parquet`.

### 10.2 Difficulty Controls

`proxy_noise`:
- Higher noise reduces separability between positive and negative frames.

`clip_length`:
- Short clips make clip recall harder because fewer frames represent each relevant segment.

`gap_between_clips`:
- Small gaps test merge behavior and false merging.

`boundary_noise`:
- Decrease proxy near clip start/end to test whether merge misses clip boundaries.

`positive_rate`:
- Lower positive rate stresses sampling and recall guarantees.

`budget_ratio`:
- `budget = floor(N * budget_ratio)`.
- Sweep low budgets first, e.g. 1%, 2%, 5%, 10%.

### 10.3 First Smoke Experiments

Smoke 1: SUPG frame-level
- Run RT and PT on a tiny mock dataframe.
- Verify non-crashing, selected frames returned, precision/recall computed.

Smoke 2: SUPG-RT+ / SUPG-PT+
- Run frame selection.
- Merge selected frames into candidate clips.
- Verify clip precision/recall/mIoU computed.

Smoke 3: ABae AVG/COUNT
- Run `run_avg` and adapter-derived `run_count`.
- Verify estimate, CI, oracle call count, runtime.

Smoke 4: CS2 probe
- Use mock predicted segments.
- Compute highlight recall/precision, candidate reduction ratio, IoU coverage, missed relevant clip rate.

Smoke 5: GVR sweep
- Run multiple seeds for one small mock scenario.
- Verify output has one row per seed and an aggregate GVR row.

## 11. Experiment Output Format

All runners should write CSV and JSON.

Common fields:

| Field | Meaning |
|---|---|
| `method` | method name, e.g. `supg_rt`, `supg_rt_plus`, `abae_avg`, `cs2_probe` |
| `dataset` | dataset/scenario name |
| `seed` | random seed |
| `budget` | oracle budget |
| `gamma` | target guarantee threshold |
| `delta` | SUPG failure probability or null |
| `iou_threshold` | clip hit threshold |
| `frame_precision` | frame-level precision or null |
| `frame_recall` | frame-level recall or null |
| `clip_precision` | clip-level precision or null |
| `clip_recall` | clip-level recall or null |
| `mIoU` | mean best IoU over GT clips or null |
| `oracle_calls` | expensive label calls |
| `runtime` | seconds |

ABae extra fields:
- `aggregate`: `avg`, `sum`, or `count`.
- `estimate`.
- `ci_lower`.
- `ci_upper`.
- `ci_width = ci_upper - ci_lower`.
- `ci_covered`: whether true aggregate lies inside CI, available for mock data.

CS2 probe extra fields:
- `highlight_recall`.
- `highlight_precision`.
- `candidate_reduction_ratio`.
- `iou_coverage`.
- `missed_relevant_clip_rate`.

Recommended JSON sidecar:
- `config`: full experiment config.
- `repo_versions`: commits and dirty flags.
- `warnings`: adapter caveats.
- `raw_outputs`: optional per-method raw debug payloads.

## 12. Implementation Roadmap for Claude Code

### Phase 0: repo audit and version records

Goal:
- Turn audit metadata into machine-readable version record.

Input:
- Three repo paths.

Output:
- `garc_eval\outputs\repo_versions.json`.

Files:
- `garc_eval\outputs\repo_versions.json`.
- optionally `garc_eval\docs\experiment_protocol.md`.

Acceptance:
- JSON includes path, commit hash, dirty flag, dependency files, and notes for all three repos.
- No third-party repo files modified.

Risks:
- Repos may not be git repos in another environment. Handle missing `.git` gracefully.

### Phase 1: garc_eval skeleton + mock data generator

Goal:
- Create package skeleton and deterministic mock `frames.parquet`.

Input:
- Mock config with seed, N, fps, clip count, noise.

Output:
- `garc_eval\data\frames.parquet`.
- mock GT clips JSON/CSV.

Files:
- `garc_eval\data\mock\...`.
- `garc_eval\docs\data_schema.md`.
- TODO decide exact generator filename, e.g. `garc_eval\data\mock_generator.py` or `garc_eval\experiments\make_mock_data.py`.

Acceptance:
- Can generate a tiny dataset in < 5 seconds.
- Schema validates.
- Positive frames have non-null `gt_clip_id`.

Risks:
- Parquet dependencies (`pyarrow`/`fastparquet`) may be missing. Add fallback CSV or declare dependency.

### Phase 2: metrics implementation

Goal:
- Implement frame, clip, and guarantee metrics.

Input:
- Mock frames and predicted frame/clip ids.

Output:
- Metric dicts.

Files:
- `garc_eval\metrics\frame_metrics.py`.
- `garc_eval\metrics\clip_metrics.py`.
- `garc_eval\metrics\guarantee_metrics.py`.

Acceptance:
- Unit/smoke tests cover empty predictions, perfect predictions, partial overlap, no positives, and multi-video cases.
- `gap_tolerance=0` default is tested.

Risks:
- Inclusive frame intervals vs half-open time intervals can cause off-by-one errors. Use half-open temporal intervals `[start, end)`.

### Phase 3: SUPG adapter + SUPG-RT/PT

Goal:
- Wrap SUPG RT/PT for frame-level experiments.

Input:
- `frames.parquet`.

Output:
- Standard result rows for RT and PT.

Files:
- `garc_eval\adapters\supg_adapter.py`.
- `garc_eval\experiments\run_supg_frame.py`.
- optionally `garc_eval\baselines\supg_rt_plus.py` later.

Acceptance:
- RT/PT run on tiny mock data.
- Output includes selected frame ids, frame precision/recall, oracle calls, runtime.
- No call to `supg\experiments\example.py` 100-trial runner.

Risks:
- SUPG assumes ids are sequential and labels indexable by `id`. Use adapter-owned mapping if needed.

### Phase 4: SUPG-RT+ / SUPG-PT+

Goal:
- Convert frame selections into candidate clips and evaluate clip metrics.

Input:
- SUPG selected frames.
- Ground-truth clips from mock frames.

Output:
- Clip-level rows with `clip_precision`, `clip_recall`, `mIoU`.

Files:
- `garc_eval\baselines\supg_rt_plus.py`.
- `garc_eval\baselines\supg_pt_plus.py`.
- `garc_eval\experiments\run_supg_clip.py`.

Acceptance:
- `gap_tolerance=0` default.
- Clip hit uses IoU threshold.
- Handles empty selected frames.

Risks:
- SUPG may select sparse positives inside a clip, causing fragmented predicted clips. Later gap sweeps can address this.

### Phase 5: ABae adapter + record aggregation

Goal:
- Wrap ABae AVG and adapter-derived COUNT for record-level smoke tests.

Input:
- `frames.parquet`.

Output:
- Estimate, CI, oracle calls, runtime.

Files:
- `garc_eval\adapters\abae_adapter.py`.
- `garc_eval\baselines\abae_record.py`.
- `garc_eval\experiments\run_abae_record.py`.

Acceptance:
- `run_avg` produces estimate and CI.
- Oracle calls are counted.
- `seed` produces repeatable smoke output.

Risks:
- ABae global `np.random` can leak state. Wrap seed handling carefully.
- `replace=False` sampling can fail if strata are too small.

### Phase 6: ABae clip stress test

Goal:
- Show what record-level aggregate methods miss when evaluated on clip coverage.

Input:
- Mock frames with varying clip lengths and proxy noise.

Output:
- ABae aggregate quality plus clip-level stress summaries.

Files:
- `garc_eval\baselines\abae_clip_stress.py`.
- `garc_eval\experiments\run_abae_clip_stress.py`.

Acceptance:
- Demonstrates AVG/COUNT estimate behavior separately from clip recall.
- Writes standard CSV/JSON with ABae extra fields.

Risks:
- ABae is not a clip retrieval method. Report must avoid overclaiming.

### Phase 7: CS2 probe

Goal:
- Evaluate mock/precomputed highlight segments as candidate clips.

Input:
- Mock predicted CS2-like segment JSON.
- Mock ground-truth clips.

Output:
- Highlight recall/precision, candidate reduction ratio, IoU coverage, missed relevant clip rate.

Files:
- `garc_eval\adapters\cs2_adapter.py`.
- `garc_eval\experiments\run_cs2_probe.py`.

Acceptance:
- Runs without CS2, OBS, FFmpeg, demoparser, or LLM.
- Accepts precomputed JSON shape similar to CS2 `clips`.

Risks:
- Real CS2 outputs use ticks, not seconds. Adapter should define conversion via `tick_rate` when real parse JSON is introduced.

### Phase 8: ARC simplified baseline

Goal:
- Add a simple G-ARC/ARC-style baseline for comparison.

Input:
- Mock frames and budget config.

Output:
- Standard result rows.

Files:
- `garc_eval\baselines\arc_simplified.py`.
- possibly `garc_eval\experiments\run_gvr_sweep.py`.

Acceptance:
- Baseline is deterministic under seed.
- Clearly documents guarantee assumptions and limitations.

Risks:
- "ARC" can become underspecified. Keep first version minimal and label it simplified.

### Phase 9: GVR sweep and report

Goal:
- Aggregate guarantee violation across seeds, budgets, proxy noise, and methods.

Input:
- Experiment configs.

Output:
- `outputs\tables\gvr_sweep.csv`.
- `outputs\tables\gvr_sweep_summary.json`.
- optional figures.

Files:
- `garc_eval\experiments\run_gvr_sweep.py`.
- `garc_eval\metrics\guarantee_metrics.py`.
- `garc_eval\docs\experiment_protocol.md`.

Acceptance:
- Reports `GVR = fraction of runs where clip_recall < gamma`.
- Includes method/dataset/seed/budget/gamma/delta/iou_threshold.
- Reproducible with one smoke command.

Risks:
- Runtime can grow quickly with many seeds. Start with tiny smoke sweeps.

## 13. Risks and Open Questions

SUPG:
- README import path appears stale because `supg\__init__.py` is empty. Use direct module imports.
- `threshold_tau` is not an explicit output. Inferred tau is diagnostic only.
- `DFDataSource` assumes `id`, `label`, `proxy_score`; adapter must isolate schema conversion.
- Need inspection result after implementation: whether selector lookup count matches intended oracle budget exactly for both RT and PT.

ABae:
- Native implementation estimates AVG over predicate-positive records, not generic SUM/COUNT.
- `online.abae` does not appear to use `proxy_scores` for sorting; adapter must handle sorting.
- Global RNG usage may make reproducibility fragile.
- Hard-coded dataset paths in `data.py` must be avoided.
- Bootstrap CI for derived SUM/COUNT needs careful design. TODO before claiming CI coverage for those aggregates.

CS2:
- README text is partially mojibake in this checkout, but code structure is readable.
- Native parser consumes CS2 `.dem`, not generic video.
- Real parse output is tick-based; mock probe should use seconds and later add tick conversion.
- Optional AI reviewer and OBS/FFmpeg recording must stay out of first-stage experiments.
- CS2 is not a guarantee component; use as candidate generator/probe only.

Framework:
- Need decide packaging style: plain scripts vs installable package with `pyproject.toml`.
- Need decide test framework and minimal dependencies.
- Need decide parquet backend (`pyarrow` preferred).
- Need define exact mock config file format.

## 14. Recommended First Claude Code Task

Start with a small, verifiable foundation:

1. Create the `garc_eval` skeleton directories.
2. Add `garc_eval\outputs\repo_versions.json` generation with the audited commits and dirty flags.
3. Add `garc_eval\docs\data_schema.md` from Section 7.
4. Implement only a mock data generator and schema validator.
5. Generate one tiny `garc_eval\data\frames.parquet` smoke dataset.

Acceptance for the first task:
- No third-party repo source files are modified.
- `garc_eval\data\frames.parquet` contains the required schema.
- A single command can regenerate the mock data deterministically.
- No SUPG, ABae, or CS2 adapter code is implemented yet.
