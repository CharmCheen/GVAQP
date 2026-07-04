# Next Experiment Recommendation

## 1. Most Credible Conclusions
- E0 (top prior envelope) misses positive temporal mass (H1 supported).
- Outside positives cluster temporally (H2 supported).
- Ours-full improves event-level recall at some budgets, but the gain is mixed across event types and parameter settings.
- Budget accounting is exact; the comparison is fair.

## 2. Claims That Cannot Be Made Yet
- 'LATE-AQP repair recovers full event intervals better than ExSample+expansion' — complete-event coverage evidence is weak.
- 'Audit ledger is calibrated' — H7 unverified.
- 'Ours reduces false positives' — duration-based precision is often lower than B7.
- Comparison to SUPG/ABae baselines — not yet run.

## 3. Recommended Next Steps (priority order)
1. **A. Exhaustive calibration annotation** — highest priority. Without H7, no calibration claim is possible.
2. **D. Long-event-only replay** — second priority. Remove point-anchor events and re-run B6/B7/Ours to see if long-event structure repair holds.
3. **B. SUPG/ABae baselines** — third priority. Needed for H3/H4 and broader positioning.
4. **E. Redesign repair utility** — conditional. If long-event replay still shows weak coverage, reformulate repair as a budget reallocation rather than interval expansion.
5. **C. Audit schedule v3 ablation** — lower priority until H7 is verified.

## 4. Next Codex Prompt Draft
```
TASK: Long-Event-Only Replay for LATE-AQP
Use the same data as outputs/exsample_aware_replay/, but restrict reference events to long_interval events (duration >= 1s).
Re-run B6, B7, and Ours-full with the same pre-registered parameters and budgets.
Report event-level recall, complete-event coverage, boundary IoU, precision, and selected duration.
Determine whether Ours-full still outperforms B7 when point-anchor events are excluded.
Do not modify existing labels or priors. No new VLM/YOLO/GPU/API calls.
```
