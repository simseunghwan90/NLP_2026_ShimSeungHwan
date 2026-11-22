import subprocess
from setup import ROOT

def test_native_loss_preserves_coast_brake_and_direction(tmp_path):
    source=tmp_path/'check.cpp'
    source.write_text('''#include "PoweredLoss.h"
#include <cassert>
int main() {
  assert(poweredResidual(8.4, 0, 0, .1, true)==8.4);
  assert(poweredResidual(8.4, -2.24, 349.2, .1, false)==8.4);
  assert(std::abs(poweredResidual(8.4, -2.24, 349.2, .1, true)-9.652)<1e-12);
  assert(poweredResidual(8.4,-2.24,349.2,.1,true)==poweredResidual(8.4,-2.24,349.2,-.1,true));
  assert(poweredResidual(8.4,-20,0,0,true)==0);
  bool rejected=false; try { poweredResidual(8.4,0,-1,.1,true); } catch(...) { rejected=true; }
  assert(rejected);
}''')
    header=ROOT/'simulator/variants/refine_20261121/Plugins/AirSim/Source/Vehicles/Car'
    exe=tmp_path/'check'
    subprocess.run(['g++','-std=c++14','-I',str(header),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
