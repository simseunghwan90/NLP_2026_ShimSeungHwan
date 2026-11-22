import copy
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('r5_stages_validation',Path(__file__).with_name('validation.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_full_lat6_keeps_original_times():
    case=dict(lift=False,duration_s=394,commands=[[0,0,100,30,7],[3,75,0,30,7],[390,0,100,20,7]])
    original=copy.deepcopy(case)
    module.validate_case(case)
    assert case==original


@pytest.mark.parametrize('duration,lift',[(601,False),(0,False),(float('nan'),False),(394,True)])
def test_duration_extension_is_ground_only_and_bounded(duration,lift):
    with pytest.raises(ValueError):module.validate_case(dict(lift=lift,duration_s=duration,commands=[[0,0,100,0,7]]))


@pytest.mark.parametrize('row',[[3,101,0,30,7],[3,75,-1,30,7],[3,75,0,151,7],[3,75,0,30,8],[0,75,0,30,7],[395,75,0,30,7]])
def test_long_replay_does_not_weaken_wire_or_time_guards(row):
    with pytest.raises(ValueError):module.validate_case(dict(lift=False,duration_s=394,commands=[[0,0,100,30,7],row]))
