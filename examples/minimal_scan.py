from garc.scan import CoverageState, PublicUnit, SafeCoveragePolicy

units = tuple(PublicUnit(f"u{i}", i * 10.0, (i + 1) * 10.0) for i in range(9))
state = CoverageState(units)
print(SafeCoveragePolicy().choose_next_unit(state))  # u4
