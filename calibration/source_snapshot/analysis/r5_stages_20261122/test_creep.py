import copy
import json
import subprocess
import pytest
from common import ROOT
from model_validation_map import validate_model


@pytest.mark.parametrize('value',[-1,16,float('nan'),True])
def test_creep_configuration_cannot_bypass_bounds(value):
    model=json.loads((ROOT/'models/candidates/drive_r5_stages_2026-11-22_S8C.json').read_text())
    model['powered_creep_resistance_nm']=value
    with pytest.raises(ValueError):validate_model(model)


@pytest.mark.parametrize('value',[.15,.81,float('nan'),True])
def test_creep_speed_transition_stays_bounded(value):
    model=json.loads((ROOT/'models/candidates/drive_r5_stages_2026-11-22_S8C.json').read_text())
    model['powered_creep_speed_zero_mps']=value
    with pytest.raises(ValueError):validate_model(model)


def test_creep_disabled_and_command_boundaries(tmp_path):
    source=tmp_path/'creep.cpp'
    source.write_text('''#include "PoweredCreep.h"
#include <cassert>
int main() {
  for (double k : {0.,.01,.07,.1}) for(double v : {0.,.15,.3,.6,10.}) {
    assert(poweredCreepLoss(0,k,v,75,0)==0);
    assert(poweredCreepLoss(8,k,v,0,0)==0);
    assert(poweredCreepLoss(8,k,v,75,1)==0);
    assert(poweredCreepLoss(8,k,v,85,0)==0);
    assert(poweredCreepLoss(8,k,v,100,0)==0);
    assert(poweredCreepLoss(8,k,v,75,0)==poweredCreepLoss(8,-k,-v,75,0));
    double loss=poweredCreepLoss(8,k,v,75,0); assert(loss>=0 && loss<=8);
    if(v>=.6 || k==0) assert(loss==0);
  }
  assert(poweredCreepLoss(8,.07,0,75,0)==8);
  assert(poweredCreepLoss(8,.07,.3,75,0)>poweredCreepLoss(8,.07,.5,75,0));
  assert(poweredCreepLoss(8,.07,.3,84,0)<poweredCreepLoss(8,.07,.3,83,0));
  assert(poweredCreepLoss(8,.07,.3,75,0,.3)==0);
  bool rejected=false;try {poweredCreepLoss(16,.07,.2,75,0);} catch(const std::runtime_error&){rejected=true;} assert(rejected);
}''')
    header=ROOT/'simulator/variants/r5_creep_20261122/Plugins/AirSim/Source/Vehicles/Car'
    exe=tmp_path/'check'
    subprocess.run(['g++','-std=c++14','-I',str(header),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
