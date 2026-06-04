# G-ARC Certificate MVP Report

## 1. Purpose

This is a first minimal G-ARC recall certificate prototype.
It uses finite-population non-candidate frame-mass audit to derive
a conservative lower bound on clip-level recall.

This is NOT ARC reproduction. This is NOT final theory.
YOLOv8x is used as pseudo-oracle, not human ground truth.

## 2. Method

### Candidate Generation (arc_style_proxy_candidates)
1. Threshold proxy_vehicle_count >= K to get proxy-positive frames.
2. Merge positive runs separated by gap <= tau/3.
3. Keep clips with length >= tau.

### Non-Candidate Frame-Mass Audit
1. Define non-candidate (NC) frames as frames not covered by any candidate clip.
2. Sample s frames uniformly without replacement from NC frames.
3. Query oracle-positive labels on sampled frames.
4. Apply one-sided Hoeffding bound: q_U = min(1, x/s + sqrt(log(1/delta)/(2s))).
5. Missed positive frame upper bound: F_U = q_U * N_NC.
6. Missed clip upper bound: M_U = floor(F_U / tau).
7. Certified recall lower bound: recall_LB = H / (H + M_U).

## 3. Why This Is Conservative but Valid

The bound is conservative because:
- Hoeffding gives a worst-case upper bound on the positive fraction in NC region.
- Converting frame mass to clip count (floor(F_U / tau)) adds further slack.
- It assumes every missed positive frame forms a full tau-length clip.

The bound is valid because:
- It is a proper finite-population confidence bound (no distributional assumptions).
- With probability >= 1-delta, q_U is an upper bound on the true NC positive fraction.
- Therefore recall_LB is a valid lower bound on true clip recall.

## 4. Results by Tau and Sample Size

Data: `outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv`, N=5000
K=[10], delta=0.05

### gamma = 0.8

| K | tau | s | actual_recall | cert_recall_LB | pass_rate | bound_gap | q_U | M_U | H |
|---|-----|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 10 | 5 | 100 | 0.025 | 0.003 | 0% | 0.022 | 0.378 | 299 | 1 |
| 10 | 5 | 200 | 0.025 | 0.004 | 0% | 0.021 | 0.344 | 272 | 1 |
| 10 | 5 | 500 | 0.025 | 0.004 | 0% | 0.021 | 0.312 | 247 | 1 |
| 10 | 5 | 1000 | 0.025 | 0.004 | 0% | 0.021 | 0.297 | 235 | 1 |
| 10 | 10 | 100 | 0.130 | 0.024 | 0% | 0.107 | 0.336 | 126 | 3 |
| 10 | 10 | 200 | 0.130 | 0.025 | 0% | 0.105 | 0.311 | 116 | 3 |
| 10 | 10 | 500 | 0.130 | 0.028 | 0% | 0.103 | 0.282 | 105 | 3 |
| 10 | 10 | 1000 | 0.130 | 0.029 | 0% | 0.101 | 0.266 | 99 | 3 |
| 10 | 20 | 100 | 0.182 | 0.033 | 0% | 0.148 | 0.327 | 59 | 2 |
| 10 | 20 | 200 | 0.182 | 0.037 | 0% | 0.145 | 0.296 | 53 | 2 |
| 10 | 20 | 500 | 0.182 | 0.040 | 0% | 0.142 | 0.268 | 48 | 2 |
| 10 | 20 | 1000 | 0.182 | 0.042 | 0% | 0.139 | 0.253 | 45 | 2 |

### gamma = 0.9

| K | tau | s | actual_recall | cert_recall_LB | pass_rate | bound_gap | q_U | M_U | H |
|---|-----|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 10 | 5 | 100 | 0.025 | 0.003 | 0% | 0.022 | 0.378 | 299 | 1 |
| 10 | 5 | 200 | 0.025 | 0.004 | 0% | 0.021 | 0.344 | 272 | 1 |
| 10 | 5 | 500 | 0.025 | 0.004 | 0% | 0.021 | 0.312 | 247 | 1 |
| 10 | 5 | 1000 | 0.025 | 0.004 | 0% | 0.021 | 0.297 | 235 | 1 |
| 10 | 10 | 100 | 0.130 | 0.024 | 0% | 0.107 | 0.336 | 126 | 3 |
| 10 | 10 | 200 | 0.130 | 0.025 | 0% | 0.105 | 0.311 | 116 | 3 |
| 10 | 10 | 500 | 0.130 | 0.028 | 0% | 0.103 | 0.282 | 105 | 3 |
| 10 | 10 | 1000 | 0.130 | 0.029 | 0% | 0.101 | 0.266 | 99 | 3 |
| 10 | 20 | 100 | 0.182 | 0.033 | 0% | 0.148 | 0.327 | 59 | 2 |
| 10 | 20 | 200 | 0.182 | 0.037 | 0% | 0.145 | 0.296 | 53 | 2 |
| 10 | 20 | 500 | 0.182 | 0.040 | 0% | 0.142 | 0.268 | 48 | 2 |
| 10 | 20 | 1000 | 0.182 | 0.042 | 0% | 0.139 | 0.253 | 45 | 2 |

## 5. Certificate Pass Rate

- gamma=0.8: **NO passing configurations**
- gamma=0.9: **NO passing configurations**

## 6. Bound Tightness

- gamma=0.8: best bound_gap = 0.021 (actual=0.025, cert_LB=0.004)
- gamma=0.9: best bound_gap = 0.021 (actual=0.025, cert_LB=0.004)

## 7. Whether Frame-Mass Bound Is Too Loose

The frame-mass bound is inherently loose because:
1. It converts a frame-level positive fraction to a clip count by dividing by tau.
2. This assumes worst-case: every tau positive frames form one clip.
3. In reality, positive frames cluster, so fewer clips are missed than predicted.
4. The Hoeffding bound itself adds sqrt(log(1/delta)/(2s)) slack.

## 8. Failure Cases

- gamma=0.8: worst pass rate = 0% at tau=5, s=100
- gamma=0.9: worst pass rate = 0% at tau=5, s=100

## 9. Next Improvement: Run-Aware / Window Audit

The current audit samples uniformly from all non-candidate frames.
A tighter bound would:
1. Sample **runs** (windows) rather than individual frames,
2. Detect whether a window contains a missed clip,
3. Use run-level Hoeffding to bound missed clip count directly.
4. This avoids the loose frame-to-clip conversion (floor(F_U / tau)).

---

This is a first certificate MVP. It is not final G-ARC theory.
The bound is valid but conservative. Tighter bounds require run-aware auditing.