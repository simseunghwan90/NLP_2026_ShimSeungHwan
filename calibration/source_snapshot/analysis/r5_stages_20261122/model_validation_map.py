"""Additional map guard for the isolated second refinement project."""
import json
import math
from model_validation import validate_model as validate_previous
from common import digest

def validate_model(model):
    validate_previous({k:v for k,v in model.items() if k not in {'powered_loss_map','powered_creep_resistance_nm','powered_creep_speed_zero_mps','powered_creep_rise_speed_mps'}})
    amplitude=model.get('powered_creep_resistance_nm',0)
    if isinstance(amplitude,bool) or not isinstance(amplitude,(int,float)) or not math.isfinite(amplitude) or not 0<=amplitude<=15:
        raise ValueError('Invalid powered creep resistance')
    speed=model.get('powered_creep_speed_zero_mps',.6)
    if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .2<=speed<=.8:
        raise ValueError('Invalid powered creep fade speed')
    rise=model.get('powered_creep_rise_speed_mps',0)
    if isinstance(rise,bool) or not isinstance(rise,(int,float)) or not math.isfinite(rise) or (rise!=0 and (not .05<=rise<=.5 or rise>=speed)):
        raise ValueError('Invalid powered creep rise speed')
    if 'powered_loss_map' not in model:return
    if model.get('powered_residual_offset_nm',0) or model.get('powered_curvature_loss_nm_m2',0):
        raise ValueError('Choose quadratic loss or loss map, not both')
    table=model['powered_loss_map']
    if not isinstance(table,list) or not 2<=len(table)<=16:raise ValueError('Invalid loss map length')
    previous=-1
    for point in table:
        if not isinstance(point,list) or len(point)!=2:raise ValueError('Invalid loss knot')
        x,y=point
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):
            raise ValueError('Nonfinite loss knot')
        if not previous<x<=.15 or x<0 or not 0<=y<=20:raise ValueError('Out of range loss knot')
        previous=x
    if table[0][0]!=0 or table[-1][0]<.1:raise ValueError('Incomplete loss coverage')

def live_config(model_path,output):
    path=model_path.resolve();model=json.loads(path.read_text());validate_model(model)
    return dict(model,model_sha256=digest(path),model_source=str(path),lift=False,
        telemetry_path=str(output/'vehicle_telemetry.csv'),resolved_path=str(output/'vehicle_resolved.json'),
        input_boundary='Unchanged CAN input; native state only; effective powered loss map')
