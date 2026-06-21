# Human Audit Analysis For Conservative VLM Predicate

This report summarizes the manually reviewed 68-clip audit pack. The audit pack contains all old-strict-positive clips: 22 conservative positives and 46 old-strict positives downgraded by the conservative prompt.

## Label Counts

- audited clips: 68
- human positives: 20 / 68 = 0.294
- human negatives: 48
- conservative original positives in audit pack: 22

## Conservative Predicate Against Human Audit

- TP: 19
- FP: 3
- TN: 45
- FN: 1
- precision on audited pack: 0.864
- recall within audited old-strict-positive pack: 0.950
- old strict precision on this audited pack: 0.294

Important limitation: this does not measure recall over all 102 clips because old-strict-negative clips were not included in this audit pack. It is strongest as a precision / predicate-quality check for clips previously considered positive by VLM.

## Human Positive Events

- human-positive clips: 20
- human-positive events with 4s merge gap: 6
- average positive run length: 3.333 clips/event

| event | time span | clips |
|---:|---|---:|
| 1 | 12.0-35.0s | 9 |
| 2 | 72.0-77.0s | 1 |
| 3 | 86.0-97.0s | 4 |
| 4 | 100.0-107.0s | 2 |
| 5 | 166.0-171.0s | 1 |
| 6 | 184.0-193.0s | 3 |

## Error Cases

Conservative false positives:
- `realcartest_5k_clip00005_s000010000ms_e000015000ms` (10.0-15.0s): pedestrian/bicycle crossing and ego reversing, but no likely collision course; attention-only scene, not ego-relevant risk positive
- `realcartest_5k_clip00007_s000014000ms_e000019000ms` (14.0-19.0s): same as clip05: crossing-like motion but no real collision course or ego-relevant conflict
- `realcartest_5k_clip00065_s000130000ms_e000135000ms` (130.0-135.0s): 130-135s: motorbike does not actually cross or intrude into ego path

Conservative false negatives inside audited old-strict-positive set:
- `realcartest_5k_clip00094_s000188000ms_e000193000ms` (188.0-193.0s): 188-193s: user confirmed this segment is dangerous and requires extra attention

## What This Helps With

- The audit strongly supports replacing old strict with conservative labels for this video: old strict was much too broad, while conservative labels mostly match the human-reviewed old-strict-positive subset.
- The audit identifies a small number of prompt failure modes: attention-only crossing while ego is reversing/stationary, non-intruding motorbike, and one late segment that should have been kept positive.
- The audit can be used to tune the conservative prompt examples and to create a small human-checked calibration set.

## What This Does Not Solve

- It does not make the current source video a valid benchmark. Positives are concentrated in a few short repeated temporal segments, and many clips are closed-area / low-speed / pre-road scenes rather than normal moving-camera traffic.
- It cannot validate budget allocation on a realistic large video repository because the sample is only 102 overlapping clips from one short video.
- It does not provide full human GT for all 102 clips unless old-strict-negative clips are also audited.

## Recommendation

- Use this audit as evidence that the conservative predicate is directionally correct, not as a final benchmark.
- Re-cut clips from the original dataset or a better source, with filters that remove pre-road/title/closed-area segments and target normal moving-camera road driving.
- Keep count / naive + temporal allocation as the current baseline when re-cutting; do not spend more time tuning kinematic v0 on this source video.
