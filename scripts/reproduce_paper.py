#!/usr/bin/env python3
"""Render the final four-stage paper results from preserved dataset exports."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('results/paper'))
    args = parser.parse_args()
    dataset, output = args.dataset.resolve(), args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('--output must be a new or empty directory')
    manifest = json.loads((ROOT / 'paper_results/input_manifest.json').read_text())
    inputs = []
    for entry in manifest['files']:
        relative = Path(entry['path'])
        target = relative.relative_to('four_stage_comparison')
        source = (dataset / relative).resolve()
        if not source.is_relative_to(dataset) or '..' in target.parts:
            raise ValueError(f'Invalid dataset path: {relative}')
        if not source.is_file() or digest(source) != entry['sha256']:
            raise ValueError(f'Missing or changed paper input: {relative}')
        inputs.append((source, target))
    output.mkdir(parents=True, exist_ok=True)
    for source, relative in inputs:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(ROOT / 'analysis/four_stage_20261123', output / 'reproduction',
                    ignore=shutil.ignore_patterns('__pycache__'))
    (output / 'figures').mkdir()
    subprocess.run([sys.executable, str(output / 'reproduction/make_results.py')],
                   cwd=output, check=True)
    tables = ['stage_summary_table.tex', 'all_window_tables.tex',
              'appendix_summary_table.tex', 'appendix_lat3_table.tex']
    for name in tables:
        if (output / name).read_bytes() != (ROOT / 'paper_results' / name).read_bytes():
            raise ValueError(f'Generated table differs from paper: {name}')
    figure_names = [p.name for p in (ROOT / 'paper_results/figures').iterdir()]
    for name in figure_names:
        path = output / 'figures' / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Missing generated figure: {name}')
    validation = json.loads((output / 'evidence/plot_validation.json').read_text())
    report = {
        'status': 'PASS', 'input_hashes_checked': len(inputs),
        'tables_byte_identical': tables, 'figure_files_generated': len(figure_names),
        'plot_validation': validation,
        'scope': 'Render frozen comparison CSVs; no CAN decoding, simulator execution, or fitting.',
    }
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(inputs)} inputs, {len(tables)} matching tables, '
          f'{len(figure_names)} figures. Output: {output}')


if __name__ == '__main__':
    main()
