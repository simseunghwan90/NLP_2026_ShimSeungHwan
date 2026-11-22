"""Explain a candidate using only four declared fit circles; not a native result."""
import json
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from setup import ROOT, OUT

def main():
    fit_names=json.loads((OUT/'design.json').read_text())['fit']
    s=pd.read_csv(OUT/'steady_samples.csv')
    s=s[(s.label=='T0')&s.session.isin(fit_names)].copy()
    if set(s.session)!=set(fit_names):raise ValueError('Missing fit circles')
    s['bin']=np.floor(s.relative_s).astype(int)
    s=s.groupby(['session','bin']).mean(numeric_only=True).reset_index()
    d=json.loads((ROOT/'models/candidates/drive_field_2026-11-21_trial03.json').read_text())
    mp=np.array(d['pedal_map']);curve=np.array(d['torque_curve'])
    def features(v,k,acc):
        throttle=np.interp(acc,mp[:,0],mp[:,1])
        rpm=v/.285*9.23*60/(2*np.pi)
        force=np.interp(rpm,curve[:,0],curve[:,1])*throttle*9.23/.285
        return np.array([force,np.ones(len(v)),v,v*v,v**4*k*k]).T
    weights=(1/np.sqrt(s.groupby('session').session.transform('size'))).to_numpy()
    a=features(s.native_v,s.native_k,s.acc_pct)
    result=lsq_linear(a*weights[:,None],s.native_a*weights,bounds=([.001,-1,-1,-1,-10],[.003,0,0,0,0]))
    predicted=features(s.observed_v,s.observed_k,s.acc_pct)@result.x
    residual=s.observed_a-predicted
    b=np.array([np.ones(len(s)),s.observed_k**2]).T
    beta=np.linalg.lstsq(b*weights[:,None],residual*weights,rcond=None)[0]
    report=dict(fit_sessions=fit_names,one_second_bins=len(s),native_coefficients=result.x.tolist(),
                surrogate_native_acceleration_rmse_mps2=float(np.sqrt(np.mean((a@result.x-s.native_a)**2))),
                residual_acceleration_coefficients=beta.tolist(),
                proposed_powered_residual_offset_nm=float(-beta[0]*.285/(2*result.x[0])),
                proposed_powered_curvature_loss_nm_m2=float(-beta[1]*.285/(2*result.x[0])),
                limitation='Approximate effective response sensitivity; no independently identified mass, wheel torque, hardware drag or validation result')
    (OUT/'force_fit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
