from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.smdp_oracle import legal_binary_actions


class _Estimator:
    def __init__(self, value: float):
        self.value = value

    def estimate(self) -> float:
        return self.value


class _Env:
    order = [0, 1]
    scan_cursor = 0

    def __init__(self, remaining: float, frontier: int, scan: float = 2.0, verify: float = 5.0):
        self.remaining = remaining
        self.frontier_size = frontier
        self.scan = scan
        self.verify = verify
        self.confirm_estimator = _Estimator(verify)

    def public_state(self):
        return {
            "remaining_budget_sec": self.remaining,
            "frontier_size": self.frontier_size,
            "estimated_scan_cost_sec": self.scan,
            "estimated_confirm_cost_sec": self.verify if self.frontier_size else float("inf"),
        }


def test_scan_is_productive_illegal_without_reserved_verify_budget():
    assert Action.SCAN not in legal_binary_actions(_Env(6.0, frontier=0))
    assert Action.SCAN in legal_binary_actions(_Env(7.0, frontier=0))


def test_verify_requires_frontier_and_complete_cost_bound():
    assert Action.CONFIRM not in legal_binary_actions(_Env(10.0, frontier=0))
    assert Action.CONFIRM not in legal_binary_actions(_Env(4.0, frontier=1))
    assert Action.CONFIRM in legal_binary_actions(_Env(5.0, frontier=1))

