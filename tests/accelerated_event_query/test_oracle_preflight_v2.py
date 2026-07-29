import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash


ROOT = Path(__file__).resolve().parents[2]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = load_script("aeq_v2_runner_test", "scripts/run_accelerated_event_query_oracle_preflight_v2.py")
ANALYZER = load_script("aeq_v2_analyzer_test", "scripts/analyze_accelerated_event_query_oracle_preflight_v2.py")


def raw_for(label):
    common = {"confidence": "medium", "evidence": "visible evidence"}
    if label == "relevant":
        value = {"label": label, "event_start_sec": 1.0, "event_end_sec": 2.0,
                 "required_response": ["slowdown"], "cause": "visible hazard",
                 **common, "unknown_reason": None}
    elif label == "not_relevant":
        value = {"label": label, "event_start_sec": None, "event_end_sec": None,
                 "required_response": [], "cause": None, **common, "unknown_reason": None}
    else:
        value = {"label": label, "event_start_sec": None, "event_end_sec": None,
                 "required_response": [], "cause": "possible hazard", **common,
                 "unknown_reason": "motion ambiguous"}
    return json.dumps(value, sort_keys=True)


def synthetic_records(labels, sensitivity_overrides=None):
    prereg, _, selection, _, _ = RUNNER.frozen_context()
    records = {}
    sensitivity_overrides = sensitivity_overrides or {}
    for shard in RUNNER.SHARDS:
        for call in RUNNER.schedule_for_shard(prereg, selection, shard):
            candidate = call["clip"]["candidate_id"]
            label = sensitivity_overrides.get(candidate, labels[candidate]) \
                if call["variant"] == "fps_sensitivity" else labels[candidate]
            raw = raw_for(label)
            records[(shard, RUNNER.artifact_name(call))] = {
                "model_input_identity_sha256": f"{candidate}:2" if call["sampling_fps"] == 2.0 else f"{candidate}:4",
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "parse_status": "ok",
                "effective_label": label,
                "parsed": json.loads(raw),
            }
    return prereg, selection, records


def review_consensus(prereg):
    return json.loads((ROOT / prereg["bindings"]["review_consensus_path"]).read_text())


@pytest.mark.parametrize("collapsed_label", ["unknown", "not_relevant", "relevant"])
def test_degenerate_single_class_oracles_cannot_pass(collapsed_label):
    prereg, selection, records = synthetic_records({
        clip["candidate_id"]: collapsed_label
        for clip in RUNNER.frozen_context()[2]["clips"]
    })
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["class_support_pass"] is False
    assert result["numeric_gate_pass"] is False
    assert result["overall_gate_status"] == "FAIL_NUMERIC_OR_SUPPORT_GATE"


def aligned_labels(selection):
    labels = {clip["candidate_id"]: "not_relevant" for clip in selection["clips"]}
    labels.update({
        "DALI_u0501": "unknown",
        "DALI_u0548": "relevant",
        "DALI_u0555": "relevant",
        "HANGZHOU_u0280": "unknown",
        "WUHAN_u0134": "unknown",
        "WUHAN_u0171": "relevant",
        "WUHAN_u0217": "relevant",
    })
    return labels


def test_valid_numeric_mix_still_cannot_auto_pass_claim_grounding():
    selection = RUNNER.frozen_context()[2]
    prereg, selection, records = synthetic_records(aligned_labels(selection))
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["numeric_gate_pass"] is True
    assert result["semantic_contradictions"] == []
    assert result["overall_gate_status"] == "PENDING_INDEPENDENT_CLAIM_GROUNDING_REVIEW"
    assert len(result["positive_claims_pending_grounding"]) == 4


def test_unknown_sampling_transition_requires_review():
    selection = RUNNER.frozen_context()[2]
    labels = aligned_labels(selection)
    prereg, selection, records = synthetic_records(
        labels, sensitivity_overrides={"DALI_u0555": "unknown"}
    )
    result = ANALYZER.evaluate_records(prereg, selection, review_consensus(prereg), records)
    assert result["sampling_unknown_transitions"] == 1
    assert result["overall_gate_status"] == "REVIEW_REQUIRED"


def authenticated_record_fixture():
    runner, prereg, _, _, calls = ANALYZER.expected_calls()
    expected = calls[0]
    raw = raw_for("not_relevant")
    parsed = json.loads(raw)
    model_hash = runner.model_input_identity(expected["identity"], [
        {**frame, "rgb": None} for frame in expected["frame_set"]["frames"]
    ])
    record = {
        "identity": expected["identity"],
        "input_identity_sha256": canonical_hash(expected["identity"]),
        "model_input_identity_sha256": model_hash,
        "frames": expected["frame_set"]["frames"],
        "parse_status": "ok",
        "effective_label": "not_relevant",
        "parsed": parsed,
        "raw": raw,
        "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "runtime": {"declared_physical_gpus": [0, 1],
                    "gpu_identities": ["0, NVIDIA A100, GPU-a", "1, NVIDIA A100, GPU-b"]},
    }
    record["record_sha256"] = canonical_hash(record)
    return runner, expected, record


def test_record_validator_rejects_raw_tampering():
    runner, expected, record = authenticated_record_fixture()
    ANALYZER.validate_record(runner, expected, record)
    record["raw"] += " "
    with pytest.raises(RuntimeError, match="self-hash"):
        ANALYZER.validate_record(runner, expected, record)


def test_record_validator_rejects_frame_tampering_even_with_new_self_hash():
    runner, expected, record = authenticated_record_fixture()
    record["frames"] = [dict(frame) for frame in record["frames"]]
    record["frames"][0]["decoded_index"] += 1
    record["record_sha256"] = canonical_hash({key: value for key, value in record.items()
                                               if key != "record_sha256"})
    with pytest.raises(RuntimeError, match="frame identity"):
        ANALYZER.validate_record(runner, expected, record)
