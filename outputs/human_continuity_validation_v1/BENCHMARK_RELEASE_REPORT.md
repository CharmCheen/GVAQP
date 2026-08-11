# Human Event-Continuity Benchmark: Ready for Blinded Annotation

## Frozen contract

- Base human protocol: `06deda4503981179bdd2bc9157f94f80c104dcc7fffb5e866da4fd10325716ac`.
- Active pre-label analysis clarification R2: `7eb23201edd5d72d2fc040e9150098df3df015b82fc5372a3a6f09e999e8bdd1`.
- This is a **POST-P0 independent human validation**. Existing P0 results were known; human labels observed when the protocol, population, samples, clips, and R2 decision rules were frozen: **0**.
- R2 changes no video, query, VLM unit label, reference relation, C0/C1/K3 definition, sample, or clip. It makes the reserve-unlock and analysis rules operational before annotation starts.

## Population and blinded samples

The hidden population has 248 consecutive full-grid VLM-positive anchor pairs: 81 DALI, 92 HANGZHOU, and 75 WUHAN. The public primary workload is 40 cases, source-balanced 13/13/14. The 20-case reserve is independently frozen and locked (7/7/6); it may be opened only under R2's objective `INCONCLUSIVE_PRIMARY` rule.

The annotator only receives opaque `CASE_####` identities, the frozen predicate text, full A-to-B video context, and neutral A/B markers. C0/C1/K3 predictions, hidden anchor IDs/times, event IDs, P0 metrics, selectors, and model-relative reference data remain outside `annotation_package/`.

## QA evidence

- 40 blinded primary cases and 56 MP4 clips were rendered.
- Every rendered clip decodes (`ANNOTATION_PACKAGE_QA_V2.csv`).
- 96 expected A/B marker exposures passed pixel-level verification (`ANNOTATION_MARKER_QA.csv`).
- Static-package and live `/api/cases` checks found no method/result leakage.
- The deterministic random public order is not source-video/time order.
- `serve_human_continuity_annotation.py --self-test` passed append, edit/latest-answer, and restart/resume semantics without touching this package.
- `HUMAN_LABELS_PRIMARY.jsonl` is empty and no frozen-label CSV exists.

## Annotation entrypoint

From the repository root:

```bash
python scripts/serve_human_continuity_annotation.py \
  --package outputs/human_continuity_validation_v1/
```

Open `http://127.0.0.1:8765/`. Each case receives exactly one of `SAME_EVENT`, `DIFFERENT_EVENTS`, `ANCHOR_INVALID`, or `UNCERTAIN`; answers autosave immediately. At 40 completed cases the server writes and hashes the immutable frozen primary label CSV. Then run:

```bash
python scripts/analyze_human_continuity_validation.py \
  --package outputs/human_continuity_validation_v1/
```

The analyzer refuses to inspect partial JSONL progress records.
