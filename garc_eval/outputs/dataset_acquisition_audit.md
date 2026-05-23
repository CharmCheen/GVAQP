# Dataset Acquisition Audit

Generated: 2026-05-23

## Scope

Goal: find a larger real traffic/video dataset for non-degenerate SUPG-style frame selection and later clip-level G-ARC experiments.

Required benchmark shape:

- `N >= 10,000` frames if feasible.
- Predicate: `count_car(frame) >= K`.
- Positive rate after `K` calibration: 1% to 20%.
- High proxy score uniqueness.
- Non-vacuous SUPG-RT smoke behavior: `selected_n / N < 0.95`.
- Temporal continuity so selected frames can be merged into candidate clips.
- YOLOv8n is the proxy and YOLOv8x is the pseudo-oracle. YOLOv8x is not human ground truth.

## Preflight Summary

- Repository: `/qiuyeqing/llama_prl/G-ARC`
- Environment setup used: `source env_garc.sh`
- Python: `/qiuyeqing/tools/miniconda3/envs/garc/bin/python`
- Python version: `3.10.20`
- CUDA through torch: available, 2 devices
- Required packages available: `torch`, `ultralytics`, `cv2`, `pandas`, `pyarrow`, `yaml`, `numpy`
- Relevant existing code:
  - real-frame materialization: `garc_eval/experiments/materialize_frame_scores.py`
  - SUPG real-frame runner: `garc_eval/experiments/run_supg_real_frames.py`
  - count calibration: `garc_eval/experiments/calibrate_count_threshold.py`
  - frame-to-clip metrics: `garc_eval/experiments/run_frame_clip_gap.py`, `garc_eval/metrics/frame_to_clip.py`
  - dataset prep: `garc_eval/datasets/build_bdd100k_frame_table.py`, `garc_eval/datasets/extract_uadetrac_from_zip.py`

## Candidate Audit

| Dataset | Local/practical availability | Raw videos or image sequences | Expected frames | Traffic/car suitability | Temporal continuity | Access/license notes | Decision |
|---|---:|---|---:|---|---|---|---|
| BDD100K / Berkeley DeepDrive | Local validation images are present: 10,000 `.jpg` files. Full videos require Berkeley user portal/manual download. | Local copy is 100K image-style validation split, not video clips. Official BDD100K includes 100,000 40s clips at 30 fps, but not locally available as video. | 10,000 local val images; far more in full videos. | Strong road/dashcam traffic content. | Local val images are sampled stills, each effectively separate, so not suitable for clip merging. | Official data is available through Berkeley portal; FiftyOne docs also state source files must be downloaded manually. | Reject for current clip-capable benchmark; keep as frame-only smoke candidate. |
| UA-DETRAC | Local `data/ua_detrac/ua_detrac_training_set.zip` exists, plus 13,932 extracted frames already present. | Image sequences from traffic surveillance videos. | Local controlled subset: 13,932 frames from 8 sequences. Full dataset is reported around 100 sequences / over 140k frames. | Strong traffic surveillance vehicle content. | Yes: sequence frame indices and timestamps are continuous at 25 fps. | Existing repo audit records a Hugging Face mirror with CC-BY-4.0; original UA-DETRAC papers describe real traffic sequences and annotations. | Select. |
| CityFlow | Not locally present. Would require external dataset acquisition. | Synchronized HD traffic-camera videos. | Paper reports over 3 hours from 40 cameras and over 200k boxes. | Excellent traffic-camera fit. | Yes in principle. | AI City / benchmark access may require manual dataset terms or challenge portal. No local archive found. | Reject for this run because UA-DETRAC is already local and usable. |
| D2-City | Not locally present. | Dashcam videos. | Paper reports more than 10,000 clips. | Strong dashcam traffic fit. | Yes in principle. | No local copy found; practical download route not already configured here. | Reject for this run because acquisition would be manual/uncertain. |
| DRIV100 | Prior finding: accessible record lacks raw videos. | Not usable locally as raw video. | Unknown usable frame count here. | Traffic-like target, but blocked. | Blocked by missing raw videos. | Raw-video access blocker remains unresolved. | Reject. |
| KITTI raw | Local, but already validated as too small / too positive / SUPG-RT selects all. | Image sequences. | Too small for target. | Traffic content. | Yes, but insufficient benchmark difficulty. | Local only; not a current target. | Reject except as pipeline smoke. |

References checked during audit:

- BDD100K official site: https://bdd-data.berkeley.edu/
- BDD100K download page: https://bdd-data.berkeley.edu/download.html
- FiftyOne BDD100K docs: https://docs.voxel51.com/dataset_zoo/datasets/bdd100k.html
- CityFlow CVPR page: https://openaccess.thecvf.com/content_CVPR_2019/html/Tang_CityFlow_A_City-Scale_Benchmark_for_Multi-Target_Multi-Camera_Vehicle_Tracking_and_CVPR_2019_paper.html
- D2-City paper page: https://arxiv.org/abs/1904.01975
- UA-DETRAC paper page: https://arxiv.org/abs/1511.04136

## Final Selected Dataset

Selected dataset: **UA-DETRAC controlled local subset**.

Rationale:

- It is already usable in this environment without more dataset download.
- It has more than 10,000 frames: `N = 13,932`.
- It is real traffic surveillance imagery, not synthetic.
- It has temporal continuity across 8 sequences, enabling clip merging.
- Existing cached YOLOv8n/YOLOv8x materialization is present.
- Existing calibration selects `K = 25`, giving a YOLOv8x pseudo-oracle positive rate of `1519 / 13932 = 10.902957%`.

This is the best defensible default because BDD100K local data lacks temporal continuity, while CityFlow and D2-City are not locally acquired and would require manual external acquisition.

## Exact Commands Attempted

Preflight and local availability:

```bash
pwd
sed -n '1,220p' AGENTS.md
env GIT_CONFIG_GLOBAL=/tmp/garc-gitconfig git status --short
bash -lc 'source env_garc.sh && which python'
bash -lc 'source env_garc.sh && python --version'
bash -lc 'source env_garc.sh && python -c "import importlib.util as u; mods=[\"torch\",\"ultralytics\",\"cv2\",\"pandas\",\"pyarrow\",\"yaml\",\"numpy\"]; print({m: bool(u.find_spec(m)) for m in mods}); import torch; print(\"torch\", torch.__version__, \"cuda_available\", torch.cuda.is_available(), \"device_count\", torch.cuda.device_count())"'
find garc_eval -maxdepth 2 -type f
find data -maxdepth 4 -type d
find data/bdd100k/bdd100k/images/100k/val -maxdepth 1 -type f -name '*.jpg' | wc -l
find data/frames/uadetrac -type f -name '*.jpg' | wc -l
ls -lh data/ua_detrac
```

Smoke runs selected for the benchmark report:

```bash
bash -lc 'source env_garc.sh && python -m garc_eval.experiments.run_supg_real_frames --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --budget 1000 --gamma 0.9 --delta 0.05 --trials 5 --outdir garc_eval/outputs/uadetrac_temporal/supg_smoke_5'
bash -lc 'source env_garc.sh && python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget 1000 --gamma 0.9 --delta 0.05 --trials 5 --iou-threshold 0.5 --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir garc_eval/outputs/uadetrac_temporal/clip_smoke_5'
```

No new external dataset download was attempted because a suitable UA-DETRAC archive and extracted controlled subset were already present locally.

## Rejected Dataset Reasons

- BDD100K: locally available validation split is frame-only; it fails the temporal continuity requirement for later clip-level G-ARC experiments.
- CityFlow: strong candidate, but not locally acquired and would require external/manual access; not preferable over available UA-DETRAC for this run.
- D2-City: strong candidate, but not locally acquired and practical download route is unresolved here.
- DRIV100: remains blocked because raw videos are unavailable in the accessible record.
- KITTI: do not tune further; it is only a pipeline smoke benchmark.

## Unresolved Blockers

- Full research-valid conclusions still require human ground truth or a documented accepted pseudo-label protocol. Current labels are YOLOv8x pseudo-oracle labels only.
- CityFlow and D2-City remain plausible future acquisition targets, but need manual/legal acquisition checks before use.
- The selected UA-DETRAC subset is suitable for engineering smoke and likely a 20-trial next step, but this audit does not make a formal research-valid claim.
