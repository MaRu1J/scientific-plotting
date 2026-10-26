"""Reference-inspired palettes on synthetic engineering replicate summaries."""
import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific-plotting' / 'scripts'))
from plot_template import render_plot, render_multipanel


def main(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose a fresh output directory; existing figures/bundles are not overwritten.')
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261026)
    time = np.linspace(0, 12, 49)
    raw, summaries = [], []
    for index, label in enumerate(('Case A', 'Case B', 'Case C')):
        response = 1 + (0.65 - 0.16 * index) * (1 - np.exp(-time / (2.8 + index * .3)))
        # Smooth correlated replicate variation, not a fitted or smoothed observation.
        offset = rng.normal(0, .035, (24, 1))
        amplitude = rng.normal(0, .025, (24, 1))
        noise = rng.normal(0, .008, (24, len(time)))
        replicates = response + offset + amplitude * np.sin(time / 2) + noise
        for replicate, values in enumerate(replicates):
            raw.extend(dict(case=label, replicate=replicate, time=t, value=y)
                       for t, y in zip(time, values))
        summaries.extend(dict(case=label, time=t, mean=m, sd=s, n=24)
                         for t, m, s in zip(time, replicates.mean(axis=0), replicates.std(axis=0, ddof=1)))
    data = pd.DataFrame(summaries)
    data.to_csv(output / 'summary.csv', index=False)
    pd.DataFrame(raw).to_csv(output / 'synthetic_replicates.csv', index=False)
    definition = 'Synthetic replicate mean +/- sample SD (ddof=1), n=24; not a confidence interval'
    common = dict(data=data, kind='line', x='time', y='mean', group='case',
                  group_kind='categorical', xlabel='Time, t (s)', ylabel='Normalized heat transfer (-)')
    panels = [{**common, 'palette': 'classic', 'error_bars': {'y': 'sd', 'definition': definition}},
              {**common, 'palette': 'soft', 'error_bars': {'y': 'sd', 'definition': definition, 'display': 'band'}}]
    fig, _, _ = render_multipanel(panels, ncols=2, size='double', height_mm=100,
                                  legend='each', sharex=True, sharey=True,
                                  output=output / 'before_after', report=True)
    plt.close(fig)
    fig, _, _ = render_plot(**common, size='double', height_mm=105, palette='coastal',
                            error_bars={'y': 'sd', 'definition': definition, 'display': 'band'},
                            output=output / 'coastal_band', report=True,
                            bundle=output / 'replay', include_data=True)
    plt.close(fig)
    (output / 'caption.txt').write_text(
        'SYNTHETIC DEMONSTRATION ONLY; not measurements or CFD validation.\n'
        '(a) Classic colors with SD whiskers; (b) soft palette with the same SD as shaded bands.\n'
        'Separate coastal_band: the same data with coastal colors.\n'
        'Lines are means of 24 synthetic replicate trajectories; shading/whiskers are +/- sample SD (ddof=1), not 95% CI.\n'
        'No observations were removed, sorted, fitted or interpolated by the renderer.\n'
        'The pale fill uses the line color at alpha=0.18. Color and dash jointly encode case.\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'figures' / 'soft_uncertainty')
    main(parser.parse_args().output)
