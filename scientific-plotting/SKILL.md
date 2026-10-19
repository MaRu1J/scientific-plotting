---
name: scientific-plotting
description: Create or review reproducible quantitative research plots from CSV, Excel or Python arrays using a stable publication-oriented template. Includes solver and algorithm comparisons, log axes, reference-error panels, uncertainty bars, explicit order guides, zoom insets and multi-panel numeric heatmaps. Not for particle or 3D rendering.
---

# Scientific plotting

Use `scripts/plot_template.py` as the single style source. Read [style specification](references/style.md) before drawing or modifying the template. Preserve the established full rectangular frame, inward ticks on all four sides, solid major and dashed minor grids, legible type, deliberate margins and semantic colors. Do not replace these conventions with another repository's theme.

## Select the workflow

- Ordinary plots: use `render_plot` for DataFrames, equal-length column dictionaries or 2D heatmap arrays; use the CLI for CSV/Excel. `--help` lists its mappings and options.
- Solver/algorithm comparisons, stable series identities, explicit reference orders, zooms and advanced composition: read [algorithm comparisons](references/algorithm-comparisons.md). These are quantitative-data workflows, not ParaView, particle rendering or screenshot composition.
- Mixed CFD/DNS kinds, staggered grids, exact coordinate matching and optional interpolation: read [native CFD comparisons](references/style.md#native-cfd-comparisons). Keep each source's original grid and attribution; use cached raw data first.
- Before describing a figure as ready, read the dated [journal snapshots](references/journals.md). `review_figure` reports differences, not acceptance or compliance. The [source review](references/sources.md) records ideas considered, not an official journal template.

## Decide from the data

- Inspect only user-identified data. Establish columns, units, group meaning and reference identity. Ask when ambiguity changes the scientific claim, not when a documented default suffices.
- `point-line` connects all observations in original within-group row order; `line` omits visible point markers; `scatter` has no connections. Never silently sort, smooth, fit, drop or resample observations. Aggregation is allowed only for a disclosed replicate summary or a separate explicit request.
- Use explicit `kind="mixed"` and a per-series `kind` in `series_styles` when methods, reference lines and observations use different kinds. Native kinds retain their semantics. Prefer a shared paper-level `style_registry` for cross-figure identities; method × resolution roles require explicit combined labels, not inference.
- Log axes require strictly positive input and error-bar endpoints. Report invalid values instead of clipping or deleting them. Reference-error panels default to exactly equal coordinates in the same order; interpolation requires explicit authorization. Relative error at a zero reference raises an error.
- Plot supplied error, cost and residual quantities; do not infer error norms, observed orders or speedups. Power guides use an explicitly supplied order, anchor and range, not a fit. State hardware, problem size and timing scope for cost comparisons; disclose missing information. Label synthetic data as demonstrations, never real validation.

## Uncertainty is not reference error

Inspect whether an unused uncertainty column belongs to the plotted value; use it without requiring the user to say “add error bars.” Names such as SD, SEM, SE or CI are clues, not permission to confuse different statistics. If competing interpretations would change the claim, ask. Do not treat a solver-error metric, residual or tolerance as uncertainty merely because its column contains `error`.

When genuine replicates should be summarized, report the arithmetic mean, sample SD (`ddof=1`), n and units; leave an intentional raw scatter/violin cloud unaggregated. Do not manufacture uncertainty for a single DNS, simulation or formula curve. Follow explicit show/hide requests. The template only draws supplied magnitudes: pass `error_bars` with a meaningful `definition`; it does not calculate statistics. Read [error-bar details](references/style.md#optional-error-bars) for asymmetric magnitudes and alignment rules. Tolerance lines and reference-error panels are distinct from SD, SEM or confidence intervals.

## Render, inspect and deliver

- Default to **JPEG only**, 300 dpi; TIFF requires an explicit request. Refuse PNG, SVG, PDF and EPS. Preserve explicit dpi and width requests and report differences rather than silently replacing them.
- Use `elsevier` by default (90/140/190 mm); select `pof` (85/170 mm defaults) only for that target. JFM retains the documented 90 mm provisional width, not a claim of an official millimetre specification. Standalone defaults remain approximately 4:3; use declared presets or explicit supported height, not stretched exports.
- Report font fallback. Supported faces are Arial, Times New Roman, 思源黑体 and 思源宋体. Use a Chinese face for Chinese text, not merely because it is installed. Axis labels accept `t^*`, `t^+`, `x^2`, `10^-3`, `t_{wall}`, `\(...\)` and `$...$`.
- Ordered colors retain amber → deep blue-teal; methods use the categorical set. Filled point-line markers retain circle, square, triangle, diamond, down-triangle and pentagon, with white edges when sufficiently large. Do not substitute thin open rings, pluses or crosses.
- Inspect at **final physical width**: units, all four tick sides, grids, labels, legend clearance, clipping, grayscale distinction and visible markers. Per-series explicit sizes override global sizes; otherwise sizing adapts to displayed density. Never use `markevery`, thin uncertainty bars or discard observations to reduce crowding. Disclose unavoidable overlap.
- Keep the legend inside when clear; `legend="outside"` means a horizontal band above, not a side legend. Omit in-figure titles for journal figures. Use `render_multipanel` for real composition, normally one shared legend and `(a)`, `(b)`, … letters. For crowded content choose a larger declared preset or ask what to simplify, never shrink text to force a fit.
- Explicit zooms must not hide important data or crowd ticks. They copy resolved main styles and all supplied points/bars without independent sizing. Numerical heatmap comparisons need deliberate shared limits and matching quantity/units; retain linear `cividis` and disclose saturation if limits exclude values.
- CLI delivery pins the template, a rerun launcher and copies of supplied JSON configurations. Data paths still point to original inputs and need updating after relocation; do not call this a portable data bundle. Do not publish user data or the reference paper. Keep new behavior in the central template and add meaningful regression tests rather than forking styles into examples.
