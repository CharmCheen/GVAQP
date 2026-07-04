# Cheap Signal V2 Reproducible Commands

Run from repository root:

```bash
python -m py_compile src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py
python src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py all
```

Useful partial reruns:

```bash
python src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py probe
python src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py features
python src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py evaluate
```

Notes:

- No VLM inference was run.
- No new YOLO inference was run for Phase B; track features reuse `src/garc_eval/outputs/track_transition_validation_v1/tables/object_tracks_dataset3_2fps.csv`.
- Probe media uses `data/realcam/long_video_data/long_video_dataset3.mp4` with the historical +2000s local-to-media offset because `try_or_no/videos/realcartest.mp4` is absent.
- `probe_set_v1` is read-only evaluation material and must not be used for tuning, threshold selection, selector choice, or repair decisions.
