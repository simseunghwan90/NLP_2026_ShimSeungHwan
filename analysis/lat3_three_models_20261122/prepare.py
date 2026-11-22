"""Prepare a read-only-physics, isolated LAT3 comparison; never tune a model."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments/evidence/2026-11-22_lat3_three_models'
SOURCE = ROOT / 'simulator/variants/r5_stages_20261122'
PROJECT = ROOT / 'simulator/variants/lat3_three_models_20261122'
CASES = ['LAT3_Apos_s1', 'LAT3_Apos_s2', 'LAT3_Aneg_s1',
         'MOVE_LAT3_Apos_s1', 'MOVE_LAT3_Apos_s2']


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    OUT.mkdir(exist_ok=False)
    archive = ROOT / 'experiments/baselines/2026-11-10_initial/source_assets.tar'
    expected = json.loads(archive.with_name('baseline.json').read_text())['archive_sha256']
    assert digest(archive) == expected
    audit = dict(archive=str(archive.relative_to(ROOT)), archive_sha256=expected, files=[])
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            relevant = any(m.name.startswith('simulator/' + prefix) for prefix in
                           ['Content/Vehicles/A1/', 'Plugins/AirSim/Content/VehicleAdv/',
                            'Plugins/AirSim/Source/', 'Plugins/AirSim/AirLib/', 'Source/', 'Config/'])
            if not m.isfile() or not relevant:
                continue
            old = t.extractfile(m).read()
            new = SOURCE / m.name.removeprefix('simulator/')
            same = new.is_file() and hashlib.sha256(old).hexdigest() == digest(new)
            allowed = m.name.endswith(('CarPawnSimApi.cpp', 'CarPawnSimApi.h'))
            assert same or allowed, m.name
            audit['files'].append(dict(path=m.name, frozen_sha256=hashlib.sha256(old).hexdigest(),
                                      replay_sha256=digest(new), identical=same))
    audit['adapter_changes'] = 'Only CarPawnSimApi hooks plus optional ResearchReplay/ResearchSteering. Baseline uses empty drive overrides and baseline_passthrough: original engine/wheel/brake/steering smoothing and 3 low-speed substeps remain. Reviewed configure/apply branches.'
    audit['common_environment'] = 'All models use the existing comparison TestPad, not the Nov 10 map archive. Vehicle assets/defaults remain frozen; replay is instrumented, not execution of the historical binary.'
    save(OUT / 'baseline_audit.json', audit)
    shutil.copytree(SOURCE, PROJECT, ignore=shutil.ignore_patterns('local', 'DerivedDataCache', 'Saved', 'Intermediate', '__pycache__'))
    (PROJECT / 'local').mkdir()
    (OUT / 'decoded').symlink_to(ROOT / 'experiments/evidence/2026-11-21_field_followup/decoded', target_is_directory=True)
    windows = json.loads((ROOT / 'experiments/evidence/2026-11-22_r5_stages/windows.json').read_text())
    save(OUT / 'windows.json', {n: windows[n] for n in CASES})
    (OUT / 'models').mkdir()
    drive = ROOT / 'models/candidates/lift_2026-11-14_baseline.json'
    previous = ROOT / 'models/candidates/steering_field_2026-11-20_v2.json'
    base = json.loads(previous.read_text())
    base.update(model_id='INITIAL-20261110-INSTRUMENTED-REPLAY',
                base_longitudinal_model=str(drive.relative_to(ROOT)),
                base_longitudinal_sha256=digest(drive),
                baseline_passthrough=True, handwheel_to_nominal_tire_ratio=7.5,
                native_project=str(PROJECT.relative_to(ROOT)),
                native_binary_sha256=digest(PROJECT / 'Plugins/AirSim/Binaries/Linux/libUE4Editor-AirSim.so'),
                provenance='Frozen initial vehicle defaults; steering dynamics fields are ignored by baseline_passthrough. Linear pedals; no measured corrections.')
    save(OUT / 'models/Baseline.json', base)
    prev = json.loads(previous.read_text())
    prev.update(native_project=str(PROJECT.relative_to(ROOT)), native_binary_sha256=base['native_binary_sha256'])
    save(OUT / 'models/Previous.json', prev)
    save(OUT / 'design.json', dict(
        scope='LAT3 본시험 3개와 MOVE 2개의 동일 입력 비교 그림을 작성한다. 모델 보정은 수행하지 않는다.',
        cases=CASES, models=['Baseline (initial 2026-11-10 vehicle defaults)', 'Previous', 'R6V2'],
        dt_s=.01, preparation_s=3, warmup_s=2, port=41923,
        alignment='Initial rear-axle pose only, fixed receive timestamps, no posthoc fit/state injection.',
        outputs='Full XY trajectories, speed, accumulated heading, endpoint/RMSE/path length; development data, not heldout evaluation.',
        source_previous=str(previous.relative_to(ROOT)), source_previous_sha256=digest(previous),
        previous_variant_changes='Only project path and binary identity metadata; all model parameters unchanged.',
        baseline_qualification=audit['common_environment']))
    old = ROOT / 'analysis/r5_stages_20261122/replay.py'
    text = old.read_text()
    replacements = {
        'from validation import validate_case': "sys_placeholder = None\nfrom validation import validate_case",
        'OUT = ROOT / "experiments/evidence/2026-11-22_r5_stages"': 'OUT = ROOT / "experiments/evidence/2026-11-22_lat3_three_models"',
        'PROJECT = ROOT / "simulator/variants/r5_stages_20261122"': 'PROJECT = ROOT / "simulator/variants/lat3_three_models_20261122"',
        "allowed_projects={PROJECT.resolve(),(ROOT/'simulator/variants/r5_creep_20261122').resolve(),(ROOT/'simulator/variants/r5_creep_viscous_20261122').resolve()}": 'allowed_projects={PROJECT.resolve()}',
        'analysis/r5_stages_20261122/launch.py': 'analysis/lat3_three_models_20261122/launch.py',
        '"41709"': '"41923"',
    }
    for a, b in replacements.items():
        assert text.count(a) == 1, a
        text = text.replace(a, b)
    text = text.replace('sys_placeholder = None', "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'r5_stages_20261122'))")
    (Path(__file__).parent / 'replay.py').write_text(text)
    save(OUT / 'runner_derivation.json', dict(source=str(old.relative_to(ROOT)), sha256=digest(old),
                                             changes='Isolated output/project/port/launcher and import search path only. Same validation/inputs/metrics.'))
    print(OUT, flush=True)


if __name__ == '__main__':
    main()
