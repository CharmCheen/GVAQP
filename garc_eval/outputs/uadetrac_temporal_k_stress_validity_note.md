# UA-DETRAC K-Stress Validity Note

Date: 2026-05-23

This is a lightweight audit of cached UA-DETRAC K-stress artifacts. It did not run new experiments, rerun YOLO materialization, download data, modify algorithm code, commit, push, or stage files. The audit checks whether the K-stress conclusion used K-specific labels and K-specific proxy scores rather than reusing the original K=25 `proxy_score`.

## Audited Artifacts

- Baseline source: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`
- Cached frame table: `garc_eval/outputs/uadetrac_temporal/frames.parquet`
- Derived K-stress directory: `garc_eval/outputs/uadetrac_temporal/k_stress/`
- K-stress report: `garc_eval/outputs/uadetrac_temporal_k_stress_report.md`
- Count proxy implementation reference: `garc_eval/datasets/build_frame_table.py`

## Cached Columns

The baseline `supg_source.csv` contains only:

```text
id,label,proxy_score
```

The cached `frames.parquet` contains:

```text
id, video_id, frame_idx, timestamp, image_path, proxy_score_raw,
proxy_max_conf, proxy_count, proxy_conf_sum, proxy_conf_mean,
proxy_conf_top3_sum, proxy_conf_top5_sum, oracle_score,
oracle_count, proxy_score, label
```

The derived K-stress source CSVs for `K=27` and `K=28` also contain only:

```text
id,label,proxy_score
```

Their derived `frames.parquet` files retain the same columns as the baseline cached frame table.

## Label Validity

K-stress did use K-specific labels:

- `K=27`: `label == 1[oracle_count >= 27]`, positives `459 / 13,932`, positive rate `3.29%`.
- `K=28`: `label == 1[oracle_count >= 28]`, positives `233 / 13,932`, positive rate `1.67%`.

These labels are based on cached YOLOv8x pseudo-oracle counts, not human ground truth.

## Proxy Score Validity

K-stress did use K-specific proxy scores. The derived metadata files state:

```text
count_conf_hybrid recomputed as 0.7 * min(proxy_count / K, 1.0) + 0.3 * proxy_max_conf
```

This is consistent with the repository implementation of `count_conf_hybrid` in `garc_eval/datasets/build_frame_table.py`, where the count denominator is the active `count_threshold`.

The derived source values match the K-specific formula to floating-point tolerance:

| K | Matches `0.7 * min(proxy_count / K, 1.0) + 0.3 * proxy_max_conf` | Identical to baseline K=25 `proxy_score` | Max difference from baseline K=25 score |
|---:|---|---|---:|
| 27 | yes, max diff `1.11e-16` | no | `0.0518518519` |
| 28 | yes, max diff `1.11e-16` | no | `0.0750000000` |

Therefore the main concern is not borne out by the cached artifacts: the K-stress did not reuse the original K=25 `proxy_score`.

## Effect on Conclusion

The K-stress conclusion is partially valid as an engineering smoke result:

- The predicate difficulty was K-specific.
- The SUPG source labels were K-specific.
- The proxy score was K-specific under the cached `count_conf_hybrid` rule.
- SUPG-RT selected all frames in `10 / 10` cached trials for both `K=27` and `K=28` at `budget=1000`.

The conclusion should still be limited to the cached UA-DETRAC subset, YOLOv8x pseudo-oracle labels, the `count_conf_hybrid` proxy rule, and the tested budget/trial settings. It is not research-valid human-ground-truth evidence and does not establish a general UA-DETRAC or G-ARC result.

If the experiment had reused the K=25 proxy score, the conclusion would need to be weakened to: "raising the pseudo-oracle label threshold alone made positives rarer, but the observed SUPG-RT selected-all behavior may be an artifact of a proxy ranking calibrated to K=25 rather than evidence about K=27/K=28 query difficulty." That weakening is not required for the cached artifacts audited here.

## Rerun Feasibility

Rerunning K-stress with K-specific `proxy_score` is possible from cached columns without YOLO materialization because `frames.parquet` includes both `proxy_count` and `proxy_max_conf`.

However, a rerun is not needed for the validity concern audited here. The existing derived K-stress sources already use K-specific labels and K-specific `count_conf_hybrid` proxy scores.

If a provenance-clean regeneration is desired, use the derivation command embedded in `garc_eval/outputs/uadetrac_temporal_k_stress_report.md` under "Exact Commands Run", or factor that block into a minimal script such as:

```bash
source env_garc.sh
PYTHONPATH=. python scripts/derive_uadetrac_k_stress_sources.py \
  --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet \
  --outbase garc_eval/outputs/uadetrac_temporal/k_stress \
  --ks 27 28 \
  --proxy-score-rule count_conf_hybrid
```

That script does not currently exist; this note does not implement it.

## Recommendation

Do not stop UA-DETRAC K-stress because of the proxy-score validity concern. Also do not rerun the same K-stress solely to address this concern.

The exact next recommendation is to keep the existing K-stress result as a partially valid engineering smoke result and document the limitation: at `budget=1000`, `K=27` and `K=28` are valid K-specific cached stress settings, but they are degenerate for SUPG-RT because selected-all occurs in every cached trial. Do not run 100-trial formal experiments from these settings.
