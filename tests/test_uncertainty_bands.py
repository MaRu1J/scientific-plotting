"""Verify uncertainty geometry, scientific constraints and replay, not styling text."""
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific-plotting' / 'scripts'))
from plot_template import render_plot, render_multipanel, PALETTES


@pytest.fixture(autouse=True)
def cleanup():
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='.*not installed; using.*')
        yield
    plt.close('all')


def draw(data=None, **kwargs):
    return render_plot(data or {'x': [0., 1., 2.], 'y': [1., 2., 3.]},
                       kind=kwargs.pop('kind', 'line'), x='x', y='y', **kwargs)


def band(**kwargs):
    return dict(y=.2, definition='supplied sample SD, n=24', display='band', **kwargs)


def test_asymmetric_geometry_color_order_and_metadata():
    data = {'x': [2., 1., 0.], 'y': [3., 2., 1.]}
    fig, ax, _ = draw(data, palette='soft', error_bars={
        'y_lower': [.1, .2, .3], 'y_upper': [.4, .5, .6],
        'definition': 'supplied asymmetric interval', 'display': 'band'})
    fill, = [c for c in ax.collections if getattr(c, '_scientific_uncertainty_band', False)]
    vertices = fill.get_paths()[0].vertices
    for x, low, high in zip(data['x'], [2.9, 1.8, .7], [3.4, 2.5, 1.6]):
        ys = vertices[vertices[:, 0] == x, 1]
        assert min(ys) == pytest.approx(low)
        assert max(ys) == pytest.approx(high)
    assert list(ax.lines[0].get_xdata()) == data['x']
    assert fill.get_zorder() < ax.lines[0].get_zorder()
    assert fill.get_alpha() == .18
    assert fill.get_facecolor()[0, :3] == pytest.approx(to_rgb(ax.lines[0].get_color()))
    assert ax.get_ylim()[0] < .7 and ax.get_ylim()[1] > 3.4
    assert fig.scientific_metadata['error_bars']['display'] == 'band'
    assert len(ax.lines) == 1  # no whiskers or extra centerline


@pytest.mark.parametrize('xs', ([0, 2, 1], [0, 0, 1], [1]))
def test_refuses_ambiguous_connections_without_sorting(xs):
    with pytest.raises(ValueError, match='strictly monotonic'):
        draw({'x': xs, 'y': [1.] * len(xs)}, error_bars=band())


@pytest.mark.parametrize('kind,extra', [('scatter', {}), ('bar', {}),
    ('line', {'x': .1}), ('line', {'alpha': .8}), ('line', {'alpha': True}),
    ('line', {'capsize': 2})])
def test_refuses_unsupported_band_semantics(kind, extra):
    options = band()
    options.update(extra)
    with pytest.raises(ValueError):
        draw(kind=kind, error_bars=options)


def test_requires_statistic_and_positive_log_bounds():
    with pytest.raises(ValueError, match='definition'):
        draw(error_bars={'y': .1, 'display': 'band'})
    with pytest.raises(ValueError, match='non-positive'):
        draw(yscale='log', error_bars={'y': 1., 'display': 'band', 'definition': 'SD'})


def test_grouped_bands_follow_each_series_and_multipanel_report(tmp_path):
    data = {'x': [0, 1, 2, 0, 1, 2], 'y': [1, 2, 3, 2, 3, 4], 'g': ['A']*3+['B']*3}
    panel = dict(data=data, kind='line', x='x', y='y', group='g', palette='coastal', error_bars=band())
    fig, axes, _ = render_multipanel([panel, panel], size='double', height_mm=120,
                                    output=tmp_path/'panels', report=True)
    for ax in axes:
        assert len([c for c in ax.collections if getattr(c, '_scientific_uncertainty_band', False)]) == 2
    report = json.loads((tmp_path/'panels_review.json').read_text())
    assert [r['display'] for r in report['uncertainty']] == ['band', 'band']


def test_cli_bundle_replays_band_with_supplied_arrays(tmp_path):
    draw(palette='soft', error_bars={**band(), 'y': [.1, .2, .3]}, output=tmp_path/'figure',
         bundle=tmp_path/'bundle', include_data=True, report=True)
    result = subprocess.run([sys.executable, str(tmp_path/'bundle'/'reproduce.py')],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source = tmp_path/'input.csv'
    source.write_text('x,y,sd\n0,1,0.1\n1,2,0.2\n2,3,0.3\n')
    result = subprocess.run([sys.executable, str(ROOT/'scientific-plotting/scripts/plot_template.py'),
        '--input', str(source), '--kind', 'line', '--x', 'x', '--y', 'y', '--yerr', 'sd',
        '--uncertainty-display', 'band', '--errorbar-definition', 'sample SD',
        '--palette', 'coastal', '--output', str(tmp_path/'cli')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path/'cli.jpg').is_file()
