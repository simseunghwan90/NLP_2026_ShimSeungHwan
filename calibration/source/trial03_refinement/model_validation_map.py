"""Additional map guard for the isolated second refinement project."""
import json
import math
from model_validation import validate_model as validate_previous
from setup import digest

def validate_model(model):
    validate_previous({k:v for k,v in model.items() if k!='powered_loss_map'})
    if 'powered_loss_map' not in model:return
    if model.get('powered_residual_offset_nm',0) or model.get('powered_curvature_loss_nm_m2',0):
        raise ValueError('Choose quadratic loss or loss map, not both')
    table=model['powered_loss_map']
    if not isinstance(table,list) or not 2<=len(table)<=12:raise ValueError('Invalid loss map length')
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
