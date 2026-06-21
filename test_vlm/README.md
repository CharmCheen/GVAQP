# test_vlm — VLM Kill-Test for Driving Risk Detection

A minimal tool for evaluating VLMs on driving risk detection under a finite VLM budget.
Cuts short clips from long driving videos, runs Qwen3-VL on each, and outputs structured JSONL for analysis.

## Environment

- Conda environment: `garc`
- Python 3.10+, PyTorch, transformers, qwen_vl_utils
- ffmpeg with libopenh264 encoder (for video clipping)

```bash
conda activate garc
```

## Model Path

```
/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-8B-Instruct
```

## Source Videos

```
/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4
/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4
/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/test.mov
```

## Directory Structure

```
test_vlm/
  README.md
  scripts/
    make_clips.py           # Cut short clips from long video
    run_qwen3_vl_batch.py   # Batch-run Qwen3-VL on clips
    eval_vlm_results.py     # Evaluate VLM output
  manifests/                # CSV manifests
  clips/                    # Extracted video clips
  outputs/                  # JSONL results
```

## Usage

### Step 1: Cut Clips

```bash
python test_vlm/scripts/make_clips.py \
    --video /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 \
    --out_dir test_vlm/clips/smoke \
    --manifest test_vlm/manifests/smoke_manifest.csv \
    --clip_len 6 \
    --start 0 \
    --num_clips 10 \
    --stride 30
```

- `--clip_len`: duration of each clip in seconds
- `--start`: start time in the source video
- `--num_clips`: how many clips to cut
- `--stride`: seconds between clip start times

### Step 2: Run Qwen3-VL

```bash
python test_vlm/scripts/run_qwen3_vl_batch.py \
    --model /qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-8B-Instruct \
    --manifest test_vlm/manifests/smoke_manifest.csv \
    --out test_vlm/outputs/qwen3_vl_smoke_fps1.jsonl \
    --fps 1.0 \
    --limit 1
```

- `--fps`: frames per second sampled from the video (lower = fewer frames = faster)
- `--limit`: process only first N clips (useful for quick tests)
- `--resume`: skip clip_ids already in the output file

### Step 3: Evaluate

```bash
python test_vlm/scripts/eval_vlm_results.py \
    --pred test_vlm/outputs/qwen3_vl_smoke_fps1.jsonl
```

## Query Types

| Type | Description |
|------|-------------|
| `general_risk` | Any potential collision, abnormal lane change, cut-in, sudden braking, dangerous close following |
| `lane_cut_in` | Vehicle from adjacent lane suddenly entering ego lane |
| `pedestrian_or_bike_crossing` | Pedestrian/cyclist entering ego path |
| `sudden_braking` | Hard braking, dangerous close following, sudden deceleration ahead |

## VLM Output Format

Each clip produces a JSON:

```json
{
    "relevant": "yes/no/uncertain",
    "risk_type": "collision_risk/lane_cut_in/pedestrian_or_bike_crossing/sudden_braking/none/uncertain",
    "confidence": 0.0,
    "evidence": "one sentence",
    "temporal_location": "early/middle/late/whole_clip/unclear"
}
```

## Manifest Fields

| Field | Default | Description |
|-------|---------|-------------|
| clip_id | auto | Unique clip identifier |
| video_path | auto | Path to clip file |
| source_video | auto | Path to source video |
| start_sec | auto | Clip start time |
| end_sec | auto | Clip end time |
| query_type | general_risk | Type of risk to detect |
| human_label | unknown | Ground truth: `1` = positive, `0` = negative, `unknown` = skip |
| note | auto_generated | Free-form notes |

## First-Round Experiment Suggestions

1. **Start small**: Cut 10 smoke clips from `realcartest_5k.mp4` (6s each, 30s stride).
2. **Test single clip**: Run with `--limit 1` first to verify the pipeline works.
3. **Scale up**: After `--limit 1` works, run all 10 clips.
4. **Record observations**: Note latency, JSON validity rate, and obvious misjudgments.
5. **Add labels**: Manually edit `human_label` in the manifest CSV (0 = negative, 1 = positive) to enable precision/recall metrics.
6. **Iterate**: Adjust `--fps`, clip length, stride, and prompt wording based on results.

## Metrics (when human labels are available)

- **TP**: VLM says "yes", human says 1
- **FP**: VLM says "yes", human says 0
- **FN**: VLM says "no", human says 1
- **TN**: VLM says "no", human says 0
- `uncertain` / `parse_error` / `runtime_error` are excluded from binary metrics
