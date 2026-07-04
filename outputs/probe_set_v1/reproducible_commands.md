# Probe Set V1 Reproducible Commands

Run from repository root:

```bash
python -m py_compile src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py
python src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py probe
```

The export uses equal-interval time sampling independent of candidate lattice,
envelope, and prior review queues. Since `try_or_no/videos/realcartest.mp4` is
absent in this workspace, the script uses
`data/realcam/long_video_data/long_video_dataset3.mp4` with the historical
`local_to_media_offset_seconds=2000.0`.

Do not use `probe_set_v1` for tuning, threshold selection, selector choice,
repair decisions, or candidate generation.
