from garc_eval.scan_headroom.trusted_policies import PublicScanState, PublicUnit
from garc_eval.scan_scheduler import SafeCoverageConfig, SafeCoveragePolicy

def state(scanned=()):
    units=tuple(PublicUnit(f'u{i}',i*10.0,(i+1)*10.0) for i in range(9))
    return PublicScanState(units,tuple(scanned),None,60.0,())

def test_default_is_public_state_anytime_largest_gap():
    policy=SafeCoveragePolicy(); first=policy.choose_next_unit(state())
    assert policy.policy_id=='ANYTIME_LARGEST_GAP' and first=='u4'

def test_all_modes_return_unscanned_units():
    for name in ('SEQUENTIAL','UNIFORM_PREFIX','ANYTIME_LARGEST_GAP','MACRO_REGION_LARGEST_GAP'):
        policy=SafeCoveragePolicy(SafeCoverageConfig(name,3)); first=policy.choose_next_unit(state()); second=policy.choose_next_unit(state((first,)))
        assert first!=second

def test_invalid_policy_rejected():
    try: SafeCoverageConfig('YOLO_ORACLE')
    except ValueError: pass
    else: raise AssertionError('invalid policy accepted')
