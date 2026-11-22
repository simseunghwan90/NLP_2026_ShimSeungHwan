"""Report fixed development gates without silently promoting candidates."""
import argparse
import json
import pandas as pd
from setup import OUT

def number(value):
    return None if pd.isna(value) else float(value)

def compare(label):
    d=pd.read_csv(OUT/'metrics.csv').set_index(['label','session'])
    rows=[]
    for name in d.loc[label].index:
        if ('T0',name) not in d.index:continue
        a=d.loc[('T0',name)];b=d.loc[(label,name)]
        flags=[]
        if b.moving_speed_rmse_mps-a.moving_speed_rmse_mps>max(.05,.1*a.moving_speed_rmse_mps):flags.append('speed')
        for key in ['endpoint_m','position_rmse_m']:
            added=b[key]-a[key]
            if added>max(1,.1*a[key]):flags.append(key)
            if added>=10:flags.append(key+'_added_10m')
        if name.startswith(('LAT4','LAT5')):
            if b.turn_error-a.turn_error>.1:flags.append('added_turn_error')
        elif name.startswith(('LAT3','LON')):
            for key in ['heading_endpoint_deg','moving_heading_rmse_deg']:
                if b[key]-a[key]>2:flags.append(key)
        rows.append(dict(session=name,flags=flags,absolute_turn_target_met=bool(b.turn_error<=.1),
            moving_speed_before=number(a.moving_speed_rmse_mps),moving_speed_after=number(b.moving_speed_rmse_mps),
            endpoint_before=float(a.endpoint_m),endpoint_after=float(b.endpoint_m),
            position_before=float(a.position_rmse_m),position_after=float(b.position_rmse_m),
            turn_error_before=float(a.turn_error),turn_error_after=float(b.turn_error)))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args()
    rows=compare(a.label)
    path=OUT/('assessment_'+a.label+'.json')
    path.write_text(json.dumps(dict(label=a.label,policy='design.json; flags unchanged; no automatic promotion',cases=rows),indent=2)+'\n')
    for r in rows:
        print(r['session'],','.join(r['flags']) or 'PASS gates',
              'v %.3f -> %.3f; end %.2f -> %.2f; turns %.3f -> %.3f'%tuple(r[k] if r[k] is not None else float('nan') for k in ['moving_speed_before','moving_speed_after','endpoint_before','endpoint_after','turn_error_before','turn_error_after']))

if __name__=='__main__':main()
