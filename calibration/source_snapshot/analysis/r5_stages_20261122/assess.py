"""Fixed relative and absolute regressions against immediate and frozen parents."""
import argparse
import json
import pandas as pd
from common import OUT


def compare(label, parent='R5'):
    data=pd.read_csv(OUT/'metrics.csv').set_index(['label','session'])
    output=[]
    for session,new in data.loc[label].iterrows():
        references={}
        for reference in dict.fromkeys([parent,'R5']):
            if (reference,session) not in data.index:continue
            base=data.loc[(reference,session)];flags=[]
            if session.startswith(('LAT1','SELFCHECK')):
                if new.steering_rmse_deg-base.steering_rmse_deg>max(.2,.1*base.steering_rmse_deg):flags.append('stationary_steering')
                from common import ROOT
                result=json.loads((ROOT/new.folder/'result.json').read_text())
                if result['speed']['native_peak_mps']>.05:flags.append('stationary_motion')
            if new.moving_speed_rmse_mps-base.moving_speed_rmse_mps > max(.05,.1*base.moving_speed_rmse_mps):flags.append('speed')
            for key in ['endpoint_m','position_rmse_m']:
                if new[key]-base[key]>max(1,.1*base[key]):flags.append(key)
                if new[key]-base[key]>=10:flags.append(key+'_added_10m')
            if session.startswith(('LAT4','LAT5','MOVE','LAT6')):
                if new.turn_error-base.turn_error>.1:flags.append('added_turn_error')
                if session.startswith(('LAT4','LAT5')) and new.turn_error>.1:flags.append('circle_absolute_turn_target')
            elif session.startswith(('LAT3','LON')):
                for key in ['heading_endpoint_deg','moving_heading_rmse_deg']:
                    if new[key]-base[key]>2:flags.append(key)
            if session.startswith(('LON5','LONK')):
                key='moving_yaw_rate_rmse_deg_s'
                if new[key]-base[key]>max(.2,.1*base[key]):flags.append('yaw_rate')
            references[reference]=dict(flags=flags)
        output.append(dict(session=session,references=references))
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--parent',default='R5');a=p.parse_args()
    report=compare(a.label,a.parent)
    (OUT/('assessment_'+a.label+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    for row in report:
        flags={k:v['flags'] for k,v in row['references'].items() if v['flags']}
        print(row['session'],flags or 'PASS regression gates')
