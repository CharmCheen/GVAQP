# Reproduction

Run from `/qiuyeqing/llama_prl/G-ARC` in the recorded environment.

```bash
python -m unittest discover -s garc_eval/aqp_invention_v1/tests -v
python -m garc_eval.aqp_invention_v1.audit_frozen
python -m garc_eval.aqp_invention_v1.simulate_headroom
python -m garc_eval.aqp_invention_v1.prepare_physical --verify
python -m garc_eval.aqp_invention_v1.evaluate_physical
python -m garc_eval.aqp_invention_v1.evaluate_strengthened_baselines
```

The 90-call physical run is not required to reproduce post-hoc results; its raw responses, parsed outputs, frame hashes, timings, and started/completed checkpoints are sealed in `physical/`. Starting a new physical run requires separate authorization and a new experiment identity. The original runner required tmux and refuses any frozen hash mismatch.

Ceiling simulations read the strict reference and are labeled evaluator-only. Inference-time files do not import the event reference. Validate package files with `FILE_MANIFEST.csv`; that manifest excludes itself to avoid a circular hash.
