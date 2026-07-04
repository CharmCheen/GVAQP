# clean_interval_aqp_full_reference_v2_label_aligned

This experiment reuses the v1 mini-universe, full reference, and cheap signals,
then rebuilds the interval lattice and budget simulations with label-aligned
oracle calibration.

Run:

```bash
bash src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_label_aligned/run_all.sh
```

Main outputs are written under:

```text
src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/
```

The default CILS calibration label is `answer_iou_0_3`; `discovery_positive` is
diagnostic only.
