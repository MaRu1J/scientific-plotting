# Quantitative distributions, paths and signed terms

Use this workflow for tabular CFD/engineering post-processing, not physical-space field rendering. ParaView or a user-selected post-processing program supplies samples, paired observations, trajectories or already-computed budget terms. Do not infer a mechanism or causal relationship from a distribution alone.

## Choose from the question

| Question | `kind` | Input and interpretation |
| --- | --- | --- |
| How are values distributed? | `histogram` | Raw sample column `x`; explicit shared bins and statistic. |
| What fraction lies below a threshold? | `ecdf` | Raw sample `x`; empirical step function, no fitted distribution. |
| How do medians/spreads compare? | `box` | Sample `x`, optional `group`; unweighted summaries, all fliers visible. |
| How do two quantities co-occur? | `joint` | Paired `x`, `y` rows; 2D binned count/probability/density, not a physical field. |
| How does a response follow an input? | `trajectory` | Paired `x`, `y` in original within-group sequence; optional numeric order column validates, never sorts. |
| Which supplied terms are positive/negative? | `contribution` | Category `x`, signed value `y`, optional case `group`; zero baseline, no invented totals or percentages. |

These are additional native kinds of `render_plot`, also supported as `render_multipanel` panels. Use `analysis={...}` for explicit settings. Existing ordinary kinds reject this argument. Examples below assume `plot_template` has been imported from the skill's `scripts` directory.

## Samples, weights and population

Establish whether rows represent times, cells, particles, experiments or already-binned summaries; record quantity, units, region, time window and weighting in the caption. Do not interpret counts as spatial volume fractions on a nonuniform mesh. A time series can provide an empirical distribution without making its samples independent; do not infer confidence intervals or an effective sample size from the number of rows.

- Distribution samples map to `x` (including `box`); `group` identifies populations. `y` is reserved for joint/path/contribution plots.
- Missing/non-finite mapped values, negative weights and zero-total-weight populations fail explicitly. No rows are silently removed. Zero individual weights are allowed.
- Histogram, ECDF and joint plots can use `analysis={"weight": "volume", "weight_definition": "Cell volume (m^3)"}`. Weighting is never inferred. Box plots are unweighted; weighted quantiles are not implemented.
- No KDE, fitted PDF, smoothing, automatic replicate aggregation, automatic centering/RMS normalization or confidence bands. If the user supplies a previously computed PDF, plot its supplied coordinates using ordinary `line`; do not histogram the PDF values again.

## Histogram and ECDF

```python
render_plot(samples, kind="histogram", x="temperature", group="case",
            analysis={"bins": [290, 300, 310, 330, 360], "statistic": "density",
                      "weight": "volume", "weight_definition": "Cell volume (m^3)"},
            xlabel="Temperature (K)", ylabel="Probability density (1/K)")

render_plot(samples, kind="ecdf", x="temperature", group="case",
            analysis={"weight": "volume", "weight_definition": "Cell volume (m^3)"},
            xlabel="Temperature (K)")

render_plot(samples, kind="box", x="temperature", group="case",
            analysis={"whis": 1.5}, ylabel="Temperature (K)")
```

Histogram `bins` and `statistic` are required. Bins are a positive integer up to 1000 or a list of finite strictly increasing edges. Integer bins use the full pooled range, giving identical edges across overlaid groups; explicit edges must include every sample. Between separately rendered panels, pass the same explicit edges. Bins are left-closed/right-open except the final bin, which includes its right edge.

- `count`: sample count, or sum of supplied weights. Weighted counts retain weight units; label accordingly.
- `probability`: bin mass divided by that population's total mass; bin values sum to one.
- `density`: probability divided by bin width; integrated area is one, not the sum of heights. Supply inverse quantity units in the y label. Unequal-width bins are supported.

Each group's distribution is normalized separately, not as a fraction of the pooled population. Histogram outlines use distinct color/line styles without opaque overlapping fills. Edges, statistic, group sample sizes and supplied weight meaning are recorded in metadata.

ECDF uses stable sorting of a copy of the sample coordinates, combines equal-value jumps and shows the cumulative mass at and below each value, reaching one. This is an intentional statistical transformation, not a change to the input rows. It is recorded explicitly; all other connected plots retain original order.

Box plots show median, Q1/Q3, whiskers to observations within `whis * IQR` of the quartiles, and all observations outside the whiskers as fliers. Default `whis=1.5`; no notches, mean marker or inferred confidence interval. Degenerate/one-sample populations are permitted but are not evidence of variability. Box summaries do not remove samples from the original data.

## Joint distribution

```python
render_plot(samples, kind="joint", x="velocity_fluctuation", y="temperature_fluctuation",
            analysis={"bins": [30, 25], "statistic": "density",
                      "weight": "volume", "weight_definition": "Cell volume (m^3)"},
            xlabel="Velocity fluctuation (m/s)", ylabel="Temperature fluctuation (K)")
```

`bins=[x_bins, y_bins]`: each entry is an integer or an explicit edge list. Paired rows remain paired. Counts, bin probability and joint density use the same meanings as histograms, but density divides by **bin area**. Its units are the inverse product of the two variable units. At most 250000 cells are supported. No interpolation, KDE or conditional-mean reduction is performed; zero-count bins remain zero.

One population per panel; a `group` argument is refused. Use facets for different cases. The color map is `cividis` and its lower limit is zero. Set `analysis["vmax"]` identically across compared panels and use the same explicit edges, statistic, quantities, units and weighting. A maximum that would clip bins fails rather than hiding peaks. Resolved color limits enter metadata. Each panel has its own color bar; the existing heatmap-only `shared_colorbar` interface is not extended here. Colorbar labels default to count/probability/probability density; state density or weighted-count units in the caption. The example gallery demonstrates identical joint scales.

Do not label a raw velocity/temperature joint histogram as Reynolds stress, heat flux, correlation coefficient or a quadrant contribution. Those require separately defined calculations. The renderer does not derive fluctuations, quadrant integrals or causal claims.

## Parametric trajectory / hysteresis display

```python
render_plot(history, kind="trajectory", x="input", y="response", group="case",
            analysis={"order": "time", "arrows": [5, 20]},
            xlabel="Input (-)", ylabel="Response (-)")
```

Rows connect in original within-group order, even when x reverses. `order` optionally names a finite numeric column that must strictly increase within each group. A circle marks the first point. `arrows` is an explicit list of zero-based segment indices, each valid for every group, with no zero-length segment. Omit it for no arrows. Use separate panels when trajectories need different arrow locations. Do not sort x, force loop closure, calculate enclosed area, infer a cycle or claim physical hysteresis automatically. Start/end equality only occurs when the supplied coordinates have it.

## Signed contribution / budget terms

```python
render_plot(terms, kind="contribution", x="term", y="value", group="case",
            analysis={"definition": "Supplied energy-budget terms; positive adds energy, negative removes it."},
            ylabel="Budget term (W)")
```

Requires a nonempty definition of terms/sign convention. Terms retain first-seen order and original signed magnitudes; bars start at zero. Groups use separate offsets and hatch patterns. Repeated term/case pairs fail rather than aggregate. Missing combinations are absent, not fabricated zero values. All terms on an axis must be compatible quantities/units, which must be established from the user data. No stacking, cancellation-hiding normalization, sum-to-100% claim, derivative estimation or equation closure claim. If supplied closure residuals are needed, include an explicitly labelled term or a separate quantitative panel.

## Interface, delivery and limits

- Native analysis kinds currently use linear axes and the existing categorical palettes (`joint` uses its own numeric color scale). For meaningful log coordinates or custom registry-based styles, draw already-processed values using the ordinary series interface instead; do not silently transform raw samples.
- First release does not combine analysis kinds with `series_styles`, `style_registry`, semantic `encoding`, dual axes, reference-error panels, uncertainty bars, insets, reference guides or `heatmap_scale`. Unsupported combinations fail explicitly. Multi-panel global registries continue to apply only to ordinary series panels.
- For overlaid distributions/path series, use the same group order across figures to retain automatic identities; there is no new paper-level registry for these kinds. `box` category labels identify groups directly. No automatic choice of a best scheme.
- CLI: `--kind histogram --x temperature --group case --analysis-config settings.json`. JSON contains the `analysis` mapping, not a nested `analysis` key. As with other configuration files, the CLI copies it beside the generated reproduction script.
- Reports retain the analysis definition and resolved bins/scales. Bundles preserve the config and **used columns only**, including the weight/order column where applicable. Input snapshots still require explicit `include_data=True`; a bundle request alone does not grant permission to package samples.
- `examples/plot_analysis_gallery.py` generates labelled synthetic examples, including a joint two-case comparison. It refuses an existing output directory. Do not present these examples as measured or simulated findings.

## Implementation references

The binned normalizations follow NumPy's histogram definitions, including density per unit bin width/area; box rendering follows Matplotlib's boxplot interface. These are implementation references, not physical evidence:

- [NumPy histogram](https://numpy.org/doc/stable/reference/generated/numpy.histogram.html)
- [NumPy histogram2d](https://numpy.org/doc/stable/reference/generated/numpy.histogram2d.html)
- [Matplotlib boxplot](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.boxplot.html)
