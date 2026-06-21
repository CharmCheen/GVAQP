# Auto Research: Joint Allocation Summary

## 1. Does joint allocation win stably?

No.

- Total (setting × budget) pairs: 27
- Joint > candidate: 0/27 (0%)
- Delta >= 0.05: 0
- Delta >= 0.10: 0
- Average delta: **-0.109** (joint is WORSE)
- Max delta: +0.000

## 2. Where does the gain come from?

There is no gain. Candidate-only wins at every budget and every setting.
Joint methods (fixed_mix, adaptive_greedy) waste budget on non-candidate
frames that are mostly negatives.

## 3. Weak proxy effect?

With dropout_0.3/0.5, candidate_only recall drops dramatically (0.278→0.044
at budget=800). Joint allocation sometimes ties but never clearly wins.
Even under proxy degradation, audit from non-candidate frames does not
recover the lost recall.

## 4. Direction Judgment

**C. Stop**: joint allocation does not beat candidate-only reliably.

Candidate-only ARC-like refinement is the dominant strategy. Non-candidate
audit does not add value — oracle calls on random non-candidate frames
return mostly 0s, wasting budget. The earlier kill experiment's modest
gains (+0.056 recall) came from gap sweep artifacts, not from genuine
audit benefit.

### Settings tested
- label_K10 min_len=15: 18 clips, ratio=0.3736
- label_K10 min_len=30: 12 clips, ratio=0.3736
- label_K10 min_len=60: 8 clips, ratio=0.3736

### Settings filtered
- label_K5: positive_ratio=0.7384 (> 0.6)
- label_K20: only 3 positive frames (< 5 clips)

### Key evidence
| Setting | Budget | candidate_only | best_joint | delta |
|---------|--------|---------------|------------|-------|
| K10_min15 | 800 | 0.278 | 0.219 | -0.059 |
| K10_min15 | 1200 | 0.389 | 0.381 | -0.007 |
| K10_min30 | 800 | 0.333 | 0.250 | -0.083 |
| K10_min30 | 1200 | 0.500 | 0.500 | +0.000 |
| K10_min60 | 800 | 0.500 | 0.250 | -0.250 |
| K10_min60 | 1200 | 0.625 | 0.625 | +0.000 |
