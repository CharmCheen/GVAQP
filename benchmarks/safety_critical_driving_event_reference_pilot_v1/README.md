# Safety-Critical Driving Event Reference Pilot v1

This is a reference-construction pilot, not a replacement for
`partial_scan_pilot_v1` and not an online SCAN benchmark.

## Objective

Test whether a frozen Qwen3-VL-based, two-stage protocol can construct a
useful open-set reference for safety-critical driving events:

```text
full-context window
  -> Stage A high-recall observable-event discovery
  -> Stage B proposal-local safety adjudication
  -> blinded human adjudication
  -> pre-registered reference gate
```

No candidate generator, policy, matcher, or benchmark utility is changed by
this pilot.  No VLM label produced here is human ground truth.

## Current authority

- `contracts/research_contract.json` defines scope and prohibitions.
- `contracts/taxonomy_v1.json` defines the extensible event families.
- `contracts/sample_design_v1.json` defines blinded sample construction.
- `contracts/reference_gate_draft_v1.json` contains **working**, not yet
  preregistered, acceptance thresholds.
- `contracts/arm_comparison_draft_v1.json` defines the paired single-stage vs
  two-stage comparison without assuming a winner.
- `contracts/human_review_contract_v1.json` freezes the blinding boundary and
  disagreement process; no human labels have been collected.
- `prompts/` contains the frozen candidates for Stage A and Stage B.
- `prompts/single_stage_control_v1.txt` is the matched one-call control arm;
  it prevents assuming in advance that two stages are better.
- `../../src/garc_eval/safety_reference_pilot/` contains strict parsers and
  deterministic manifest construction.

## Execution boundary

The permitted first execution is CPU-only manifest construction and parser
testing.  Physical VLM calls and human-review effort require an explicit
launch decision after the sample-availability audit is complete.

Run the non-oracle preparation with:

```bash
PYTHONPATH=src python -m garc_eval.safety_reference_pilot.prepare
```

Generated private selection metadata and the blinded annotation manifest are
written below `derived/`.  The blinded manifest intentionally omits old VLM
labels, selection strata, and selection reasons.

Before inference, decoded frames must pass through `frame_labels.annotate_frames`.
This burns `Fnnn` and the exact source timestamp into each model-visible frame;
model frame indices are converted back through the saved mapping rather than
through nominal-FPS arithmetic.
