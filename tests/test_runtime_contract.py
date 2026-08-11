from garc.confirm.parser import parse_confirm_response
from garc.confirm.prompt import load_confirm_prompt

def test_confirm_prompt_hash_and_parser_positive():
    assert 'object enters ego path' in load_confirm_prompt()
    value, status = parse_confirm_response('{"label":"positive","confidence":"high"}', 1.0)
    assert status == "ok" and value["label"] == "positive"

def test_confirm_parser_source_failure_policy():
    assert parse_confirm_response("not json", 1.0) == ({}, "no_json")
    value, status = parse_confirm_response('{"label":"other","confidence":"high"}', 1.0)
    assert status == "invalid_label" and value["label"] == "other"
