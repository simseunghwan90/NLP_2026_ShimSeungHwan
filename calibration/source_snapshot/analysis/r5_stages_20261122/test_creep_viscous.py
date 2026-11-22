import json
import subprocess
import pytest
from common import ROOT
from model_validation_map import validate_model

@pytest.mark.parametrize('rise,zero',[(-.1,.6),(.01,.6),(.6,.8),(.3,.2),(True,.6),(float('nan'),.6)])
def test_reject_invalid_creep_rising_branch(rise,zero):
    model=json.loads((ROOT/'models/candidates/drive_r5_stages_2026-11-22_S8D.json').read_text())
    model.update(powered_creep_rise_speed_mps=rise,powered_creep_speed_zero_mps=zero)
    with pytest.raises(ValueError):validate_model(model)

def test_legacy_equality_and_stable_low_speed_branch(tmp_path):
    old=ROOT/'simulator/variants/r5_creep_20261122/Plugins/AirSim/Source/Vehicles/Car/PoweredCreep.h'
    new=ROOT/'simulator/variants/r5_creep_viscous_20261122/Plugins/AirSim/Source/Vehicles/Car/PoweredCreep.h'
    code='#define poweredCreepLoss legacyLoss\n#include "'+str(old)+'"\n#undef poweredCreepLoss\n#include "'+str(new)+'"\n'
    code+='''#include <cassert>
int main(){
 for(double a : {0.,8.}) for(double k : {0.,.03,.08}) for(double v : {0.,.1,.3,.6}) for(double acc : {0.,74.,84.,100.}) for(double brake : {0.,1.})
   assert(poweredCreepLoss(a,k,v,acc,brake,.6,0)==legacyLoss(a,k,v,acc,brake,.6));
 assert(poweredCreepLoss(9.5,.08,0,74,0,.6,.3)==0);
 assert(poweredCreepLoss(9.5,.08,.1,74,0,.6,.3)>0);
 assert(poweredCreepLoss(9.5,.08,.2,74,0,.6,.3)>poweredCreepLoss(9.5,.08,.1,74,0,.6,.3));
 assert(poweredCreepLoss(9.5,.08,.6,74,0,.6,.3)==0);
 assert(poweredCreepLoss(9.5,.08,.2,100,0,.6,.3)==0);
 assert(poweredCreepLoss(9.5,.08,.2,74,1,.6,.3)==0);
 bool bad=false;try{poweredCreepLoss(9.5,.08,.2,74,0,.2,.3);}catch(const std::runtime_error&){bad=true;}assert(bad);
}'''
    source=tmp_path/'check.cpp';source.write_text(code);exe=tmp_path/'check'
    subprocess.run(['g++','-std=c++14',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
