"""Propose one intermediate-curvature resistance knot using one MOVE case."""
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from common import ROOT,OUT,save

def main():
    save(OUT/'stage8_fit_design.json',dict(hypothesis='MOVE repeatedly uses curvature between the R5 circle knots; existing interpolation underestimates effective powered loss there.',
         fit='MOVE_LAT2_2_s1, entire valid powered moving record',check='Remaining five MOVE records and all eight circles',
         change='One additional curvature knot at0.0715/m, delta0..2Nm per rear wheel; preserve all old knots',
         limitation='Effective empirical resistance, not an identified mechanical cause; no session flag or measured-state input',
         model_bounds='Python map capacity12->16 only; native vector supports13; finite/ordered/0..20Nm and0..0.15/m guards retained'))
    metrics=pd.read_csv(OUT/'metrics.csv');row=metrics[(metrics.label=='R5')&(metrics.session=='MOVE_LAT2_2_s1')].iloc[0]
    v=pd.read_csv(ROOT/row.folder/'vehicle_telemetry.csv');q=pd.read_csv(OUT/'comparisons/R5_MOVE_LAT2_2_s1.csv')
    t=v.t_s.to_numpy()-3;base=v.speed_mps.to_numpy();acc=v.acc_pct.to_numpy();brake=v.brake_pct.to_numpy()
    lo,center,hi=.0644220780744,.0715,.0796922227964
    weight=np.interp(v.loss_curvature_per_m,[lo,center,hi],[0,1,0],left=0,right=0)
    weight*=np.clip((85-acc)/2,0,1)*(acc>0)*(brake==0)
    dt=np.diff(t,prepend=t[0]);force=2/(550*.285)
    mask=q.valid&q.powered&(q.observed_v>.1)
    def predict(delta):
        out=np.empty_like(base);dv=0.
        for i in range(len(base)):
            dv-=delta*force*weight[i]*dt[i]
            # Physical nonnegative-speed approximation; observed speed is never injected.
            dv=max(-base[i],dv);out[i]=base[i]+dv
        return np.interp(q.relative_s,t,out)
    opt=minimize_scalar(lambda x:float(np.mean((predict(x)[mask]-q.observed_v[mask])**2)),bounds=(0,2),method='bounded')
    result=dict(method='Native-trajectory force sensitivity with nonnegative speed; proposal only',center=center,delta_nm=float(opt.x),
                base_rmse=float(np.sqrt(np.mean((q.native_v[mask]-q.observed_v[mask])**2))),surrogate_rmse=float(np.sqrt(opt.fun)))
    save(OUT/'stage8_proposal.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
