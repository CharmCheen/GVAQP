# Dataset Acquisition Audit

Generated: 2026-05-20

## Candidates Evaluated

### 1. UA-DETRAC
- **Source**: https://huggingface.co/datasets/abhineet123/ua_detrac
- **Access friction**: None — direct download via HuggingFace, CC-BY-4.0 license
- **Format**: ZIP containing video sequences (MPEG-4)
- **Size**: ~5.6 GB (training set zip)
- **Expected frames**: ~140,000 frames from 100 video sequences
- **Scene type**: Traffic surveillance cameras (overhead/side-mounted)
- **Suitable for count_car**: Yes — dense traffic with many vehicles per frame
- **Non-interactive download**: Yes — `curl -L -O` from HuggingFace CDN
- **Decision**: **BACKUP CANDIDATE** (downloading in parallel)

### 2. BDD100K (Hirundo validation subset)
- **Source**: https://huggingface.co/datasets/hirundo-io/bdd100k-validation-only
- **Access friction**: None — direct download via HuggingFace, BSD-3-Clause license
- **Format**: ZIP containing JPEG images (1280x720)
- **Size**: ~575 MB
- **Expected frames**: ~10,000 validation images
- **Scene type**: Driving/dashcam scenes (urban, highway, residential)
- **Suitable for count_car**: Moderate — driving perspective, variable car density
- **Non-interactive download**: Yes — `curl -L -O` from HuggingFace CDN
- **Decision**: **PRIMARY CANDIDATE** (smaller, faster to process)

### 3. CityFlow / AI City Challenge
- **Source**: https://www.aicitychallenge.org/
- **Access friction**: High — requires challenge registration, Google login
- **Format**: Video sequences with annotations
- **Size**: >200,000 frames from 40 cameras
- **Suitable for count_car**: Yes — urban traffic surveillance
- **Non-interactive download**: No — requires account/registration
- **Decision**: **REJECTED** — registration required

### 4. D2-City
- **Source**: GitHub didi/d2-city (404 — repository no longer available)
- **Access friction**: Dead link
- **Decision**: **REJECTED** — source unavailable

### 5. BDD100K (Official)
- **Source**: https://bdd-data.berkeley.edu/
- **Access friction**: High — requires account registration, license agreement
- **Format**: Images (1280x720), ~7.5 GB for images alone
- **Suitable for count_car**: Yes
- **Non-interactive download**: No — requires authenticated session
- **Decision**: **REJECTED** — registration required; using Hirundo mirror instead

### 6. DRIV100 (previously tested)
- **Source**: Zenodo record 4389243
- **Access friction**: Record exists but no raw video files available
- **Decision**: **REJECTED** — data not actually available

### 7. KITTI Raw (previously tested)
- **Source**: KITTI vision benchmark
- **Access friction**: Low — direct download
- **Format**: Image sequences
- **Expected frames**: ~1,176 (combined subset)
- **Suitable for count_car**: Yes but too small
- **Non-interactive download**: Yes
- **Decision**: **REJECTED** — too small (N=1176), SUPG-RT vacuous

## Selection Strategy

1. **Primary**: BDD100K Hirundo val — 10K images, 575MB, fast download and processing
2. **Backup**: UA-DETRAC training set — 140K+ frames, 5.6GB, traffic surveillance

Both are downloading in parallel. BDD100K will be attempted first due to faster turnaround.
If BDD100K yields vacuous SUPG-RT (driving perspective may have low car counts),
UA-DETRAC will be the fallback (traffic surveillance = denser car scenes).

## Action Plan

1. Download BDD100K val (~575MB) — extract, enumerate images
2. Build frame metadata table (N >= 10,000 target)
3. Materialize proxy (YOLOv8n) and oracle (YOLOv8x) scores
4. Calibrate count threshold K for positive rate 1-20%
5. Run 5-trial SUPG smoke
6. If vacuous: switch to UA-DETRAC and repeat
