# Proxy Quality Report

Protocol: `14e0b391a87d1a5546df49dc74374fc598e673269c8e843e6b3e3313825fc72c`.  All semantic characterization was computed **after** the outcome-blind regime definitions and hashes were frozen.  No Qwen inference was run.

## Original frozen V3 proxy

| Video | Units/candidates | Positive units | Structural exposure | Positive-unit recall | Ranking AUPRC | Ranking AUROC |
|---|---:|---:|---:|---:|---:|---:|
| DALI | 567 | 82 | 1.000 | 1.000 | 0.3146 | 0.6663 |
| HANGZHOU | 561 | 93 | 1.000 | 1.000 | 0.2584 | 0.6241 |
| WUHAN | 347 | 76 | 1.000 | 1.000 | 0.3112 | 0.6130 |

The original V3 candidate generator emits exactly one candidate per frozen 10-second unit.  Thus both structural exposure and positive-unit exposure are `1.0` by design.  This does **not** mean the proxy is perfect: ranking quality is measured separately.  A candidate missing under the E-axis stress regimes is counted as an exposure miss and never represented as merely a low score.

## Regime interpretation

- `R0` is the only natural, current-interface proxy regime.
- `R1`–`R3` preserve the complete candidate universe and degrade only ranking through deterministic hash noise.
- `E1`–`E3` retain original scores but deterministically thin candidates, modeling exposure loss independently.
- Construction is GT-blind.  Labels are joined only for the metrics in `PROXY_QUALITY_METRICS.csv` and `PROXY_TOPK_YIELD.csv`.
- AUPRC/AUROC are conditional on exposed candidates.  `positive_unit_recall` measures exposure against all frozen semantic-positive units.  The Brier column is descriptive only because the YOLO-derived proxy score was not calibrated as a semantic probability.

## Natural-variant audit

The repository contains historical YOLO, PSVR, proxy-distillation and candidate assets, but none provides a versioned GOOD/MEDIUM/POOR set over the same DALI/HANGZHOU/WUHAN candidate universe and semantics.  They are excluded rather than forced into an unfair interface.  Consequently, causal claims must say **outcome-blind synthetic stress**, not natural proxy-model generalization.
