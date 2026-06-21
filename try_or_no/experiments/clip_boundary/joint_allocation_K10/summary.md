# Joint Allocation Kill Experiment Summary

- CSV: `/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv`
- Label: `label_K10`
- Frames: 5000
- True clips: 18

## Method Comparison (best per budget)

### Budget 50

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.056 | 1.000 | 0.0% | 50 | 0 |
| audit_only | 0.056 | 1.000 | 100.0% | 0 | 50 |
| fixed_mix_80_20 | 0.000 | 0.000 | 0.0% | 40 | 10 |
| fixed_mix_50_50 | 0.056 | 0.500 | 0.0% | 25 | 25 |
| adaptive_greedy | 0.056 | 0.500 | 50.0% | 25 | 25 |
### Budget 100

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.056 | 0.500 | 0.0% | 100 | 0 |
| audit_only | 0.111 | 1.000 | 100.0% | 0 | 100 |
| fixed_mix_80_20 | 0.111 | 1.000 | 50.0% | 80 | 20 |
| fixed_mix_50_50 | 0.111 | 0.667 | 33.3% | 50 | 50 |
| adaptive_greedy | 0.111 | 0.667 | 33.3% | 50 | 50 |
### Budget 200

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.056 | 0.500 | 0.0% | 200 | 0 |
| audit_only | 0.111 | 0.222 | 88.9% | 0 | 200 |
| fixed_mix_80_20 | 0.111 | 0.400 | 20.0% | 160 | 40 |
| fixed_mix_50_50 | 0.167 | 0.750 | 50.0% | 100 | 100 |
| adaptive_greedy | 0.167 | 0.300 | 70.0% | 50 | 150 |
### Budget 400

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.167 | 0.600 | 80.0% | 400 | 0 |
| audit_only | 0.222 | 0.308 | 84.6% | 0 | 400 |
| fixed_mix_80_20 | 0.222 | 1.000 | 75.0% | 320 | 80 |
| fixed_mix_50_50 | 0.222 | 0.667 | 50.0% | 200 | 200 |
| adaptive_greedy | 0.167 | 0.500 | 33.3% | 375 | 25 |
### Budget 800

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.389 | 0.500 | 35.7% | 800 | 0 |
| audit_only | 0.222 | 0.250 | 87.5% | 0 | 800 |
| fixed_mix_80_20 | 0.389 | 0.583 | 41.7% | 640 | 160 |
| fixed_mix_50_50 | 0.278 | 0.455 | 81.8% | 400 | 400 |
| adaptive_greedy | 0.389 | 0.500 | 35.7% | 775 | 25 |
### Budget 1200

| method | recall | precision | invalid | cand_calls | audit_calls |
|--------|--------|-----------|---------|------------|-------------|
| candidate_only | 0.444 | 0.333 | 50.0% | 1200 | 0 |
| audit_only | 0.222 | 0.286 | 92.9% | 0 | 1200 |
| fixed_mix_80_20 | 0.444 | 0.500 | 43.8% | 960 | 240 |
| fixed_mix_50_50 | 0.389 | 0.538 | 46.2% | 600 | 600 |
| adaptive_greedy | 0.500 | 0.429 | 42.9% | 1124 | 76 |

## Marginal Utility

| budget | candidate/100 | audit/100 | better |
|--------|---------------|-----------|--------|
| 50 | 2.00 | 0.14 | candidate |
| 100 | 1.38 | 0.92 | candidate |
| 200 | 0.88 | 1.14 | audit |
| 400 | 0.88 | 1.62 | audit |
| 800 | 1.09 | 1.22 | audit |
| 1200 | 1.24 | 1.06 | candidate |

## Judgment

**SITUATION A: Joint allocation WINS** (fixed_mix_50_50 at budget=200, +0.111 recall). Non-candidate audit has substantial value. Direction is viable.
