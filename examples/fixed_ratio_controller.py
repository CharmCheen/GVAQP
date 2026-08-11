from garc.controller import FixedRatioController, PublicState

state = PublicState(remaining_budget_sec=120, estimated_scan_cost_sec=1,
                    estimated_confirm_cost_sec=float("inf")).to_dict()
controller = FixedRatioController()
controller.reset(120, state)
print(controller.choose_action(state))
