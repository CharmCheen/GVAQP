from garc_eval.public_event_cell_gate_v1.run_gate import structural_tests


def test_required_structural_cases():
    result = structural_tests()
    assert len(result) == 10
    assert result.passed.all(), result[~result.passed].to_dict("records")
