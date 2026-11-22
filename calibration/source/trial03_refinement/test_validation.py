import json
import pytest
from model_validation import validate_model
from setup import ROOT

@pytest.mark.parametrize('key,value',[
    ('powered_residual_offset_nm',-100),('powered_residual_offset_nm',float('nan')),
    ('powered_curvature_loss_nm_m2',-1),('powered_curvature_loss_nm_m2',float('inf')),
    ('powered_curvature_loss_nm_m2',True),('unknown_option',0)])
def test_invalid_physical_options_rejected(key,value):
    model=json.loads((ROOT/'models/candidates/drive_field_2026-11-21_trial03.json').read_text())
    model[key]=value
    with pytest.raises(ValueError):validate_model(model)

def test_trial03_and_candidate_valid():
    for name in ['drive_field_2026-11-21_trial03.json','drive_trial03_refine_2026-11-21_R1.json']:
        validate_model(json.loads((ROOT/'models/candidates'/name).read_text()))
