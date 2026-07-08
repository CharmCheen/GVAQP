# T028e synthesis — proxy-free candidate generator

## T028e-0: ceiling audit

**PASS**: dataset3_1200_2400 ceiling lifts +0.083 (from 0.000 to 0.083) with no realcartest regression.

Proxy-free arms that fire:
- ZERO_PROXY_VDC: 18 calls, 1.0 positive rate
- ZERO_PROXY_MIDBAND: 27 calls, 1.0 positive rate
- ZERO_PROXY_LARGEST_GAP: 6 calls, 1.0 positive rate
- ZERO_PROXY_LOCAL_GAP_FLANK: 6 calls, 1.0 positive rate

dataset3_0_1200 ceiling stays 0 (7 positives among 76 zero-proxy bins, sparse + DISCOVER oracle ceiling bias).

## T028e-1: strict-replay LOSO with extended arms

**Key result**: c2 beats v2 on 5/9 realcartest cells (matching c1) AND beats v2 on 2/9 dataset3 cells.

Most importantly: **c2 beats the ceiling on dataset3_0_1200** (0.167 vs 0.000 at @0.20/0.30). The policy learned to use ZERO_PROXY_VDC as its primary proxy-free arm, and this transfers to held-out data where VDC hits positives.

Per-seed consistency on dataset3_0_1200 @0.20: c2=0.167 on all 3 seeds (deterministic VDC arm selection).

## Action distribution shift

c2 on dataset3_0_1200:
- ZERO_PROXY_VDC: 12-13 calls (primary proxy-free arm)
- DISCOVER: 10-22 calls
- No BRIDGE (v2 uses BRIDGE heavily but gets 0 positives)

c2 on realcartest:
- More DISCOVER + CERTIFY, less BRIDGE (same pattern as c1)
- No proxy-free arms fire (correct: proxy informative)

## What this means

1. **Proxy-free candidate generator adds value under strict replay** on dataset3_0_1200
2. **VDC (Van der Corput) is the most effective proxy-free arm** — it hits positives on held-out data even when the ceiling doesn't select it
3. **c2 matches c1 on realcartest** (0 regressions) while adding dataset3 capability
4. The ceiling is not always the best guide — learned policies can find better strategies than per-step oracle utility when the training distribution is biased

## Safe claims

- ECP-c2 with proxy-free candidates matches c1 on proxy-informative segments and adds value on proxy-zero dataset3_0_1200 (LOSO validated)
- VDC low-discrepancy sequence is effective for zero-proxy exploration under strict replay
- The proxy-free candidate generator resolves the candidate-generator bottleneck on dataset3_0_1200 (ceiling was 0, now c2 achieves 0.167 recall)
- dataset3_1200_2400 and dataset3_2400_3462 remain at ceiling/v2 level (ceiling didn't lift much, but no regression)
