# Runtime Cost Benchmark

## 1. Purpose

Distinguish **offline CSV generation cost** (running both models on every frame to build the proxy/oracle table) from **query-time cost** (using a precomputed proxy table to decide which frames need oracle evaluation).

This benchmark does NOT implement ARC or G-ARC. It only measures how reducing oracle calls translates into query-time speedup under this pseudo-oracle setup.

## 2. Measured Components

**Hardware:** NVIDIA RTX 2080 Ti, CUDA
**Models:** YOLOv8n (6.3 MB) as proxy, YOLOv8x (131 MB) as pseudo-oracle
**Benchmark frames:** 100 (first 100 frames of `test.mov`, 2940×1912)
**Inference settings:** conf=0.25, imgsz=640

| Component | Time | FPS |
|-----------|------|-----|
| Proxy-only (YOLOv8n) | 1.06s / 100 frames | **93.9 fps** |
| Oracle-only (YOLOv8x) | 2.23s / 100 frames | **44.9 fps** |
| Dual-model (sequential) | 3.22s / 100 frames | **31.0 fps** |
| CSV read (1775 rows) | **18.0 ms** | — |
| Clip stitch (tau=20, K=5) | **3.4 ms** | — |

**Key observations:**
- Oracle (YOLOv8x) is ~2.1× slower than proxy (YOLOv8n), as expected from the 20× parameter difference.
- CSV read + stitch is negligible (~21 ms total) compared to any inference cost.
- Dual-model time ≈ proxy time + oracle time (sequential, no batching overlap).

## 3. Query-Time Cost Model

### Definitions

- **N** = total processed frames = 1775 (from `video_supg.csv`)
- **oracle_fps** = 44.9 (measured)
- **proxy_fps** = 93.9 (measured)

### Exact query baseline (no proxy filtering)

Run oracle on every frame:

```
exact_query_time = N / oracle_fps = 1775 / 44.9 = 39.5s
```

### Approximate query with oracle budget ratio

Use the precomputed proxy table to select a fraction (`oracle_ratio`) of frames for oracle evaluation:

```
approx_query_time = csv_read_time + stitch_time + oracle_ratio × N / oracle_fps
```

The proxy table is assumed **precomputed offline** (the CSV already exists). If proxy is NOT precomputed, the online query must include the full proxy scan:

```
approx_query_online = proxy_scan_time + oracle_ratio × N / oracle_fps
```

Where `proxy_scan_time = N / proxy_fps = 1775 / 93.9 = 18.9s`.

## 4. Estimated Speedup

### Scenario A: Precomputed proxy table (offline CSV exists)

The proxy scan was done once offline. Query-time only reads the CSV, selects candidates, and runs oracle on them.

| oracle_ratio | candidates | oracle_time | approx_total | speedup |
|:------------:|:----------:|:-----------:|:------------:|:-------:|
| 5% | 88 | 1.96s | **1.98s** | **20.0×** |
| 10% | 177 | 3.94s | **3.96s** | **10.0×** |
| 20% | 355 | 7.91s | **7.93s** | **5.0×** |

### Scenario B: Online (proxy scan not precomputed)

Query-time must also run the proxy on all frames to generate candidates.

| oracle_ratio | candidates | oracle_time | approx_total | speedup |
|:------------:|:----------:|:-----------:|:------------:|:-------:|
| 5% | 88 | 1.96s | **20.86s** | **1.9×** |
| 10% | 177 | 3.94s | **22.84s** | **1.7×** |
| 20% | 355 | 7.91s | **26.80s** | **1.5×** |

## 5. Interpretation

**Precomputed proxy table:** If the proxy scan is done offline (e.g., during video ingestion), query-time is dominated by oracle calls. Reducing oracle to 5% of frames yields a **20× speedup** over exhaustive oracle evaluation. Even at 20% oracle ratio, we get **5× speedup**.

**Online proxy scan:** If proxy must also run at query time, speedup is modest (1.5–1.9×) because the proxy scan itself takes 18.9s — comparable to the oracle cost. The benefit comes from avoiding oracle on 80–95% of frames, but the proxy scan is not free.

**Practical implication:** For real-time or interactive use, precomputing the proxy table is essential. The proxy (YOLOv8n at 93.9 fps) can process a 43-second video in ~19 seconds — fast enough for offline batch preprocessing. The oracle (YOLOv8x at 44.9 fps) would take ~39.5 seconds on all frames, but only ~2–8 seconds on a 5–20% candidate subset.

**This is NOT ARC/G-ARC performance.** These numbers only show the raw inference cost tradeoff. ARC/G-ARC would add algorithmic overhead (selection policy, gradient computation, etc.) on top of these measurements.

## 6. Limitations

1. **100-frame microbenchmark.** Measured on the first 100 frames of one video. Frame complexity may vary across the video. Full-video fps may differ slightly.
2. **YOLOv8x pseudo-oracle.** Not human ground truth. Real oracle cost (e.g., human annotation) would be orders of magnitude higher, making the speedup even more dramatic.
3. **No ARC/G-ARC implementation.** This benchmark measures raw inference cost, not the end-to-end cost of an adaptive selection algorithm.
4. **No batching optimization.** Inference is frame-by-frame. Batched inference could change relative fps.
5. **No scheduling overhead.** Real systems would have I/O, memory, and scheduling costs not captured here.
6. **Resolution-dependent.** The test video is 2940×1912 (high-res). Lower-resolution videos would be faster for both models. The `--imgsz 640` resize step dominates actual compute.
7. **GPU-specific.** RTX 2080 Ti results. Different GPUs (A100, 4090, etc.) would shift absolute fps but relative proxy/oracle ratio should be similar.
