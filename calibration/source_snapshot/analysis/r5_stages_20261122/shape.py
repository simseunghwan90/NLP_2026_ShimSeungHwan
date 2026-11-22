"""Secondary path shape diagnostics, retaining initial alignment and full rollout metrics."""
import argparse
import json
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from common import OUT


def path(x, y, heading):
    xy = np.column_stack([x, y]).astype(float)
    arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    keep = np.r_[True, np.diff(arc) > 1e-9]
    return arc[keep], xy[keep], np.unwrap(np.asarray(heading))[keep]


def sample(arc, xy, target):
    return np.column_stack([np.interp(target, arc, xy[:, i]) for i in range(2)])


def compare(q):
    quality = q.valid.to_numpy(dtype=bool) if 'valid' in q else np.ones(len(q), dtype=bool)
    counts = dict(valid_count=int(quality.sum()), excluded_observation_count=int((~quality).sum()))
    q = q.loc[quality]
    if len(q) < 2:
        return dict(shape_available=False, **counts)
    oa, op, oh = path(q.observed_x, q.observed_y, q.observed_heading)
    na, np_, nh = path(q.native_x, q.native_y, q.native_heading)
    if min(oa[-1], na[-1]) < .1:
        return dict(shape_available=False, observed_path_length_m=float(oa[-1]), native_path_length_m=float(na[-1]), **counts)
    # Spatially uniform nodes avoid making a long stationary dwell dominate shape.
    os = sample(oa, op, np.linspace(0, oa[-1], max(2, int(np.ceil(oa[-1] / .5)) + 1)))
    ns = sample(na, np_, np.linspace(0, na[-1], max(2, int(np.ceil(na[-1] / .5)) + 1)))
    on = cKDTree(ns).query(os)[0]
    no = cKDTree(os).query(ns)[0]
    progress = np.linspace(0, 1, 1001)
    ordered = np.linalg.norm(sample(oa, op, progress * oa[-1]) - sample(na, np_, progress * na[-1]), axis=1)
    ohp = np.interp(progress * oa[-1], oa, oh) - oh[0]
    nhp = np.interp(progress * na[-1], na, nh) - nh[0]
    return dict(shape_available=True, **counts,
                observed_path_length_m=float(oa[-1]), native_path_length_m=float(na[-1]),
                path_length_ratio=float(na[-1] / oa[-1]),
                nearest_path_rms_m=float(np.sqrt((np.mean(on**2) + np.mean(no**2)) / 2)),
                observed_to_native_path_p95_m=float(np.percentile(on, 95)),
                native_to_observed_path_p95_m=float(np.percentile(no, 95)),
                observed_path_within_1m_fraction=float(np.mean(on <= 1)),
                ordered_progress_position_rmse_m=float(np.sqrt(np.mean(ordered**2))),
                ordered_progress_heading_rmse_deg=float(np.degrees(np.sqrt(np.mean((nhp-ohp)**2)))),
                observed_speed_integral_m=float(np.trapz(abs(q.observed_v), q.relative_s)),
                native_speed_integral_m=float(np.trapz(abs(q.native_v), q.relative_s)))


def main(labels):
    metrics = pd.read_csv(OUT / 'metrics.csv')
    rows = []
    for r in metrics[metrics.label.isin(labels)].itertuples():
        if r.session.startswith(('LAT1', 'SELFCHECK')):
            continue
        q = pd.read_csv(OUT / 'comparisons' / (r.label + '_' + r.session + '.csv'))
        row = dict(label=r.label, session=r.session, endpoint_m=r.endpoint_m,
                   position_rmse_m=r.position_rmse_m, turn_error=r.turn_error,
                   observed_turns=r.observed_turns, native_turns=r.native_turns,
                   moving_speed_rmse_mps=r.moving_speed_rmse_mps, **compare(q))
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / 'shape_metrics.csv', index=False)
    (OUT / 'shape_metrics.json').write_text(json.dumps(rows, indent=2, allow_nan=False) + '\n')
    print(frame[['label', 'session', 'endpoint_m', 'nearest_path_rms_m', 'ordered_progress_position_rmse_m', 'turn_error']].round(3).to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('labels', nargs='+')
    main(parser.parse_args().labels)
