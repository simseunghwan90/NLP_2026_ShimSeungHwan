"""Build Appendix E from frozen CSVs; retain the approved A-D and F prose."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ['LAT3_Apos_s1', 'LAT3_Apos_s2', 'LAT3_Aneg_s1', 'LAT5_L_s1',
         'LON5_Aneg_v50_s1', 'MOVE_LAT3_Apos_s1', 'MOVE_LAT3_Apos_s2']
NAMES = ['LAT3 A+ s1', 'LAT3 A+ s2', 'LAT3 A- s1', 'LAT5 L s1',
         'LON5 A- 50 s1', 'MOVE LAT3 A+ s1', 'MOVE LAT3 A+ s2']


def read_csv(name):
    with (ROOT / 'evidence' / name).open(newline='') as source:
        return list(csv.DictReader(source))


def tex_name(name):
    return name.replace('+', r'$+$').replace('-', r'$-$')


def make_table(rows, key, names, caption, label, path):
    lines = [r'\begin{center}', r'\small', r'\setlength{\tabcolsep}{5pt}',
             r'\begin{tabular}{@{}llrrrr@{}}', r'\toprule',
             r'Test & Model & \shortstack{Speed RMSE\\(m/s)} & \shortstack{Position RMSE\\(m)} & \shortstack{Endpoint Error\\(m)} & \shortstack{Turn Error\\(rev)} \\',
             r'\midrule']
    previous = None
    for row in rows:
        group = row[key]
        if previous is not None and group != previous:
            lines.append(r'\addlinespace[2pt]')
        name = tex_name(names.get(group, group)) if group != previous else ''
        flagged = (row['contact_flags'] == 'True' if 'contact_flags' in row
                   else row['replay_status'] != 'PASS')
        model = row['model'] + (r'$^{*}$' if flagged else '')
        cells = [f"{float(row[k]):.{digits}f}" for k, digits in
                 [('speed_rmse_mps', 3), ('position_rmse_m', 2),
                  ('endpoint_m', 2), ('turn_error', 3)]]
        lines.append(' & '.join([name, model] + cells) + r' \\')
        previous = group
    lines += [r'\bottomrule', r'\end{tabular}',
              r'\captionof{table}{' + caption + '}',
              r'\label{' + label + '}', r'\end{center}']
    (ROOT / path).write_text('\n'.join(lines) + '\n')


def main():
    grouped = read_csv('table2_metrics.csv')
    individual = read_csv('metrics_all_windows.csv')
    lat3 = [r for r in individual if r['case'].startswith('LAT3_')]
    assert len(grouped) == 20 and len(individual) == 28 and len(lat3) == 12
    make_table(grouped, 'group', {
        'LAT3 (3-window mean)': 'LAT3 (mean)',
        'MOVE LAT3 A+ s1': 'MOVE s1', 'MOVE LAT3 A+ s2': 'MOVE s2'},
        r'Four-stage vehicle-model comparison. Lower values indicate smaller errors. LAT3 values are equal-weight means across three replay windows. $^{*}$Initial-model rollouts that completed but failed wheel-contact validation. Ground-refined corresponds to \texttt{trial03}. All evaluations use development data rather than independent held-out measurements.',
        'tab:additional_summary', 'appendix_summary_table.tex')
    make_table(lat3, 'case', dict(zip(CASES, NAMES)),
        r'Individual LAT3 replay-window errors. Together with the LAT5, LON5, and MOVE rows in Table~\ref{tab:additional_summary}, these rows report all seven replay windows for all four models.',
        'tab:additional_lat3', 'appendix_lat3_table.tex')
    lines = [r'\renewcommand{\thetable}{E\arabic{table}}',
             r'\renewcommand{\theHtable}{appendixE.\arabic{table}}',
             r'\setcounter{table}{0}',
             r'\renewcommand{\thefigure}{E\arabic{figure}}',
             r'\renewcommand{\theHfigure}{appendixE.\arabic{figure}}',
             r'\setcounter{figure}{0}',
             r'\twocolumn[{\begin{minipage}{\textwidth}',
             r'\section{Additional Results}', r'\label{app:replay_results}',
             r'Table~\ref{tab:additional_summary} reports the errors of four vehicle-model configurations across representative development replay windows. All configurations were evaluated using identical recorded control inputs and corresponding GNSS/INS measurements. Table~\ref{tab:additional_lat3} expands the LAT3 mean into individual windows. Turn Error is the absolute difference between simulated and measured signed accumulated rotations, expressed in revolutions.',
             r'\input{appendix_summary_table}', r'\input{appendix_lat3_table}',
             r'\end{minipage}}]']
    for part in (CASES[:3], CASES[3:5], CASES[5:]):
        lines += [r'\clearpage', r'\twocolumn[{\begin{minipage}{\textwidth}']
        for case in part:
            kind = 'accumulated signed rotations' if case.startswith(('LAT5', 'MOVE')) else 'speed'
            name = tex_name(NAMES[CASES.index(case)])
            cap = f'{name}: trajectory and {kind} for all four models and GNSS/INS. '
            if case.startswith('LAT3') or case == 'MOVE_LAT3_Apos_s1':
                cap += 'Insets enlarge the refined-model range. '
            elif case in ('LAT5_L_s1', 'MOVE_LAT3_Apos_s2'):
                cap += 'The inset enlarges the refined-model rotation range. '
            if case.startswith(('LAT5', 'MOVE')):
                cap += 'The Initial-model rollout failed wheel-contact validation.'
            lines += [r'\begin{center}',
                      r'\includegraphics[width=\textwidth]{figures/additional_' + case + '.pdf}',
                      r'\captionof{figure}{' + cap.rstrip() + '}',
                      r'\label{fig:additional_' + case + '}', r'\end{center}']
        if part == CASES[5:]:
            lines.append(r'\input{availability}')
        lines.append(r'\end{minipage}}]')
    (ROOT / 'appendix_results.tex').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
