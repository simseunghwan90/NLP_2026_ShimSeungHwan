"""Freeze each single-mechanism hypothesis before its native replay."""
import copy
import json
from common import ROOT, OUT, PROJECT, digest, save
from model_validation_map import validate_model


def model_path(label):
    return ROOT / f"models/candidates/steering_r5_stages_2026-11-22_{label}.json"


def make(label, parent, stage, hypothesis, drive_patch=None, steering_patch=None, extra=None):
    path = model_path(parent)
    steering = json.loads(path.read_text())
    drive_path = ROOT / steering['base_longitudinal_model']
    assert digest(drive_path) == steering['base_longitudinal_sha256']
    drive = json.loads(drive_path.read_text())
    drive_patch = drive_patch or {}
    steering_patch = steering_patch or {}
    design = dict(stage=stage, label=label, parent=parent, parent_model=str(path.relative_to(ROOT)),
                  parent_sha256=digest(path), hypothesis=hypothesis,
                  drive_changes=drive_patch, steering_changes=steering_patch,
                  input_windows_sha256=digest(OUT/'windows.json'),
                  acceptance='design.json; compare immediate parent and frozen R5; complete rollout, no resets',
                  extra=extra or {})
    save(OUT/(label+'_design.json'), design)
    drive.update(copy.deepcopy(drive_patch))
    drive.update(model_id='DRIVE-R5-STAGES-20261122-'+label,
                 provenance=dict(parent=str(drive_path.relative_to(ROOT)), design=str((OUT/(label+'_design.json')).relative_to(ROOT)), status='experimental'))
    validate_model(drive)
    new_drive=ROOT/f'models/candidates/drive_r5_stages_2026-11-22_{label}.json'
    save(new_drive,drive)
    steering.update(copy.deepcopy(steering_patch))
    steering.update(model_id='STEER-R5-STAGES-20261122-'+label,
                    base_longitudinal_model=str(new_drive.relative_to(ROOT)),base_longitudinal_sha256=digest(new_drive),
                    provenance=dict(parent=str(path.relative_to(ROOT)), design=str((OUT/(label+'_design.json')).relative_to(ROOT)), status='experimental'))
    save(model_path(label),steering)
    return design
