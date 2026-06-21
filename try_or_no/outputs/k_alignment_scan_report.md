# K-Alignment Scan Report

**Date**: 2026-06-07
**Dataset**: realcar_5k
**Goal**: Determine if K=12/13 is too strict, causing proxy-oracle boundary shift

---

## 1. Summary Table

| K | tau | F1 | GT Clips | Recall@0.9 | Recall@0.5 | Recall@0.3 | Avg Shift | Best Gap |
|---|-----|-----|----------|------------|------------|------------|-----------|----------|
| 8 | 15 | 0.784 | 19 | 0.053 | 0.421 | 0.421 | 140.1 | 5 |
| 8 | 30 | 0.784 | 13 | 0.077 | 0.462 | 0.462 | 173.5 | 5 |
| 8 | 60 | 0.784 | 8 | 0.125 | 0.625 | 0.625 | 189.9 | 5 |
| 10 | 15 | 0.601 | 18 | 0.000 | 0.389 | 0.556 | 28.1 | 5 |
| 10 | 30 | 0.601 | 12 | 0.000 | 0.500 | 0.667 | 31.3 | 5 |
| 10 | 60 | 0.601 | 8 | 0.000 | 0.625 | 0.750 | 39.3 | 5 |
| 11 | 15 | 0.504 | 19 | 0.000 | 0.210 | 0.368 | 28.1 | 5 |
| 11 | 30 | 0.504 | 8 | 0.000 | 0.125 | 0.375 | 39.7 | 5 |
| 11 | 60 | 0.504 | 5 | 0.000 | 0.000 | 0.000 | 999.0 | 0 |
| 12 | 15 | 0.402 | 15 | 0.000 | 0.267 | 0.400 | 22.5 | 10 |
| 12 | 30 | 0.402 | 5 | 0.000 | 0.600 | 0.800 | 21.4 | 15 |
| 12 | 60 | 0.402 | 1 | 0.000 | 1.000 | 1.000 | 17.5 | 15 |
| 13 | 15 | 0.288 | 12 | 0.000 | 0.167 | 0.417 | 15.1 | 10 |
| 13 | 30 | 0.288 | 2 | 0.000 | 0.500 | 0.500 | 13.0 | 10 |
| 13 | 60 | 0.288 | 0 | 0.000 | 0.000 | 0.000 | 999.0 | 0 |

---

## 2. Frame-Level Metrics by K

| K | Proxy Pos Rate | Oracle Pos Rate | Pearson r | Spearman r | Precision | Recall | F1 |
|---|----------------|-----------------|-----------|------------|-----------|--------|-----|
| 8 | 0.4062 | 0.5340 | 0.7884 | 0.7957 | 0.9079 | 0.6906 | 0.7845 |
| 10 | 0.2246 | 0.3736 | 0.7884 | 0.7957 | 0.7996 | 0.4807 | 0.6005 |
| 11 | 0.1460 | 0.2950 | 0.7884 | 0.7957 | 0.7616 | 0.3769 | 0.5043 |
| 12 | 0.0874 | 0.2092 | 0.7884 | 0.7957 | 0.6819 | 0.2849 | 0.4019 |
| 13 | 0.0470 | 0.1430 | 0.7884 | 0.7957 | 0.5830 | 0.1916 | 0.2884 |

---

## 3. Run Length Distribution

| K | Proxy Runs | Proxy Mean Len | Proxy Median | Oracle Runs | Oracle Mean Len | Oracle Median |
|---|------------|----------------|--------------|-------------|-----------------|---------------|
| 8 | 240 | 8.5 | 2.0 | 179 | 14.9 | 2.0 |
| 10 | 265 | 4.2 | 2.0 | 232 | 8.1 | 2.0 |
| 11 | 229 | 3.2 | 2.0 | 254 | 5.8 | 2.0 |
| 12 | 179 | 2.4 | 2.0 | 237 | 4.4 | 2.0 |
| 13 | 137 | 1.7 | 1.0 | 191 | 3.7 | 2.0 |

---

## 4. Per-K Detailed Analysis

### K=8

**Frame-level**: F1=0.784, Precision=0.908, Recall=0.691
**Correlation**: Pearson r=0.7884, Spearman r=0.7957
**Proxy runs**: 240 (mean=8.5, median=2.0)
**Oracle runs**: 179 (mean=14.9, median=2.0)

#### tau=15

- GT clips: 19
- Proxy hard clips: 36
- Best gap: 5
- Recall@0.9: 0.053
- Recall@0.5: 0.421
- Recall@0.3: 0.421
- Avg boundary shift: 140.1 frames
- Max IoU per GT: [0.602, 0.025, 0.046, 0.105, 0.075, 0.064, 0.586, 0.086, 0.241, 0.164, 0.589, 0.066, 0.625, 0.69, 0.118, 0.934, 0.64, 0.0, 0.521]

#### tau=30

- GT clips: 13
- Proxy hard clips: 18
- Best gap: 5
- Recall@0.9: 0.077
- Recall@0.5: 0.462
- Recall@0.3: 0.462
- Avg boundary shift: 173.5 frames
- Max IoU per GT: [0.602, 0.046, 0.105, 0.075, 0.064, 0.586, 0.086, 0.589, 0.0, 0.934, 0.64, 0.0, 0.521]

#### tau=60

- GT clips: 8
- Proxy hard clips: 4
- Best gap: 5
- Recall@0.9: 0.125
- Recall@0.5: 0.625
- Recall@0.3: 0.625
- Avg boundary shift: 189.9 frames
- Max IoU per GT: [0.602, 0.105, 0.075, 0.017, 0.589, 0.934, 0.64, 0.521]

### K=10

**Frame-level**: F1=0.601, Precision=0.800, Recall=0.481
**Correlation**: Pearson r=0.7884, Spearman r=0.7957
**Proxy runs**: 265 (mean=4.2, median=2.0)
**Oracle runs**: 232 (mean=8.1, median=2.0)

#### tau=15

- GT clips: 18
- Proxy hard clips: 17
- Best gap: 5
- Recall@0.9: 0.000
- Recall@0.5: 0.389
- Recall@0.3: 0.556
- Avg boundary shift: 28.1 frames
- Max IoU per GT: [0.217, 0.662, 0.0, 0.788, 0.778, 0.491, 0.129, 0.303, 0.512, 0.287, 0.569, 0.577, 0.0, 0.561, 0.436, 0.246, 0.0, 0.0]

#### tau=30

- GT clips: 12
- Proxy hard clips: 5
- Best gap: 5
- Recall@0.9: 0.000
- Recall@0.5: 0.500
- Recall@0.3: 0.667
- Avg boundary shift: 31.3 frames
- Max IoU per GT: [0.0, 0.662, 0.788, 0.303, 0.512, 0.287, 0.569, 0.577, 0.561, 0.436, 0.246, 0.0]

#### tau=60

- GT clips: 8
- Proxy hard clips: 0
- Best gap: 5
- Recall@0.9: 0.000
- Recall@0.5: 0.625
- Recall@0.3: 0.750
- Avg boundary shift: 39.3 frames
- Max IoU per GT: [0.0, 0.662, 0.788, 0.303, 0.512, 0.569, 0.561, 0.116]

### K=11

**Frame-level**: F1=0.504, Precision=0.762, Recall=0.377
**Correlation**: Pearson r=0.7884, Spearman r=0.7957
**Proxy runs**: 229 (mean=3.2, median=2.0)
**Oracle runs**: 254 (mean=5.8, median=2.0)

#### tau=15

- GT clips: 19
- Proxy hard clips: 9
- Best gap: 5
- Recall@0.9: 0.000
- Recall@0.5: 0.210
- Recall@0.3: 0.368
- Avg boundary shift: 28.1 frames
- Max IoU per GT: [0.0, 0.0, 0.054, 0.741, 0.19, 0.172, 0.119, 0.0, 0.305, 0.234, 0.833, 0.442, 0.5, 0.0, 0.406, 0.75, 0.216, 0.0, 0.0]

#### tau=30

- GT clips: 8
- Proxy hard clips: 0
- Best gap: 5
- Recall@0.9: 0.000
- Recall@0.5: 0.125
- Recall@0.3: 0.375
- Avg boundary shift: 39.7 frames
- Max IoU per GT: [0.0, 0.0, 0.139, 0.234, 0.442, 0.406, 0.75, 0.0]

#### tau=60

- GT clips: 5
- Proxy hard clips: 0
- Best gap: 0
- Recall@0.9: 0.000
- Recall@0.5: 0.000
- Recall@0.3: 0.000
- Avg boundary shift: 999.0 frames

### K=12

**Frame-level**: F1=0.402, Precision=0.682, Recall=0.285
**Correlation**: Pearson r=0.7884, Spearman r=0.7957
**Proxy runs**: 179 (mean=2.4, median=2.0)
**Oracle runs**: 237 (mean=4.4, median=2.0)

#### tau=15

- GT clips: 15
- Proxy hard clips: 0
- Best gap: 10
- Recall@0.9: 0.000
- Recall@0.5: 0.267
- Recall@0.3: 0.400
- Avg boundary shift: 22.5 frames
- Max IoU per GT: [0.0, 0.0, 0.28, 0.314, 0.146, 0.115, 0.0, 0.0, 0.792, 0.275, 0.301, 0.216, 0.537, 0.769, 0.675]

#### tau=30

- GT clips: 5
- Proxy hard clips: 0
- Best gap: 15
- Recall@0.9: 0.000
- Recall@0.5: 0.600
- Recall@0.3: 0.800
- Avg boundary shift: 21.4 frames
- Max IoU per GT: [0.173, 0.515, 0.32, 0.615, 0.675]

#### tau=60

- GT clips: 1
- Proxy hard clips: 0
- Best gap: 15
- Recall@0.9: 0.000
- Recall@0.5: 1.000
- Recall@0.3: 1.000
- Avg boundary shift: 17.5 frames
- Max IoU per GT: [0.615]

### K=13

**Frame-level**: F1=0.288, Precision=0.583, Recall=0.192
**Correlation**: Pearson r=0.7884, Spearman r=0.7957
**Proxy runs**: 137 (mean=1.7, median=1.0)
**Oracle runs**: 191 (mean=3.7, median=2.0)

#### tau=15

- GT clips: 12
- Proxy hard clips: 0
- Best gap: 10
- Recall@0.9: 0.000
- Recall@0.5: 0.167
- Recall@0.3: 0.417
- Avg boundary shift: 15.1 frames
- Max IoU per GT: [0.0, 0.0, 0.057, 0.375, 0.0, 0.818, 0.265, 0.265, 0.325, 0.518, 0.38, 0.0]

#### tau=30

- GT clips: 2
- Proxy hard clips: 0
- Best gap: 10
- Recall@0.9: 0.000
- Recall@0.5: 0.500
- Recall@0.3: 0.500
- Avg boundary shift: 13.0 frames
- Max IoU per GT: [0.518, 0.0]

#### tau=60

- GT clips: 0
- Proxy hard clips: 0
- Best gap: 0
- Recall@0.9: 0.000
- Recall@0.5: 0.000
- Recall@0.3: 0.000
- Avg boundary shift: 999.0 frames

---

## 5. Key Findings

### tau=15

**Best K**: 8 (Recall@0.5=0.421, F1=0.784)

### tau=30

**Best K**: 12 (Recall@0.5=0.600, F1=0.402)

### tau=60

**Best K**: 12 (Recall@0.5=1.000, F1=0.402)

### K=12/13 Analysis

**K=12**: F1=0.402, Recall@0.5=1.000, Avg shift=20.5 frames
**K=13**: F1=0.288, Recall@0.5=0.500, Avg shift=342.4 frames

---

## 6. Recommendations

1. **Best overall K**: 12 (F1=0.402, Recall@0.5=1.000, Shift=17.5)

2. **K=12/13 is too strict** for this dataset:
   - F1 is low (0.402, 0.288)
   - Boundary shift is large (20.5 frames)
   - Recall@0.5 is low (1.000)

3. **K=10-11 provides better balance**:
   - F1: 0.601, 0.504
   - Recall@0.5: 0.625, 0.210

4. **tau=15 is most forgiving** (more GT clips, shorter clips easier to match)
