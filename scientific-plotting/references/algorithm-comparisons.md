# Solver and algorithm comparisons

Use these interfaces for quantitative data, not particle rendering, 3D fields, screenshots or ParaView pipelines. Errors, residuals, wall times and memory measurements must already be supplied. Do not derive norms, speedups or observed convergence orders unless a separate user request authorizes that analysis. Synthetic examples demonstrate plotting only, never solver validation.

## Stable identities across a paper

`style_registry` is a mapping from exact string series labels to `color`, `marker`, and `linestyle`. The CLI reads the same object with `--style-registry registry.json`. It never sets `kind` or stroke sizes.

```python
registry = {
    "Baseline": {"color": "#2F6DB5", "marker": "o", "linestyle": "-"},
    "Candidate": {"color": "#D35400", "marker": "s", "linestyle": "--"},
}
figure, axes, paths = render_plot(
    table, kind="point-line", x="spacing", y="error", group="method",
    style_registry=registry, xscale="log", yscale="log", output="convergence",
)
```

An empty entry `{}` assigns color/marker/dash from its position in the registry using the current categorical palette and symbol sets. Keep that registry order unchanged between figures, or specify all three fields explicitly. Extra registry entries are allowed. Missing entries warn and use the original automatic per-figure allocation; they have no cross-figure guarantee. Explicit `series_styles` overrides individual registry properties, followed by existing automatic defaults. Pure lines ignore registered markers and scatter ignores registered dashes. `mixed` still requires every plotted series' `kind` in `series_styles`.

For method × resolution comparisons, make the full label explicit, for example `Baseline, h=0.05`. Assign method colors and resolution markers/dashes deliberately in the registry. Do not infer these roles from column names or independently recolor subsets. Shared legends still reject inconsistent identities for the same label.

## Explicit reference guides

`reference_guides` is a list; the CLI accepts it via `--reference-config guides.json`. Every guide requires a visible, nonempty `label`. Guides use a restrained gray dashed stroke, appear in the legend and never participate in density-based sizing. They do not alter observations.

```python
reference_guides = [
    {"kind": "power", "order": 2, "anchor": [0.1, 0.005],
     "range": [0.025, 0.2], "label": "$h^2$ reference (explicit)"},
]
```

Power guides require **both axes logarithmic**. The supplied `order=p`, `anchor=[x0,y0]`, and increasing `range=[xmin,xmax]` draw `y=y0*(x/x0)**p`; x, y and evaluated results must be strictly positive and finite. This is a user-selected reference, not an estimated convergence order or proof of convergence. It is sampled independently, without fitting or reordering input data.

Constant guides use `{"kind":"constant", "axis":"y", "value":1e-6, "label":"Explicit tolerance"}`; `axis="x"` marks a supplied coordinate or event. On a log axis the value must be positive. A pair of horizontal constants may describe a supplied tolerance interval. Label the meaning honestly: a tolerance is **not** an SD, confidence interval or uncertainty band. When a tolerance must be computed from a reference, request or explicitly disclose that calculation rather than silently deriving it.

## Explicit local zoom

```python
inset = {"xlim": [0.35, 0.65], "ylim": [1.105, 1.125],
         "bounds": [0.32, 0.12, 0.4, 0.32]}
```

Pass this object as `inset` or via `--inset-config zoom.json`. `bounds=[left,bottom,width,height]` uses main-axes fractions, must fit inside the main axes, and is explicitly chosen, not an automatic region selector. Limits must increase and be positive for log axes. Supported kinds are line, point-line, scatter and mixed.

The inset retains **all** original observations in original order, then clips their display to its limits. It copies resolved main-plot stroke/marker sizes, colors, dashes and supplied uncertainty bars, without another density adaptation. It has no repeated legend or reference guides. Main axes limits and the reference-error panel remain independent. `axes.scientific_inset_axes` exposes the zoom; `axes.scientific_inset_connectors` contains its region rectangle and connectors. Inspect the selected position at print width: move it if it hides the main data or makes ticks crowded, rather than shrinking text or thinning points.

## Quantitative multi-panel layouts

`render_multipanel` accepts `style_registry`, `layout` and `shared_colorbar`. These composition features are Python-only in this version. Each panel can pass `reference_guides`, `inset` and `heatmap_scale` along with its existing plot options.

```python
panels = [
    {"id": "residual", "data": residuals, "kind": "line", "x": "step", "y": "r",
     "group": "method", "yscale": "log"},
    {"id": "accuracy", "data": errors, "kind": "line", "x": "h", "y": "error",
     "group": "method", "xscale": "log", "yscale": "log"},
    {"id": "cost", "data": timings, "kind": "line", "x": "seconds", "y": "error",
     "group": "method", "xscale": "log", "yscale": "log"},
]
figure, axes, paths = render_multipanel(
    panels, layout=[["residual", "residual"], ["accuracy", "cost"]],
    style_registry=registry, size="double", height_mm=155, output="validation",
)
```

Layout rows have equal lengths. Panel IDs must be unique nonempty strings; every panel must appear, unknown IDs are rejected, and `None` means blank. Repeated cells for one panel must form a single rectangle. Omit `ncols` when supplying layout. Returned axes and `(a)`, `(b)`, … letters follow **input panel order**, not matrix traversal. Without layout the existing `ncols` behavior is unchanged. Shared coordinate axes are only appropriate for compatible quantities, units and scales; avoid sharing different physical meanings. Prefer shared-time small multiples to multiple y axes.

### Shared numeric heatmap scales

Standalone `render_plot(..., kind="heatmap", heatmap_scale={"vmin":0,"vmax":5})` keeps the current **linear `cividis`** mapping. Data are unchanged; out-of-range values saturate visually at the selected limits. State that limitation and select the range deliberately.

For one colorbar across multiple heatmaps:

```python
panels = [
    {"data": baseline_matrix, "kind": "heatmap", "quantity": "pressure", "unit": "Pa"},
    {"data": candidate_matrix, "kind": "heatmap", "quantity": "pressure", "unit": "Pa"},
]
figure, axes, paths = render_multipanel(
    panels, shared_colorbar={"vmin":0,"vmax":5,"label":"Pressure (Pa)"},
    size="double", height_mm=85, output="pressure_comparison",
)
```

At least two numeric heatmaps are required. Every heatmap must explicitly declare matching `quantity` and `unit`; use `"-"` for dimensionless values. These declarations are caller assertions, not automatic dimensional verification. All heatmaps share the supplied limits and only one colorbar; a conflicting panel `heatmap_scale` is rejected. Non-heatmap panels remain independent. No screenshot recoloring, diverging palette, zero-centered normalization or 3D processing is introduced.

## Delivery and comparison notes

- Record error definitions and units. Report time as supplied, with hardware, problem size and timing scope (for example solver-only or including I/O). If missing, disclose the missing information; do not claim fair performance or derive speedups.
- Separate methods, discretizations and reference results explicitly. A nominal baseline is not automatically analytical truth. Preserve original sample grids and the existing exact-match/interpolation contract for error panels.
- CLI reproduction pins all four configuration files (`series`, `registry`, `references`, `inset`) beside the template and launcher. Like the existing launcher, input/output and copied configuration paths are absolute; this is not a portable data bundle.
- Reference guides or an inset cause standalone exports to record their settings in `_metadata.json`. Multi-panel metadata is available through `figure.scientific_metadata`, including panel metadata; returned paths contain images only.
- Keep default JPEG and explicit TIFF only. Do not enlarge a declared width, reduce font sizes, hide an error warning, or claim journal acceptance to make a crowded figure fit.
