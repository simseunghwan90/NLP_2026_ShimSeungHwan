"""Propose three pedal knots from R5's fixed LON2 acceleration residual only."""
import json
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.optimize import lsq_linear
from common import ROOT, OUT, PREVIOUS, save
from candidate import make


def main():
    old=pd.read_csv(PREVIOUS/'metrics.csv')
    row=old[(old.label=='R5') & (old.session=='LON2_Aneg_s1')].iloc[0]
    native=pd.read_csv(ROOT/row.folder/'vehicle_telemetry.csv')
    q=pd.read_csv(PREVIOUS/'comparisons/R5_LON2_Aneg_s1.csv')
    t=native.t_s.to_numpy()-3
    drive=json.loads((ROOT/'models/candidates/drive_trial03_refine_2026-11-21_R5.json').read_text())
    curve=np.asarray(drive['torque_curve']);torque=np.interp(native.engine_rpm,curve[:,0],curve[:,1])
    # Inherited effective body mass and drive ratio: proposal sensitivity, not identified force.
    gain=torque*9.23/(550*.285)
    knots=np.array([83,85,90,95,100])
    kernels=[]
    for index in [1,2,3]:
        values=np.zeros(5);values[index]=1
        weight=np.interp(native.acc_pct,knots,values,left=0,right=0)
        sensitivity=cumulative_trapezoid(weight*gain*(native.brake_pct.to_numpy()==0),t,initial=0)
        kernels.append(np.interp(q.relative_s,t,sensitivity))
    matrix=np.column_stack(kernels)
    mask=q.valid & q.powered & (q.observed_v>.1)
    fit=lsq_linear(matrix[mask],(q.observed_v-q.native_v)[mask],bounds=([0,0,-.025],[.075,.055,.035]))
    table=np.asarray(drive['pedal_map']);base=np.interp([85,90,95],table[:,0],table[:,1]);proposed=base+fit.x
    for x,y in zip([85,90,95],proposed):table[table[:,0]==x,1]=y
    assert np.all(np.diff(table[:,1])>=0)
    diagnostic=dict(fit_case='LON2_Aneg_s1',reference='R5',method='Integrated local force sensitivity at native speed; proposal only, requires native replay',
                    base=base.tolist(),proposed=proposed.tolist(),delta=fit.x.tolist(),
                    powered_moving_rmse_before=float(np.sqrt(np.mean((q.native_v[mask]-q.observed_v[mask])**2))),
                    surrogate_rmse=float(np.sqrt(np.mean((q.native_v[mask]+matrix[mask]@fit.x-q.observed_v[mask])**2))),
                    fixed='<=83% and100%, torque curve, braking, coast, mass, COM, steering and timing')
    save(OUT/'stage4_proposal.json',diagnostic)
    make('S4A','P0',4,'The 85/90/95% pedal map underpredicts LON2 ramp speed; adjust only those three knots while preserving circle and full-pedal regions.',
         drive_patch={'pedal_map':table.tolist()},extra=dict(diagnostic=diagnostic,fit=['LON2_Aneg_s1'],checks=['LON2_Apos_s1','LAT3_Apos_s1','LON5_Aneg_v50_s1','LONK_Apos_v30_s1','LONK_Aneg_v30_s1'],full_regression='all28 before cumulative selection'))
    print(json.dumps(diagnostic,indent=2))


if __name__=='__main__':main()
