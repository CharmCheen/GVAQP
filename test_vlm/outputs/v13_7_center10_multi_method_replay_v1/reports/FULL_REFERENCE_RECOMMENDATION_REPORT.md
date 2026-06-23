# Stage 8: Full Center10 Oracle Reference Recommendation

## Decision Criteria

```
CENTER10_FULL_REFERENCE_RECOMMENDED:
  At least one proxy/hybrid method improves positive recall or enrichment
  over uniform/random by >= 0.10 absolute on the labeled subset,
  AND selected positives include mostly complete_event_visible=true cases,
  AND no leakage is detected.
```

## Evidence

### 1. Proxy methods beat random by ≥0.10 at all budgets

| Budget | Best Method | Proxy Recall | Random Mean Recall | Delta |
|---|---|---|---|---|
| B=5 | top_yolo_vehicle_mean | 0.172 | 0.000 | **+0.172** |
| B=10 | top_yolo_vehicle_mean | 0.207 | 0.021 | **+0.186** |
| B=20 | top_yolo_vehicle_max | 0.448 | 0.034 | **+0.414** |
| B=40 | top_yolo_vehicle_max | 0.517 | 0.103 | **+0.414** |

**Finding:** Multiple proxy/hybrid methods exceed the +0.10 threshold at every budget level. At B≥10, the delta is ≥0.15 across all tested proxy methods. At B≥20, top_yolo_vehicle_max achieves 0.448 recall with +0.414 delta.

### 2. Selected positives are all complete_event_visible=true

The V13.6 center_10s results showed 100% complete_event_rate and 0% truncation for all 29 labeled positives. Every positive on the labeled subset has complete_event_visible=true and boundary_status=ok.

### 3. No leakage detected

The proxy features (center10_proxy_features.csv) were built exclusively from V13.5 proxy features (motion energy, YOLOv8n detections). No VLM labels, event boundaries, or oracle outputs were used. The hard invariant (no VLM/oracle/event fields in proxy table) is verified.

### 4. Enrichment vs uniform

| Budget | Best Method | Enrichment vs Uniform |
|---|---|---|
| B=5 | top_yolo_vehicle_mean | +79% |
| B=10 | top_yolo_vehicle_mean | +20% |
| B=20 | top_yolo_vehicle_max | +17% |
| B=40 | top_yolo_vehicle_max | +3% |

At low budgets, proxy methods dramatically enrich the positive rate vs uniform sampling. Enrichment decreases at higher budgets as uniform catches up, but absolute recall still favors proxy methods.

## Caveats

1. The labeled subset (52 clips, 29 positives) is pilot-derived and biased toward high-proxy regions (25% were high_yolo_vehicle_count samples). This inflates apparent proxy performance.
2. The labeled subset covers only 45/399 anchors (11%). Most anchors have no VLM label.
3. Full-video positive recall cannot be estimated from this subset — a full center10 oracle reference is needed.

## Recommendation

```
CENTER10_FULL_REFERENCE_RECOMMENDED
```

**Rationale:** All three criteria are met:
1. ✅ Proxy methods beat random by ≥0.10 at every budget (max delta +0.414)
2. ✅ All labeled positives have complete_event_visible=true
3. ✅ No leakage detected — proxy features built from V13.5 only

The next step is to run the full 399-anchor center10 oracle (Qwen3-VL-32B-Instruct on all 399 center10 anchors), which would provide an unbiased full-video VLM-oracle-relative reference for evaluating any anchor selection method.
