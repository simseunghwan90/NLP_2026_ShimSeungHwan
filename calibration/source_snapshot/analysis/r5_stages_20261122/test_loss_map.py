import copy
import json
import subprocess
import pytest
from common import ROOT
from model_validation_map import validate_model

def model():
    d=json.loads((ROOT/'models/candidates/drive_field_2026-11-21_trial03.json').read_text())
    d['powered_loss_map']=[[0,8.4],[.015,8.4],[.04,7],[.1,10]]
    return d

@pytest.mark.parametrize('table', [[[0,8],[.1,float('nan')]],[[0,8],[0,9]],[[.01,8],[.1,9]],[[0,8],[.1,-1]],[[0,8],[True,9]]])
def test_reject_invalid_loss_map(table):
    d=model();d['powered_loss_map']=table
    with pytest.raises(ValueError):validate_model(d)

def test_reject_ambiguous_loss_models():
    d=model();validate_model(d);d['powered_residual_offset_nm']=1
    with pytest.raises(ValueError):validate_model(d)

def test_native_map_boundaries(tmp_path):
    source=tmp_path/'map.cpp'
    source.write_text('''#include "PoweredLoss.h"
#include <cassert>
int main() {
  std::vector<std::pair<double,double>> m={{0,8.4},{.015,8.4},{.04,7},{.1,10}};
  for (double k : {0.,.01,.04,.08,.12}) {
    assert(mappedPoweredResidual(8.4,m,k,0,0)==8.4);
    assert(mappedPoweredResidual(8.4,m,k,75,1)==8.4);
    assert(mappedPoweredResidual(8.4,m,k,100,0)==8.4);
    assert(mappedPoweredResidual(8.4,m,k,75,0)==mappedPoweredResidual(8.4,m,-k,75,0));
  }
  assert(mappedPoweredResidual(8.4,m,.01,75,0)==8.4);
  assert(mappedPoweredResidual(8.4,m,.04,83,0)==7);
  assert(std::abs(mappedPoweredResidual(8.4,m,.04,84,0)-7.7)<1e-12);
  assert(mappedPoweredResidual(8.4,m,.2,75,0)==10);
}''')
    header=ROOT/'simulator/variants/r5_stages_20261122/Plugins/AirSim/Source/Vehicles/Car'
    exe=tmp_path/'check'
    subprocess.run(['g++','-std=c++14','-I',str(header),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
