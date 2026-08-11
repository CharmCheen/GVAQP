# Conditioned-oracle pilot status

Status: `IMPLEMENTATION_PILOT_ONLY`  
Command: `PYTHONPATH=src python -u scripts/build_binary_smdp_oracle_dataset_v1.py --pilot --tasks V1_Q1 --budgets 60 --max-states 4 --beam-widths 128,512,2048`

Observed evidence:

- 11 unique both-legal states were reached by the frozen behavior-policy set;
- 4 deterministically selected states were labeled in the bounded pilot;
- all four labels were identical at beam widths 128, 512 and 2048;
- three of four searches were exact; all four labels were width-stable;
- all four were `EFFECTIVELY_TIED`, with zero attainable event and zero
  AnytimeAUC difference;
- no V0 cost imputation was involved because this pilot used V1 only;
- 23 focused oracle/legacy controller tests passed after adversarial review.

Interpretation: this verifies forced-action branching, stable-width plumbing and
artifact generation on one real trace regime. It provides no positive headroom
evidence: V1_Q1 at 60 seconds has no reachable confirmed event in these sampled
states. Informative budgets/groups must be tested before the headroom gate can
be decided.

An additional V1_Q2/120-second state after one SCAN was informative at all
three widths: both branches ended with one event, while SCAN-first AnytimeAUC
was 0.315645 versus 0.171093 for VERIFY-first (`SCAN_BETTER`). It was stable but
not exact. There was no beam pruning, but 570 SCAN-branch and 25 VERIFY-branch
transitions were rejected after a supposedly conservative admission bound led
to realized overrun. This is evidence for a possible timing value difference
and simultaneously decisive evidence that the present shield cannot support a
safe conditioned-oracle claim.

Negative safety evidence is decisive. A V1 SCAN took 17.3111 s while the
other-video calibration upper bound was 14.0642 s. More seriously, 9 of the 11
V1_Q1/60 behavior rollouts admitted a CONFIRM that physically completed around
80 s, after the 60 s deadline. The repaired two-phase transition committed no
Frontier/event result, and every violation is retained in the manifest. This
falsifies treating the external empirical bound as a physical WCET and fails
the present zero-overrun gate. Formal safety remains unestablished.
