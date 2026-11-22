"""Validate only the additional effective-loss options, preserving old guards."""
import importlib.util
import json
import math
from common import ROOT, digest

spec=importlib.util.spec_from_file_location('refine_original_validation',ROOT/'analysis/lift_20261114/replay.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
EXTRA={'powered_residual_offset_nm','powered_curvature_loss_nm_m2'}

def validate_model(model):
    original.validate_model({k:v for k,v in model.items() if k not in EXTRA})
    for k in EXTRA:
        x=model.get(k,0)
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('Invalid '+k)
    if not -model.get('rear_residual_torque_nm',0)<=model.get('powered_residual_offset_nm',0)<=10:
        raise ValueError('Powered loss offset outside declared range')
    if not 0<=model.get('powered_curvature_loss_nm_m2',0)<=1000:
        raise ValueError('Powered curvature loss outside declared range')

def live_config(model_path,output):
    path=model_path.resolve();model=json.loads(path.read_text());validate_model(model)
    return dict(model,model_sha256=digest(path),model_source=str(path),lift=False,
        telemetry_path=str(output/'vehicle_telemetry.csv'),resolved_path=str(output/'vehicle_resolved.json'),
        input_boundary='Unchanged CAN acceleration percentage; effective powered loss applied only in native plant')
