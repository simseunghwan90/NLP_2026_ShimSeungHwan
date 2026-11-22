"""Bounded proposal from native force differences; never replaces native validation."""
import ctypes
import json
import subprocess
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar,differential_evolution
from common import ROOT,OUT,save
from candidate import make
from metrics import summarize

def main():
    folder=OUT/'creep_surrogate';folder.mkdir(exist_ok=False)
    source=folder/'kernel.cpp'
    source.write_text('''#include "PoweredCreep.h"
extern "C" void simulate(const double* base,const double* k,const double* acc,const double* brake,const double* dt,int n,double relaxation,double amp,double zero,double* out){
 out[0]=base[0];
 for(int i=1;i<n;i++){
 double force=poweredCreepLoss(amp,k[i-1],out[i-1],acc[i-1],brake[i-1],zero)*2/(550*.285);
 out[i]=std::max(0.0,out[i-1]+base[i]-base[i-1]-relaxation*(out[i-1]-base[i-1])*dt[i]-force*dt[i]);
 }
}''')
    lib=folder/'kernel.so';header=ROOT/'simulator/variants/r5_creep_20261122/Plugins/AirSim/Source/Vehicles/Car'
    command=['g++','-O3','-std=c++14','-shared','-fPIC','-I',str(header),str(source),'-o',str(lib)]
    subprocess.run(command,check=True,capture_output=True);kernel=ctypes.CDLL(str(lib)).simulate
    array=np.ctypeslib.ndpointer(dtype=np.float64,ndim=1,flags='C_CONTIGUOUS')
    kernel.argtypes=[array]*5+[ctypes.c_int]+[ctypes.c_double]*3+[array];kernel.restype=None
    cases={}
    for name in ['MOVE_LAT3_Apos_s2','LAT4_L120_s1','LAT4_L150_s1']:
        paths={}
        for label in ['S7DRIVEFIX','S8D']:
            paths[label]=next((OUT/'native_replays').glob('*'+name+'_'+label+'/result.json'))
            assert json.loads(paths[label].read_text())['status']=='PASS';summarize(paths[label])
        v=pd.read_csv(paths['S7DRIVEFIX'].parent/'vehicle_telemetry.csv');d=pd.read_csv(paths['S8D'].parent/'vehicle_telemetry.csv')
        assert len(v)==len(d)
        data=[np.ascontiguousarray(v[x].to_numpy(dtype=float)) for x in ['speed_mps','loss_curvature_per_m','acc_pct','brake_pct']]
        t=v.t_s.to_numpy();dt=np.ascontiguousarray(np.diff(t,prepend=t[0]));data.append(dt)
        def predict(relaxation,amp,zero):
            out=np.empty(len(v));kernel(*data,len(v),relaxation,amp,zero,out);return out
        opt=minimize_scalar(lambda x:float(np.mean((predict(x,8,.6)-d.speed_mps.to_numpy())**2)),bounds=(0,.2),method='bounded')
        q=pd.read_csv(OUT/'comparisons'/('S7DRIVEFIX_'+name+'.csv'));observed=np.interp(t-3,q.relative_s,q.observed_v,left=0,right=0)
        valid=np.interp(t-3,q.relative_s,q.valid.astype(float),left=0,right=0)>.99
        cases[name]=dict(data=data,t=t,observed=observed,valid=valid,relaxation=float(opt.x),native_fit_rmse=float(np.sqrt(opt.fun)))
    def predict(c,params):
        out=np.empty(len(c['t']));kernel(*c['data'],len(out),c['relaxation'],*params,out);return out
    def objective(params):
        score=0
        for name,c in cases.items():
            pred=predict(c,params);mask=c['valid'];t=c['t']
            if name.startswith('MOVE'):
                e=pred[mask]-c['observed'][mask]
                score+=float(np.mean(e**2)+5*np.mean(e)**2)
            else:
                # Preserve circle distance to avoid trading creep fit for missing revolutions.
                distance=float(np.trapz(pred-c['data'][0],t))
                score+=.02*max(0,abs(distance)-.5)**2
        return score
    opt=differential_evolution(objective,[(3,8),(.2,.6)],seed=20261122,maxiter=60,popsize=10,tol=1e-7,polish=False)
    params=[float(x) for x in opt.x]
    report=dict(build_command=command,optimizer_success=bool(opt.success),params={'powered_creep_resistance_nm':params[0],'powered_creep_speed_zero_mps':params[1]},
                cases={n:{'relaxation_per_s':c['relaxation'],'native8Nm_fit_rmse_mps':c['native_fit_rmse'],
                          'proposal_distance_change_m':float(np.trapz(predict(c,params)-c['data'][0],c['t'])),
                          'proposal_speed_rmse_mps':float(np.sqrt(np.mean((predict(c,params)[c['valid']]-c['observed'][c['valid']])**2)))} for n,c in cases.items()},
                limitation='Local time-dependent native-force surrogate only; cannot select model without native fixed-time gates')
    save(folder/'result.json',report)
    make('S8E','S8D',8,'Reduce creep loss amplitude and fade speed using native-to-native sensitivity; preserve circle launch distance while improving slow MOVE.',drive_patch=report['params'],extra=report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
