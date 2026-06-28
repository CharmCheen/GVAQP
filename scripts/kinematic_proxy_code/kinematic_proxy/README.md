# Kinematic Proxy MVP

This experiment ranks dashcam clips for possible vehicle cut-in / ego-path intrusion using YOLO detections, tracking, and cheap kinematic proxy scores. It does not run VLMs, train models, download datasets, or create ground truth.

## Run

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/00_make_clips.py \
  --config experiments/kinematic_proxy/config.yaml

python experiments/kinematic_proxy/01_detect_track.py \
  --config experiments/kinematic_proxy/config.yaml

python experiments/kinematic_proxy/02_score_proxies.py \
  --config experiments/kinematic_proxy/config.yaml

python experiments/kinematic_proxy/03_make_review_pool.py \
  --config experiments/kinematic_proxy/config.yaml
```

Manually fill labels in:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/review_pool.csv
```

Label convention:

- `1` = positive cut-in / ego-path intrusion
- `0` = negative
- `-1` = uncertain, ignored by evaluation

Then run:

```bash
python experiments/kinematic_proxy/04_eval_pooled.py \
  --config experiments/kinematic_proxy/config.yaml
```

## Smoke Test

To process only the first 30 seconds:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/00_make_clips.py \
  --config experiments/kinematic_proxy/config.yaml \
  --max-duration-sec 30

python experiments/kinematic_proxy/01_detect_track.py \
  --config experiments/kinematic_proxy/config.yaml

python experiments/kinematic_proxy/02_score_proxies.py \
  --config experiments/kinematic_proxy/config.yaml

python experiments/kinematic_proxy/03_make_review_pool.py \
  --config experiments/kinematic_proxy/config.yaml
```

## Outputs

All outputs are written under:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy
```

Expected files:

- `clips.csv`
- `clips/*.mp4`
- `tracks.csv`
- `proxy_scores.csv`
- `review_pool.csv`
- `review_html/index.html`
- `eval_report.md` after manual labeling and evaluation

## VLM Pseudo-GT Budget Simulation

This stage treats full or near-full VLM32B scan results as pseudo-GT / pseudo-oracle labels. It asks whether a limited VLM call budget can recover most VLM32B-positive clips using cheap proxy rankings and temporal allocation. These labels are not formal human ground truth.

Default VLM label file:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels.csv
```

Required schema:

```text
clip_id,start_time,end_time,clip_path,vlm_label,vlm_risk_level,vlm_reason
```

Label convention:

- `1` = VLM32B positive
- `0` = VLM32B negative
- `-1` = uncertain / invalid, excluded from budget denominator

The current config points to an existing VLM32B raw review CSV:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1_review.csv
```

If `vlm_labels.csv` is missing, `05_budget_simulation.py` adapts that explicitly configured review CSV to the current proxy clips by time overlap. If neither a label file nor a configured source exists, it writes:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_template.csv
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/BLOCKED_missing_vlm_labels.md
```

Run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/05_budget_simulation.py \
  --config experiments/kinematic_proxy/config.yaml
```

Outputs:

- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels.csv`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_curve.csv`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_curve_raw.csv`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_selected_clips.csv`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_report.md`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_curve.png`

Interpretation boundary: this simulation measures recovery of VLM32B-positive clips under limited VLM calls. It does not prove real incident detection accuracy, and it inherits VLM32B prompt/model biases.

## Budget Simulation Diagnostics And Event-Level Evaluation

The current VLM pseudo labels are preliminary because they map 67 original 6-second, stride-3 VLM windows onto 102 proxy clips of 5 seconds, stride 2. This can duplicate one VLM decision across adjacent proxy clips and inflate temporal continuity.

`05_budget_simulation.py` now writes mapping diagnostics:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_label_diagnostics.md
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_variants.csv
```

Label variants:

- `broad`: the current mapped `vlm_label`.
- `strict`: requires usable risk-level or affected-ego fields. If the source CSV lacks those fields, this variant is left empty and reported as unavailable.
- `high_confidence`: uses explicit yes/no relevance or confidence fields. In the current raw 32B source, this is equivalent to `broad` because confidence is empty but relevance is explicit yes/no.

Event-level recall:

- Positive clips are sorted by time.
- Adjacent positive clips are merged when their `start_time` gap is `<= event_merge_gap_sec`.
- An event is hit if any selected clip overlaps the event interval.

This event metric is stricter for temporal allocation analysis: high clip recall with low event recall means the policy may be spending budget on overlapping clips from the same positive segment.

Temporal policy sweep outputs:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_policy_sweep.csv
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_policy_sweep_report.md
```

The sweep covers expansion radius, anchor fraction, and temporal NMS gap for uniform expansion, proxy-anchored expansion, and temporal NMS methods.

Best next label-cleaning step:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/TODO_exact_102_clip_vlm_labels.md
```

The cleanest next experiment is to run the same 32B VLM prompt directly on the 102 proxy clips and write exact clip-id-level labels:

```text
clip_id,start_time,end_time,clip_path,vlm_label,vlm_risk_level,vlm_affected_ego,vlm_reason
```

Exact 102-clip labels would remove the main time-overlap mapping ambiguity and make clip-level recall curves more trustworthy.

## Exact 102-Clip VLM Pseudo-GT Labeling And Budget Simulation

The mapped `vlm_labels.csv` file is useful for early simulation, but it maps 67 original 6-second stride-3 Qwen3-VL-32B windows onto the current 102 5-second stride-2 proxy clips. That overlap adapter can inflate temporal continuity because one VLM decision may label multiple adjacent proxy clips.

The exact-label step runs Qwen3-VL-32B directly on every clip in:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/proxy_scores.csv
```

It writes:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_exact_102.csv
```

Exact label schema:

```text
clip_id,start_time,end_time,clip_path,vlm_relevant,vlm_risk_level,vlm_affected_ego,vlm_event_type,vlm_confidence,vlm_reason,raw_response
```

Label variants:

- `broad`: `vlm_relevant == yes`
- `ego_relevant`: `vlm_affected_ego == true`
- `strict`: `vlm_affected_ego == true AND vlm_risk_level in [L2, L3]`

Smoke test:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/06_run_exact_vlm_labels.py \
  --config experiments/kinematic_proxy/config.yaml \
  --limit 3
```

Full exact labeling:

```bash
python experiments/kinematic_proxy/06_run_exact_vlm_labels.py \
  --config experiments/kinematic_proxy/config.yaml
```

The script supports resume. A clip is skipped only when `vlm_labels_exact_102.csv` already contains a valid result for that `clip_id`. Runtime failures are logged to:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_exact_102_failed.csv
```

If the local 32B model path, proxy table, or clip files are missing, the script writes:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/BLOCKED_exact_102_vlm.md
```

Run exact-label budget simulation:

```bash
python experiments/kinematic_proxy/05_budget_simulation.py \
  --config experiments/kinematic_proxy/config.yaml \
  --label-source exact
```

Exact simulation outputs:

- `budget_report_exact_102.md`
- `budget_curve_exact_102.csv`
- `budget_curve_exact_102.png`
- `budget_selected_clips_exact_102.csv`
- `budget_policy_sweep_exact_102.csv`
- `budget_policy_sweep_report_exact_102.md`
- `vlm_label_diagnostics_exact_102.md`
- `vlm_labels_variants_exact_102.csv`

These VLM labels are pseudo-GT for budget allocation analysis. They are not human ground truth and should not be presented as final real-world risk labels.

## Strict Label Variant Analysis

The first exact-label run still produced a high positive rate: broad, ego-relevant, and strict labels are useful diagnostics, but `strict` can remain too broad for rare risk retrieval. This stage derives stricter pseudo-GT variants from the existing exact 102-clip VLM labels without calling the VLM again.

Input:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_exact_102.csv
```

Derived variants:

- `broad`: `vlm_relevant == yes`
- `ego_relevant`: `vlm_affected_ego == true`
- `strict`: `vlm_affected_ego == true AND vlm_risk_level in [L2, L3]`
- `strict_v2`: `strict` plus strong event type, excluding dense traffic, roadside static, close following, and none; low confidence is negative.
- `strict_v3`: keeps L3 ego-relevant events, or high/medium-confidence L2 `cut_in`, `crossing`, `sudden_braking`, or `lane_conflict`; excludes `other` and weak event types.

Run strict label derivation:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/07_strict_label_analysis.py \
  --config experiments/kinematic_proxy/config.yaml
```

Outputs:

- `vlm_labels_strict_variants_exact_102.csv`
- `strict_v2_label_diagnostics.md`

Run strict-variant budget simulation:

```bash
python experiments/kinematic_proxy/05_budget_simulation.py \
  --config experiments/kinematic_proxy/config.yaml \
  --label-source strict_variants
```

Outputs:

- `budget_report_strict_variants_exact_102.md`
- `budget_curve_strict_variants_exact_102.csv`
- `budget_curve_strict_variants_exact_102.png`
- `budget_policy_sweep_strict_variants_exact_102.csv`
- `budget_policy_sweep_report_strict_variants_exact_102.md`

Interpretation: this is post-processing over VLM pseudo-GT fields. If strict_v2 / strict_v3 remain too positive, the right next step is likely a more conservative 32B prompt, not more kinematic-v0 tuning. None of these labels are human GT.

## Conservative VLM Predicate Calibration

When strict_v2 / strict_v3 remain too broad, run a small calibration pass with a more conservative Qwen3-VL-32B prompt before launching any full 102-clip relabeling. This step calls the local 32B model only on a selected calibration subset by default.

Default calibration set:

- 10 clips evenly sampled from old strict positives.
- 5 high count/naive clips with negative pooled review labels when available.
- 5 top-kinematic clips.

Run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/08_calibrate_conservative_vlm.py \
  --config experiments/kinematic_proxy/config.yaml
```

Outputs:

- `conservative_calibration_set.csv`
- `vlm_labels_conservative_calibration_20.csv`
- `conservative_vlm_calibration_report.md`

The script supports `--limit N`, `--overwrite`, and `--full-run`, but full-run should only be used after explicitly deciding that the calibration predicate is acceptable.

## Learned Anomaly Proxy Feasibility Check

This stage asks whether a local DoTA / traffic anomaly / learned video anomaly detector can serve as a cheap proxy anchor for the conservative VLM pseudo-GT budget allocation experiment. It does not download DoTA, does not download checkpoints, does not call Qwen3-VL, and does not fabricate anomaly scores.

Allowed search scope is configured in `config.yaml`:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm
/qiuyeqing/llama_prl/G-ARC/refe_repos
/qiuyeqing/llama_prl/G-ARC/models
/qiuyeqing/llama_prl/G-ARC/try_or_no
```

Run the feasibility gate:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
conda activate garc

python experiments/kinematic_proxy/10_learned_anomaly_proxy.py \
  --config experiments/kinematic_proxy/config.yaml
```

If no runnable detector is found, the script writes:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/BLOCKED_learned_anomaly_proxy.md
```

The blocking report lists searched directories, candidate repos/files, weight-like files, inference/demo entrypoints, and the minimum resources needed from the user: repository path, checkpoint path, inference command, expected input format, and score semantics.

Only when a real detector and checkpoint are available should the adapter produce:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/learned_anomaly_scores.csv
```

Required score schema:

```text
clip_id,start_time,end_time,clip_path,score_learned_anomaly,score_source,score_aggregation,runtime_sec,status,error_message
```

If detector output is frame-level, aggregate to clip-level with max or top-k mean and document that choice. Then merge the real score into:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/proxy_scores_augmented.csv
```

After real scores exist, `05_budget_simulation.py` can be extended/run with methods such as `top_learned_anomaly`, `temporal_nms_learned_anomaly`, `proxy_then_expansion_learned_anomaly`, `ensemble_count_naive_learned`, and `ensemble_all_proxy_learned`.

Current interpretation boundary: without a local learned anomaly repo, pretrained weights, and runnable inference command, continue using count / naive proxies plus temporal NMS, proxy-triggered expansion, and conservative VLM pseudo-GT as the main line. Do not fake `score_learned_anomaly`.
