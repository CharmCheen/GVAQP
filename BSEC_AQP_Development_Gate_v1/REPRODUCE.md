# Reproduction

Run commands from the repository root. Use a copy of the package if the sealed outputs must remain byte-identical, because the gate runners overwrite their output CSVs and manifests.

## Environment and frozen hashes

- CLIP: `openai/clip-vit-base-patch32`
- revision: `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`
- v1 protocol: `4eea29f266f35be771ee430bb04221babe32c48adffc7bd7dd4a64e3ac7fd42a`
- v2 protocol: `f62800ece1edee2751afa646efe8d8d344dd8a04de3b1392c9845d0aa15e1daa`
- v3 protocol: `5fad1ac9b59430d9d19363c66c55001d33b5da9fc1c56552081d611336ee61ef`
- frozen next PSTR candidate: `8da4c56f651839120a7975dbc3bbbf209fb76db746c8f3993189cd32da17cff2`
- terminal PSTR external protocol v5: `edecabf4a10346a7629ff90a7b5a94b0635ad3464c622594f371dc8d2234ab79`

The exact CLIP revision must already be available in the Hugging Face cache or be downloaded before offline reproduction.

## Recompute CLIP scores

```bash
python BSEC_AQP_Development_Gate_v1/scripts/score_heldout_clip.py \
  --protocol BSEC_AQP_Development_Gate_v1/config/frozen_protocol.json \
  --output BSEC_AQP_Development_Gate_v1/outputs/heldout/clip_inference \
  --unit-count 120 --absolute-index-start 200 --device cpu --threads 31 --execute

python BSEC_AQP_Development_Gate_v1/scripts/score_heldout_clip.py \
  --protocol BSEC_AQP_Development_Gate_v1/config/frozen_continuation_v2.json \
  --output BSEC_AQP_Development_Gate_v1/outputs/confirmatory/clip_inference \
  --unit-count 157 --absolute-index-start 0 --device cpu --threads 31 --execute

python BSEC_AQP_Development_Gate_v1/scripts/score_heldout_clip.py \
  --protocol BSEC_AQP_Development_Gate_v1/config/frozen_continuation_v3.json \
  --output BSEC_AQP_Development_Gate_v1/outputs/final_confirmation/realcartest_1630_2000/clip_inference \
  --unit-count 37 --absolute-index-start 163 --device cpu --threads 31 --execute

python BSEC_AQP_Development_Gate_v1/scripts/score_heldout_clip.py \
  --protocol BSEC_AQP_Development_Gate_v1/config/frozen_continuation_v3.json \
  --output BSEC_AQP_Development_Gate_v1/outputs/final_confirmation/realcartest_3200_3830/clip_inference \
  --unit-count 63 --absolute-index-start 320 --device cpu --threads 31 --execute
```

Each scorer writes a label-blind inference ledger, media hashes, checkpoint hashes, and sealed ranking. It must report an empty forbidden-input list and zero physical oracle calls.

## Recompute gates and post-hoc audits

```bash
python BSEC_AQP_Development_Gate_v1/scripts/run_frozen_gate.py
python BSEC_AQP_Development_Gate_v1/scripts/run_continuation_gate.py
python BSEC_AQP_Development_Gate_v1/scripts/run_final_confirmation_gate.py
python BSEC_AQP_Development_Gate_v1/scripts/audit_arc_seed_robustness.py --seed-count 1000
python BSEC_AQP_Development_Gate_v1/scripts/run_pstr_exploration.py
python BSEC_AQP_Development_Gate_v1/scripts/run_pstr_exploration_v2.py
```

The ARC seed audit and both PSTR runs are explicitly post-hoc. The v2 PSTR runner adds dataset3 and supersedes the four-domain exploration without deleting it. These runs do not alter the frozen v3 decision or create new unseen data.

## Verify

```bash
python -m py_compile BSEC_AQP_Development_Gate_v1/scripts/*.py
python BSEC_AQP_Development_Gate_v1/scripts/verify_package.py
```

Expected terminal verifier status is `PASS`. `FINAL_OUTPUT_MANIFEST.csv` inventories all non-cache package files except the manifest files themselves.
