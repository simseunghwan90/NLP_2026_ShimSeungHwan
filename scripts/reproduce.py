"""Rebuild existing HW2 tables/figures using only the exported publication files.

This adapter restores historical relative paths in a disposable directory. It runs
the preserved table/figure code without invoking simulators or fitting models.
"""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile

CODE = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def inside(base, relative):
    p = (base / relative).resolve()
    if not p.is_relative_to(base.resolve()):
        raise ValueError('Path outside selected package: ' + relative)
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('results/hw2'))
    args = parser.parse_args()
    dataset, output = args.dataset.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory must be absent or empty; use a new output path.')
    manifest = json.loads((dataset / 'manifest.json').read_text())
    restored = 0
    with tempfile.TemporaryDirectory(prefix='a1-hw2-reproduction-') as temp:
        workspace = Path(temp)
        os.environ['MPLCONFIGDIR'] = str(workspace / 'matplotlib-cache')
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        for name in ['analysis', 'models']:
            shutil.copytree(CODE / name, workspace / name, ignore=shutil.ignore_patterns('__pycache__'))
        for entry in manifest['files']:
            if not entry['workspace_paths']:
                continue
            source = inside(dataset, entry['path'])
            if sha(source) != entry['sha256']:
                raise ValueError('Dataset hash mismatch: ' + entry['path'])
            for relative in entry['workspace_paths']:
                target = inside(workspace, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if sha(target) != entry['sha256']:
                        raise ValueError('Conflicting historical path: ' + relative)
                else:
                    shutil.copy2(source, target)
                    restored += 1
        (workspace / 'paper').mkdir()
        sys.path.insert(0, str(workspace / 'analysis/hw2_experiments_20261122'))
        publication = importlib.import_module('publish')
        publication.DEST.mkdir()
        data, metrics = publication.build_data.main()
        publication.figures(data)
        publication.tables(metrics)
        for name in ['metrics.csv', 'figure_sources.json', 'costs.json', 'windows.json']:
            shutil.copy2(publication.build_data.OUT / 'comparison' / name, publication.DEST / name)
        import pandas as pd
        checks = {}
        for name in ['metrics.csv', 'grouped_metrics.csv', 'inventory.csv']:
            actual = pd.read_csv(publication.DEST / name)
            expected = pd.read_csv(CODE / 'expected' / name)
            pd.testing.assert_frame_equal(actual, expected, check_exact=False, rtol=0, atol=1e-9)
            checks[name] = 'matches archived values (absolute tolerance 1e-9)'
        for name in ['results_table.tex', 'inventory_table.tex', 'complete_table.tex', 'numeric_macros.tex']:
            if (publication.DEST / name).read_bytes() != (CODE / 'expected' / name).read_bytes():
                raise AssertionError('Table text differs: ' + name)
            checks[name] = 'byte-identical to archived table'
        if json.loads((publication.DEST / 'costs.json').read_text()) != json.loads((CODE / 'expected/costs.json').read_text()):
            raise AssertionError('Cost catalog summary differs')
        checks['costs.json'] = 'matches archived catalog summary'
        report = dict(status='PASS', cases=int(metrics.case.nunique()), rows=len(metrics),
                      replay_statuses=metrics.replay_status.value_counts().to_dict(),
                      restored_historical_paths=restored, checks=checks,
                      scope='Archived-output table and figure reconstruction only. No new simulation, model fitting, or raw-CAN decoding.',
                      execution_environment=dict(python=sys.version.split()[0], numpy=publication.np.__version__,
                                                 pandas=pd.__version__, matplotlib=publication.matplotlib.__version__))
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(publication.DEST, output, dirs_exist_ok=True)
        (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        print('Output:', output)


if __name__ == '__main__':
    main()
