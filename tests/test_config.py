import json

import pytest

from rc_sem import RCSEMConfig, config_sha256, config_to_dict, load_config


def test_reference_config_round_trip_matches_code_defaults():
    config, status = load_config("configs/rc_sem_reference_v1.json")
    assert config == RCSEMConfig()
    assert status == "STAGING_NOT_CONFIRMATORY"
    assert config_to_dict(config, status=status) == json.loads(
        open("configs/rc_sem_reference_v1.json", encoding="utf-8").read()
    )
    assert len(config_sha256(config, status=status)) == 64


def test_config_loader_rejects_extra_keys(tmp_path):
    payload = config_to_dict(RCSEMConfig())
    payload["post_hoc_threshold"] = 0.5
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="top-level key mismatch"):
        load_config(path)
