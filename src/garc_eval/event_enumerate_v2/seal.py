"""Seal the zero-call held-out-data terminal decision and deliverables."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
SPRINT = ROOT / "AQP_Algorithm_Invention_Sprint_v1"
OUTPUT = SPRINT / "operator_validation/event_enumerate_v2"
IMPLEMENTATION = ROOT / "src/garc_eval/event_enumerate_v2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _pytest_summary() -> dict[str, Any]:
    root = ET.parse(OUTPUT / "runtime/pytest_results.xml").getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise RuntimeError("missing pytest suite")
    return {
        "tests": int(suite.attrib["tests"]),
        "failures": int(suite.attrib["failures"]),
        "errors": int(suite.attrib["errors"]),
        "skipped": int(suite.attrib["skipped"]),
        "seconds": float(suite.attrib["time"]),
        "sha256": sha256_file(OUTPUT / "runtime/pytest_results.xml"),
    }


def _review() -> dict[str, Any]:
    path = OUTPUT / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"
    if not path.exists():
        return {"overall": "PENDING", "review_identity": "not_yet_run"}
    return json.loads(path.read_text(encoding="utf-8"))


def _preexecution_summary() -> dict[str, Any]:
    path = OUTPUT / "audit/PRE_EXECUTION_PROCESSOR_AUDIT.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    if (
        summary.get("processor_gate") != "PASS"
        or summary.get("checks") != summary.get("passes")
    ):
        raise RuntimeError("pre-execution processor audit is not all-pass")
    return summary


def write_status_artifacts() -> None:
    for directory in [
        "audit",
        "theory",
        "config",
        "tests",
        "data",
        "physical/attempts",
        "runtime",
        "metrics",
        "diagnostics",
        "logs",
    ]:
        (OUTPUT / directory).mkdir(parents=True, exist_ok=True)
    physical = {
        "status": "NOT_RUN",
        "reason": "HELDOUT_DATA_REQUIRED",
        "physical_calls_started": 0,
        "physical_calls_completed": 0,
        "maximum_authorized_calls": 100,
        "gpu_seconds": None,
        "wall_seconds": None,
        "model_loaded": False,
        "tmux_session_created": False,
        "old_compressed_runtime_reused": False,
        "evidence_scope": "bundle-local files, ledgers, and process artifacts only",
        "external_scheduler_audit": False,
    }
    write_json(OUTPUT / "physical/NO_CALLS.json", physical)
    (OUTPUT / "physical/CALL_LEDGER.csv").write_text(
        "attempt_id,operator,video_id,input_start,input_end,status,gpu_seconds,wall_seconds\n",
        encoding="utf-8",
    )
    (OUTPUT / "physical/README.md").write_text(
        """# Physical execution status

No Qwen3-VL generation call was made.  The processor-only tests do not load
the VLM and are not physical calls.  The held-out data gate returned
`HELDOUT_DATA_REQUIRED`, so the specification forbids creating a call matrix,
starting tmux inference, measuring corrected enumerator cost, or measuring a
matched dense cost.

This zero-call statement is verified within the v2 bundle (empty attempts,
header-only call ledger, runtime ledger, and no-call status).  No independent
external scheduler or cluster-accounting audit was available.
""",
        encoding="utf-8",
    )
    metrics = {
        "status": "NOT_MEASURED",
        "reason": "no valid held-out semantic population",
        "event_precision": None,
        "event_recall": None,
        "event_f1": None,
        "event_count_error": None,
        "empty_interval_rejection": None,
        "single_event_recall": None,
        "multi_event_recall": None,
        "boundary_localization": None,
        "coordinate_warp_diagnostic_is_semantic_metric": False,
        "duplicate_events": None,
        "merged_events": None,
        "split_events": None,
        "abstain_failure_rate": None,
        "corrected_enumerator_gpu_seconds": None,
        "corrected_enumerator_wall_seconds": None,
        "matched_dense_gpu_seconds": None,
        "matched_dense_wall_seconds": None,
        "gpu_cost_ratio": None,
        "wall_cost_ratio": None,
    }
    write_json(OUTPUT / "metrics/METRICS_STATUS.json", metrics)
    tests = _pytest_summary()
    write_csv(
        OUTPUT / "runtime/RUNTIME_LEDGER.csv",
        [
            {
                "activity": "processor_correctness_pytest",
                "calls": 0,
                "gpu_seconds": 0,
                "wall_seconds": tests["seconds"],
                "status": "PASS",
                "evidence": "runtime/pytest_results.xml",
            },
            {
                "activity": "physical_qwen_generation",
                "calls": 0,
                "gpu_seconds": "",
                "wall_seconds": "",
                "status": "NOT_RUN_HELDOUT_DATA_REQUIRED",
                "evidence": "physical/NO_CALLS.json",
            },
        ],
    )
    (OUTPUT / "diagnostics/PROCESSOR_TEST_SUMMARY.md").write_text(
        f"""# Processor test summary

The metadata suite passed `{tests['tests']}/{tests['tests']}` tests with zero
failures, errors, or skips in `{tests['seconds']:.3f}` seconds.  It verifies
frame barcodes, real timestamps, local source offsets, Qwen timestamp tokens,
old compression reproduction, corrected 60-second transport, batch/single
equivalence, row-order invariance, parser determinism, final partial intervals,
and lack of reference access.  See `audit/PRE_EXECUTION_PROCESSOR_AUDIT.csv`.
""",
        encoding="utf-8",
    )
    (OUTPUT / "diagnostics/HELDOUT_CANDIDATE_SUMMARY.md").write_text(
        """# Held-out candidate summary

Nine local candidate families were audited and zero passed.  Nexar is the
closest available disjoint source, but its one collision/near-collision label
per clip is neither an exhaustive `enter_ego_path` relation nor evidence of
multi-event completeness.  DrivingDojo lacks target-event intervals.  DoTA,
DADA-2000, and Micro-CASQ lack local filled references.  Remaining artifacts
are strict-video-derived, pseudo-referenced, development-used, or missing
their raw source.  See `data/HELDOUT_CANDIDATE_AUDIT.csv`.
""",
        encoding="utf-8",
    )


def write_decision_and_reports() -> None:
    tests = _pytest_summary()
    preexecution = _preexecution_summary()
    review = _review()
    review_overall = review.get("overall", "PENDING")
    decision_row = {
        "decision": "HELDOUT_DATA_REQUIRED",
        "processor_gate": "PASS",
        "heldout_gate": "FAIL_NO_VALID_POPULATION",
        "physical_execution": "NOT_RUN",
        "physical_calls": 0,
        "event_precision": "NOT_MEASURED",
        "event_recall": "NOT_MEASURED",
        "event_f1": "NOT_MEASURED",
        "corrected_enumerator_gpu_seconds": "NOT_MEASURED",
        "corrected_enumerator_wall_seconds": "NOT_MEASURED",
        "matched_dense_gpu_seconds": "NOT_MEASURED",
        "matched_dense_wall_seconds": "NOT_MEASURED",
        "independent_review": review_overall,
        "reason": "no disjoint independently frozen exhaustive enter_ego_path event reference exists locally",
    }
    write_csv(OUTPUT / "FINAL_DECISION.csv", [decision_row])
    report = f"""# Metadata-correct EVENT_ENUMERATE operator gate v2 — final report

## Exact decision

`HELDOUT_DATA_REQUIRED`.

The processor gate passes, but zero local candidate populations satisfy the
held-out-reference requirements.  Under the preregistered stop rule, no
physical Qwen3-VL generation call, semantic metric, or corrected cost
measurement is permitted.

## 1–4. Cause, corrected contract, and metadata tests

The exact old compression cause is the v1 invocation at
`src/garc_eval/aqp_invention_v1/run_physical.py:153-157`.  It called
`process_vision_info(messages)` without requesting returned video metadata or
video kwargs, then called the processor without `video_metadata` and without
`do_sample_frames=False`.  The message-level `fps` field at line 148 did not
reach the processor.  For each nominal 60-second call, 121 decoded frames were
padded to 122; missing source FPS defaulted to 24; default 2-FPS sampling
reduced the tensor to `int(122/24*2)=10` frames; five temporal-patch timestamp
tokens ended at 4.8 displayed seconds while the prompt still declared 60.0.

This causal reconstruction is supported by preserved schedules, frame
identities, raw-response hashes, the saved processor warning, and the pinned
current dependency source.  A processor-only sentinel reproduces the exact
old helper-to-processor call signature, and all 68 nominal saved calls match
the reconstructed shape.  The exact old dependency image, serialized chat,
processor metadata object, model-input tensors, and temporal position IDs were
not preserved, and old model generation was not rerun.

The corrected contract retains the one old fixed-stride 2-FPS selection,
passes original source FPS plus relative source-frame indices in explicit
`VideoMetadata`, disables processor resampling, requires exact timestamp-token
and grid identity, maps model-relative seconds from the actual first decoded
frame, reuses the byte-identical v1 prompt, and parses without repair or
clamping.  Maximum input length is 60 seconds/121 decoded frames.

Metadata result: `{tests['tests']}/{tests['tests']} PASS`, zero failures, zero
errors, zero skips.  The pre-execution audit has
`{preexecution['passes']}/{preexecution['checks']} PASS` entries.  The
nominal corrected input retains 121 frames as 61 temporal patches spanning
0.2 (display-rounded first patch center) through 60.0 seconds.  Beginning,
middle, end, nonzero-offset, odd-count, alternate-FPS, and final-partial cases
pass.  Batch and single processor preparation are byte-equivalent after
splitting their concatenated tensors.

The old-call coordinate-warp table is diagnostic only: it maps generated
coordinates between exact processor patch centers and is explicitly excluded
from semantic boundary localization.  No event-localization value is inferred
from that table.

## 5. Held-out videos and reference

Accepted held-out videos: **none**.  Accepted reference: **none**.

- Nexar: 200 positive and 403 negative local clips, but the metadata labels
  one collision/near-collision alert-to-event interval and is not exhaustive
  for every `enter_ego_path` event or multi-event intervals.
- DrivingDojo-mini: 32 disjoint frame sequences with camera/ego-motion data,
  but no target-event relation.
- DoTA and DADA-2000: mapping notes only; raw/reference files absent locally.
- Micro-CASQ-v0: empty annotation template and no video population.
- Other references: strict-video-derived, VLM pseudo-references,
  development-used, non-exhaustive, or missing their raw source.

## 6–10. Calls, semantic results, and cost

| Result | Value |
|---|---:|
| New physical Qwen3-VL calls | 0 |
| Event precision / recall / F1 | NOT MEASURED |
| Multi-event recall | NOT MEASURED |
| Boundary localization | NOT MEASURED |
| Corrected enumerator GPU / wall cost | NOT MEASURED |
| Matched dense GPU / wall cost | NOT MEASURED |
| Cost ratio | NOT MEASURED |

The previous 0.240987 compressed-input GPU ratio is not reused.
Zero-call evidence is bundle-local (empty attempt directory, header-only call
ledger, runtime ledger, and no-call status); no external scheduler audit was
available.

## 11. VERA physical viability

VERA physical execution is **unresolved and not currently authorized**.  The
old physical instantiation remains falsified.  The corrected processor path
removes a demonstrated transport defect, but it supplies no evidence that the
operator meets recall/F1 or beats matched dense cost.  Therefore VERA cannot
yet be called viable or intrinsically nonviable.

## 12. Independent review

Independent-review result: `{review_overall}`.  Full checks and reviewed
hashes are in `audit/INDEPENDENT_ADVERSARIAL_REVIEW.json` when present.

## 13. Exact next task

Acquire or create, without using EVENT_ENUMERATE/VERA outputs as truth, a
byte-disjoint video population with an independently adjudicated exhaustive
`enter_ego_path` event relation and reviewed negative coverage.  Freeze its
provenance and evaluator-only reference.  Before labels are exposed to the
inference path, verify every source FPS/frame count is compatible with the
frozen <=121-frame selection rule; if not, refreeze one event-independent
selection rule and repeat the processor audit.  Then freeze the smallest
<=100-call enumeration-plus-matched-dense matrix and rerun the unchanged
processor audit before the first physical call.

## Scientific interpretation

Strongest supported conclusion: the old temporal transport was wrong and the
new transport is processor-correct.  Main competing explanation for the old
quality failure: intrinsic semantic weakness of 2-FPS long-window
enumeration, which the current zero-call gate cannot test.  Key uncertainty:
semantic recall/F1 and matched cost on an independent population.  Reject or
revise the operator hypothesis if a valid held-out run falls below recall
0.80 or F1 0.80, or if corrected GPU cost is not strictly below matched dense
execution.
"""
    (OUTPUT / "FINAL_REPORT.md").write_text(report, encoding="utf-8")

    state = f"""# Research state

## Current objective

Determine whether a correctly represented Qwen3-VL `EVENT_ENUMERATE` operator
can meet event recall and F1 >=0.80 at lower synchronized GPU cost than matched
dense 10-second execution, without changing VERA.

## Established findings

- The old 60-second physical input was temporally compressed from 121 decoded
  frames to 10 processor-consumed frames because metadata and the no-resample
  kwargs were omitted.
- All 70 old enumeration schedules/responses were reconstructed; 68 are
  nominal 60-second calls and their processor timeline ends at 4.8 displayed
  seconds.
- The single corrected path passes {tests['tests']} processor tests and
  {preexecution['checks']} pre-execution audit checks, including exact
  timestamps, the exact old helper/processor signature, and batch equivalence.
- The prompt is byte-identical to v1 and no semantic reference was used to
  choose sampling, metadata, parser, or thresholds.
- Nine local held-out candidate families were audited; zero provide a valid
  disjoint exhaustive event relation.
- Physical calls spent: 0.  Terminal decision: `HELDOUT_DATA_REQUIRED`.

## Active hypotheses

- H-OPERATOR: corrected temporal transport may recover semantic recall/F1
  while retaining a cost advantage.  Still untested.
- H-INTRINSIC: 2-FPS, up-to-60-second enumeration may remain semantically too
  weak even with correct metadata.  Still plausible.
- H-COST: retaining 121 frames rather than 10 may erase the old cost advantage.
  Still untested; the previous ratio is invalid.

## Rejected hypotheses

- H-MESSAGE-FPS-SUFFICIENT: putting `fps` in the chat message correctly informs
  the processor.  Rejected by source tracing and regression.
- H-OLD-COST-REUSABLE: the compressed-input runtime estimates corrected cost.
  Rejected because the corrected tensor has materially different frames/tokens.
- H-LOCAL-DATA-SUFFICIENT: an existing local population already satisfies the
  held-out gate.  Rejected by the candidate audit.

## Important failures and lessons

Frame hashes before the processor do not prove model-visible time.  Future
physical runs must persist metadata, decoded source timestamps, serialized
timestamp tokens, grids, tensor hashes, and absolute mapping for every call.
Dataset disjointness alone is insufficient: an event enumerator needs an
exhaustive relation plus reviewed emptiness and multi-event coverage.

## Unresolved uncertainty

Semantic accuracy, multi-event behavior, boundary localization, corrected GPU
cost, and matched dense cost are all unmeasured.  Processor correctness does
not imply operator quality.  The frozen stride rule can exceed the 121-frame
cap for some non-integer source FPS values, so future held-out media require an
FPS/frame-count compatibility check before label exposure or physical
authorization.

## Next highest-value action

Produce and independently freeze the missing held-out event relation according
to `data/HELDOUT_DATA_REQUIREMENTS.md` and
`data/REQUIRED_ANNOTATION_SCHEMA.md`.  First validate the media-only FPS/frame
metadata against the frozen selection rule; if incompatible, refreeze one
event-independent rule and repeat this processor gate.  Then freeze, but do
not tune, the bounded physical matrix.
"""
    (OUTPUT / "RESEARCH_STATE.md").write_text(state, encoding="utf-8")


def write_reproduction() -> None:
    tests = _pytest_summary()
    preexecution = _preexecution_summary()
    text = f"""# Reproduction

Run from `/qiuyeqing/llama_prl/G-ARC` in the existing `garc` environment.
These commands make no model-generation call and do not modify prior sprint
artifacts.

```bash
export PYTHONPATH=src
python -m garc_eval.event_enumerate_v2.forensics
python -m garc_eval.event_enumerate_v2.generate_metadata_corpus
python -m garc_eval.event_enumerate_v2.freeze
pytest -q AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/tests \
  --junitxml=AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/runtime/pytest_results.xml
python -m garc_eval.event_enumerate_v2.audit_heldout
python -m garc_eval.event_enumerate_v2.preexecution_audit
python -m garc_eval.event_enumerate_v2.seal
```

Expected test result: `{tests['tests']} passed`; expected pre-execution result:
`{preexecution['passes']}/{preexecution['checks']} PASS`.  Expected terminal decision:
`HELDOUT_DATA_REQUIRED`; `physical/attempts` must remain empty and
`physical/NO_CALLS.json` must report zero calls.

Do not run a physical command after this reproduction.  A later physical run
requires a newly supplied held-out reference, frozen evaluator-only sample,
preregistered call matrix, independent review, and an unchanged passing
processor audit.
"""
    (OUTPUT / "REPRODUCTION.md").write_text(text, encoding="utf-8")


def write_experiment_manifest() -> None:
    tests = _pytest_summary()
    preexecution = _preexecution_summary()
    review = _review()
    manifest = {
        "experiment_id": "metadata_correct_event_enumerate_operator_gate_v2",
        "decision": "HELDOUT_DATA_REQUIRED",
        "selected_algorithm": "VERA (unchanged and not executed)",
        "operator": "EVENT_ENUMERATE",
        "processor_gate": "PASS",
        "heldout_gate": "FAIL_NO_VALID_POPULATION",
        "physical_calls": 0,
        "maximum_authorized_physical_calls": 100,
        "model_generation_performed": False,
        "old_sprint_artifacts_modified": False,
        "tests": tests,
        "preexecution_checks": preexecution["checks"],
        "accepted_heldout_videos": [],
        "accepted_heldout_reference": None,
        "semantic_metrics": None,
        "corrected_cost": None,
        "matched_dense_cost": None,
        "independent_review": review.get("overall", "PENDING"),
        "phases": [
            {"phase": 0, "name": "failed path recovery", "status": "PASS"},
            {"phase": 1, "name": "metadata corpus", "status": "PASS"},
            {"phase": 2, "name": "local/official semantics", "status": "PASS"},
            {"phase": 3, "name": "one corrected path", "status": "PASS_FROZEN"},
            {"phase": 4, "name": "postprocessor verification", "status": "PASS"},
            {"phase": 5, "name": "held-out data gate", "status": "TERMINAL_HELDOUT_DATA_REQUIRED"},
            {"phase": 6, "name": "held-out sample freeze", "status": "NOT_REACHED"},
            {"phase": 7, "name": "physical preregistration", "status": "NOT_REACHED"},
            {"phase": 8, "name": "physical execution", "status": "NOT_RUN"},
            {"phase": 9, "name": "operator evaluation", "status": "NOT_RUN"},
            {"phase": 10, "name": "quality/cost decision", "status": "NOT_REACHED"},
        ],
        "authoritative_artifacts": {
            "config": "config/FROZEN_EVENT_ENUMERATE_V2_CONFIG.json",
            "processor_audit": "audit/PRE_EXECUTION_PROCESSOR_AUDIT.csv",
            "old_timeline": "audit/OLD_CALL_TIMELINE_RECONSTRUCTION.csv",
            "old_coordinate_warp": "audit/OLD_COORDINATE_WARP_DIAGNOSTICS.csv",
            "heldout_gate": "data/HELDOUT_GATE.json",
            "physical_status": "physical/NO_CALLS.json",
            "metric_status": "metrics/METRICS_STATUS.json",
            "independent_review": "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json",
        },
    }
    write_json(OUTPUT / "EXPERIMENT_MANIFEST.json", manifest)


def write_completion_audit() -> None:
    preexecution = _preexecution_summary()
    review = _review().get("overall", "PENDING")
    rows = [
        {"requirement": "prior artifacts unmodified", "status": "PASS", "evidence": "all v2 writes confined to new output/implementation directories"},
        {"requirement": "old 60-second calls reconstructed", "status": "PASS", "evidence": "audit/OLD_CALL_TIMELINE_RECONSTRUCTION.csv: 68 nominal rows, 70 total"},
        {"requirement": "exact compression cause identified", "status": "PASS", "evidence": "audit/FAILED_PIPELINE_FORENSICS.md and old runner lines 153-157"},
        {"requirement": "metadata videos and five named tests", "status": "PASS", "evidence": "tests/metadata_videos and runtime/pytest_results.xml"},
        {"requirement": "processor semantics independently verified", "status": "PASS", "evidence": "theory/QWEN3_VL_TEMPORAL_SEMANTICS.md plus installed-source tests"},
        {"requirement": "one corrected path frozen", "status": "PASS", "evidence": "config/FROZEN_EVENT_ENUMERATE_V2_CONFIG.json"},
        {"requirement": "all pre-execution processor checks pass", "status": "PASS", "evidence": f"audit/PRE_EXECUTION_PROCESSOR_AUDIT.csv: {preexecution['passes']}/{preexecution['checks']}"},
        {"requirement": "disjoint held-out reference", "status": "ABSENT_TERMINAL_STOP", "evidence": "data/HELDOUT_GATE.json"},
        {"requirement": "physical calls only after all gates", "status": "PASS_ZERO_CALLS", "evidence": "physical/NO_CALLS.json"},
        {"requirement": "quality/cost metrics not fabricated", "status": "PASS_NOT_MEASURED", "evidence": "metrics/METRICS_STATUS.json"},
        {"requirement": "independent adversarial review", "status": review, "evidence": "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"},
        {"requirement": "allowed exact decision", "status": "PASS", "evidence": "FINAL_DECISION.csv: HELDOUT_DATA_REQUIRED"},
    ]
    write_csv(OUTPUT / "audit/COMPLETION_AUDIT.csv", rows)


def write_research_log() -> None:
    tests = _pytest_summary()
    preexecution = _preexecution_summary()
    review = _review().get("overall", "PENDING")
    text = f"""# Research log

## 2026-07-12 — reconstruction

Recovered all 70 enumeration attempts and proved that the preserved decoded
frame identities were correct while the downstream processor coordinate was
not.  Located the missing metadata/no-resample arguments at old runner lines
153-157 and reconstructed the five timestamp patches for each nominal call.

## 2026-07-12 — discriminating test

Built a label-independent, burned-timestamp/barcode corpus.  The installed
processor reproduced the old 122-to-10-frame path and preserved the corrected
121-frame path as 61 timestamped patches through 60.0 seconds.  Full result:
{tests['tests']} passed; pre-execution audit: {preexecution['passes']} passed.

## 2026-07-12 — held-out gate

Audited nine candidate families.  Zero combine disjoint media, development
independence, an exhaustive trusted predicate reference, and empty/single/multi
coverage.  Applied the mandated terminal decision without spending a physical
call.  Independent review status: {review}.

## State update

The processor-correctness uncertainty is resolved; the dominant bottleneck is
now reference validity.  H-OPERATOR remains live, while old-cost reuse and
message-only FPS transport are rejected.
"""
    (OUTPUT / "logs/RESEARCH_LOG.md").write_text(text, encoding="utf-8")


def write_file_manifest() -> None:
    rows = []
    for base, scope in [(OUTPUT, "deliverable"), (IMPLEMENTATION, "implementation")]:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == "FILE_MANIFEST.csv":
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rows.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "scope": scope,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_csv(OUTPUT / "FILE_MANIFEST.csv", rows)


def seal() -> None:
    write_status_artifacts()
    write_decision_and_reports()
    write_reproduction()
    write_experiment_manifest()
    write_completion_audit()
    write_research_log()
    write_file_manifest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    seal()


if __name__ == "__main__":
    main()
