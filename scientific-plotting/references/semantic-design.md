# Palettes and semantic multi-variable figures

These are explicit extensions of the central template, not a replacement theme. Default calls retain the classic palette, filled markers, frame, grids, text sizes and JPEG-only export. The renderer executes a declared design; the agent recommends a layout from known scientific roles. It does not infer units, normalize values or detect correlation.

## Choose a layout before adding channels

1. Establish x, quantities/units, category identities and experimental conditions from the identified inputs. A reference screenshot is a design reference, not measurements or instructions.
2. For one quantity, compare categories on one axis while readable; facet by condition when needed. Numeric/datetime groups retain an ordered ramp unless explicitly categorical.
3. For different quantities sharing x, prefer separate rows/panels. Keep each panel's quantity and unit explicit. Do not use `sharey=True` across different quantities. Existing `sharey` is figure-wide, not row-wise; automatic y limits may differ even within a row, so disclose that or deliberately review equal limits after editing.
4. Consider dual y axes only when simultaneous event location and compactness matter, and the user has requested or accepted that tradeoff. Different units alone are not a reason. Offer facets first when the figure is crowded.
5. Do not silently standardize, interpolate, thin points, choose a focus method or rescale axes to make curves overlap. Decline unsupported combinations instead of manual bypasses.

The same quantity expressed in convertible units needs a reversible conversion axis, not two independent datasets/scales. A conversion-axis API is not implemented here; share a common unit or use separate panels. No third independent y axis is supported.

## Categorical palettes

Both renderers accept `palette="classic" | "jewel" | "muted" | "focus"` and optional `focus`.

| Palette | Intended use |
| --- | --- |
| `classic` | Existing categorical set; ordered groups retain amber → deep blue-teal |
| `jewel` | More vivid separated hues, up to eight categorical colors |
| `muted` | More subdued, sufficiently dark categorical hues, up to eight colors |
| `focus` | One **explicitly named** identity in blue, background identities in gray; retain marker/dash differences |

`focus` is required only for `palette="focus"`; other palettes reject it. It names a series label normally, a declared category with `encoding`, or an x category for an ungrouped bar/violin plot. A registry can retain an absent focus series across subset panels. No focus is inferred from a baseline, best value or input order.

The new categorical sets refuse ordered groups and capacity overflow rather than interpolate/repeat their colors. Use `group_kind="categorical"` only when that scientific meaning is correct. `classic` preserves its older cycling behavior for compatibility. Continuous heatmaps retain linear `cividis`; passing a categorical palette directly to a heatmap is refused. An outer multi-panel palette applies to eligible non-heatmap panels only. Per-panel palette/focus can override the outer choice.

Use the existing `style_registry` for stable line/scatter/point-line series identities across figures and subsets. Named palette colors initialize its entries in declaration order. Category-level `encoding` is the preferred way to retain the same material identity across different metrics. Bar/violin palette assignment follows their existing category/group order; they do not gain the line-series registry or multi-variable encoding interface.

```python
registry = {"Proposed": {}, "Baseline": {}, "Reference": {}}
figure, axes, paths = render_plot(
    table, kind="point-line", x="step", y="value", group="method",
    palette="jewel", style_registry=registry, output="comparison",
)
```

## Explicit category × metric roles

`encoding` works with line, point-line, scatter and mixed series. It does not transform the table. Supply long-form rows with a unique combined series column yourself, preserving within-series row order. Do not obtain those rows by guessing values from a screenshot.

```python
encoding = {
    "categories": {"Silicon": {}, "Teflon": {}},
    "metrics": {
        "Height": {"fillstyle": "full", "quantity": "relative height", "unit": "-"},
        "Angle": {"fillstyle": "none", "linestyle": "--",
                  "quantity": "contact angle", "unit": "deg"},
    },
    "series": {
        "Silicon height": {"category": "Silicon", "metric": "Height"},
        "Teflon height": {"category": "Teflon", "metric": "Height"},
        "Silicon angle": {"category": "Silicon", "metric": "Angle"},
        "Teflon angle": {"category": "Teflon", "metric": "Angle"},
    },
    "category_label": "Material",
    "metric_label": "Metric",
    "legend": "factorized",
    "reason": "Compare materials across two separately identified responses",
}
```

- `categories` is an ordered identity registry: each value allows explicit `color` and `marker`, otherwise chosen from the palette and existing shapes. Keep its declaration order stable across figures. An unused category retains its slot; no invented observations are drawn.
- `metrics` allows `linestyle`, `fillstyle="full" | "none"`, and paired `quantity`/`unit` declarations. Provide quantity and unit for scientific multi-metric figures; use `"-"` for dimensionless values. They are caller assertions, not automatic dimensional analysis. Missing declarations generate review warnings when multiple metrics share a panel. Different declared quantity/unit pairs cannot share an ordinary y axis; use facets or an explicit validated secondary axis.
- `series` must cover every plotted combined label with a known category and metric. Extra mappings support subset panels. Roles are never parsed out of labels or guessed from numbers.
- Shape/color describe category; fill and optional dash describe metric. No third role automatically consumes the same channel. Condition is normally a panel, not another color.
- Final style priority is `series_styles` > explicitly supplied registry fields > category/metric styles > automatic defaults. With encoding, registry-generated default fields do not overwrite role styles. Without encoding the existing registry behavior is unchanged.
- With `kind="mixed"`, provide each series kind as before. A factorized legend requires one native kind; use `legend="combined"` for heterogeneous kinds or non-factorizable overrides. Typed quantities still require compatible axis meanings; mixed does not grant permission to overlay incompatible units.

### Legends and hollow markers

`encoding.legend="factorized"` creates separate `Material: …` and `Metric: …` keys; it does not claim every combination was observed. The review records missing pairs. One category/metric pair cannot represent several indistinguishable series in this mode. Distinct roles need distinct visible encodings, and conflicting per-series overrides raise a clear error. Use a combined legend or revise the encoding rather than publish misleading proxy keys.

`encoding.legend="combined"` retains all original series labels. Shared multi-panel legends deduplicate keys and reject inconsistent identities between panels. Legends keep the existing inside-first/outside-horizontal policy and original font sizes. Shared legends account for panel letters rather than covering them.

`fillstyle` also works explicitly in `series_styles` and `style_registry` for point-line/scatter series. Plain lines reject it. Hollow symbols retain colored edges and no fill through density adaptation, uncertainty bars, legend copying and insets. Final marker diameters below 3.6 pt generate a review warning: switch to facets or an explicitly suitable marker size, never `markevery`/row removal. Normal filled-marker defaults remain unchanged.

## Explicit independent dual y axes

Native line, point-line and scatter accept `secondary_y` on the same long-form table. Each combined series goes wholly to one axis, preserving its own x samples. There is no sorting, interpolation or alignment of the two grids.

```python
secondary_y = {
    "series": ["Silicon angle", "Teflon angle"],
    "label": "Contact angle (deg)",
    "quantity": "contact angle", "unit": "deg",
    "limits": [40, 150], "scale": "linear",
    "primary": {"quantity": "relative height", "unit": "-", "limits": [0.9, 2.0]},
    "reason": "Compact synchronized-response comparison; limits cover the measured ranges",
}
figure, axes, paths = render_plot(
    long_table, kind="point-line", x="field", y="value", group="series",
    xlabel="Electric field (kV/cm)", ylabel="Relative height (-)",
    encoding=encoding, secondary_y=secondary_y, palette="jewel",
    size="double", output="responses", report=True,
)
right_axes = axes.scientific_secondary_axes
```

Required safeguards:

- Both axes have an explicit quantity, unit and increasing finite limits; primary `ylabel`, secondary `label` and a scientific `reason` are required. This documents a caller decision, not independent proof of scientific appropriateness. Keep a common meaningful x domain; staggered samples are allowed and not resampled.
- `series` is a nonempty unique proper subset of actual plotted labels. A declared metric cannot be split across axes, and its declared quantity/unit must match its assigned axis. The same named quantity is refused as independent dual axes.
- Limits must cover every observation and supplied uncertainty whisker. No automatic clipping or omission. A log axis validates its own values and lower endpoints; the other axis may remain linear with negative values.
- Only the primary axis draws a grid. Right ticks/labels are visible and use the existing typography; the legend belongs to the topmost/right Axes so secondary data cannot cover it.
- Draw supplied uncertainty bars on their own axis, with the original statistic definition; they do not become uncertainty on the other metric. Bounds must already use each plotted metric's units.
- Multi-panel composition accepts `secondary_y` per panel. It refuses figure-wide `sharey=True`; choose scientifically justified limits separately. With `sharex=True`, retain a scientifically common independent variable.
- **Not supported together yet:** `mixed`, `inset`, `reference_guides`, or reference-error panels. These combinations fail instead of silently ignoring options. Use ordinary panels for those workflows.
- Record in the caption that the y axes are independent. Curve crossings, relative slopes and visual alignment are not equality or statistical correlation. If the final-width figure is unclear, return to facets; do not tune limits to create apparent agreement.

The review records axis limits and rationale, screens right-label overlap and secondary gridlines, compares grayscale identities across **both** axes, and warns if limits are later manually changed. After manual edits rerun `review_figure` and inspect the final canvas; the review is not certification.

## CLI, reports and reproduction

Single-plot CLI adds `--palette`, `--focus`, `--encoding-config roles.json`, and `--secondary-y-config axes.json`. Both new JSON files are pinned beside the legacy launcher like the existing style/inset files. A fresh output using a named palette, encoding or dual axes saves numeric metadata separately; returned paths remain image-only.

`report=True` includes `visual_decisions` for active new modes, with resolved role identities and explicit axis rationale; Markdown reports summarize those choices. Multi-panel recipes preserve both outer settings and panel overrides. Bundles pin the current template and settings; `include_data=False` still omits inputs, and explicit used-column snapshots remain opt-in. Do not interpret the metadata sidecar beside the original export as data-free.

Run the synthetic gallery into a **fresh** output location:

```bash
MPLBACKEND=Agg .venv/bin/python examples/plot_semantic_gallery.py --output figures/semantic_gallery
MPLBACKEND=Agg .venv/bin/python -m pytest -q tests/test_semantic_plotting.py
```

The gallery produces palette comparisons, metric × condition facets, an uncertainty-bearing dual-axis figure and three dual-axis conditions, JSON/Markdown reviews, a data-authorized synthetic replay bundle, separate caption notes, and grayscale/protanopia/deuteranopia/tritanopia derivatives. Palette diagnostics report contrast and Oklab separation as heuristics. CVD derivatives use Machado et al. (2009) severity 1.0 matrices in linear sRGB with out-of-gamut clipping; they are previews, not observations or accessibility certification. No extra runtime package is required. The synthetic data are not the attached experiment or a paper reproduction.

Design references: Matplotlib's “Choosing Colormaps”, “Styling with cycler”, `Line2D.fillstyle`, `Axes.twinx` and “Secondary Axis”; Machado, Oliveira and Fernandes (2009), “A Physiologically-based Model for Simulation of Color Vision Deficiency”. The broader rationale and source locators remain in the dated repository optimization plan.
