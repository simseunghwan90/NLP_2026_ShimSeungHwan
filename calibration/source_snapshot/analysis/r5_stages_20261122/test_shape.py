import numpy as np
import pandas as pd
from shape import compare


def trajectory(observed, native, oh=None, nh=None):
    t = np.linspace(0, 10, len(observed))
    return pd.DataFrame(dict(relative_s=t, observed_x=observed[:, 0], observed_y=observed[:, 1],
                             native_x=native[:, 0], native_y=native[:, 1],
                             observed_heading=np.zeros(len(t)) if oh is None else oh,
                             native_heading=np.zeros(len(t)) if nh is None else nh,
                             observed_v=np.ones(len(t)), native_v=np.ones(len(t))))


def test_speed_progression_is_separate_from_shape():
    u = np.linspace(0, 1, 1001)
    a = np.column_stack((10*u, np.zeros_like(u)))
    b = np.column_stack((10*u*u, np.zeros_like(u)))
    r = compare(trajectory(a, b))
    assert np.sqrt(np.mean(np.sum((a-b)**2, axis=1))) > 1
    assert r['ordered_progress_position_rmse_m'] < 1e-8


def test_extra_lap_cannot_hide_behind_nearest_path_metric():
    u = np.linspace(0, 2*np.pi, 2001)
    a = np.column_stack((10*(np.cos(u)-1), 10*np.sin(u)))
    b = np.column_stack((10*(np.cos(2*u)-1), 10*np.sin(2*u)))
    r = compare(trajectory(a, b, u, 2*u))
    assert r['nearest_path_rms_m'] < .3
    assert r['ordered_progress_position_rmse_m'] > 10
    assert r['ordered_progress_heading_rmse_deg'] > 200
    assert abs(r['path_length_ratio']-2) < .001


def test_translation_is_not_fitted_away():
    u = np.linspace(0, 1, 101)
    a = np.column_stack((10*u, np.zeros_like(u)))
    b = a + [0, 10]
    r = compare(trajectory(a, b))
    assert abs(r['nearest_path_rms_m']-10) < 1e-8
    assert abs(r['ordered_progress_position_rmse_m']-10) < 1e-8


def test_only_observation_quality_excludes_corrupt_position():
    u = np.linspace(0, 1, 101)
    a = np.column_stack((10*u, np.zeros_like(u)))
    q = trajectory(a, a.copy())
    q['valid'] = True
    q.loc[50, 'observed_y'] = 1000
    q.loc[50, 'valid'] = False
    r = compare(q)
    assert r['excluded_observation_count'] == 1
    assert r['ordered_progress_position_rmse_m'] < 1e-8
    q.loc[50, 'valid'] = True
    assert compare(q)['ordered_progress_position_rmse_m'] > 100
