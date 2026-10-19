---
name: scientific-plotting
description: Create reproducible scientific plots from CSV, Excel or Python arrays using a stable, publication-oriented Python template. Use for connected data points, line/bar/scatter plots, heatmaps and violin plots, including figure review and export.
---

# Scientific plotting

Use this skill when making or reviewing data-driven research figures. The user's established Origin-like style is the default: a full rectangular axis frame, inward ticks on all four sides, solid major and dashed minor gridlines where appropriate, legible fonts, restrained semantic colors, and deliberate margins around the plotting area. Read [style specification](references/style.md) before modifying the template or making a figure.

## Decide before drawing

- Inspect only the data the user identifies. Confirm column mapping, units, group meaning, and what a plotted uncertainty band or error bar represents. Ask when an ambiguity changes the scientific meaning; otherwise follow the defaults in the style specification.
- Distinguish **point-line** (connect observations in their original row order, within each group) from **line** (same connection without visible point markers) and **scatter** (points only). Never sort, smooth, fit, aggregate, omit records, or infer uncertainty unless the user asks and the transformation is disclosed.
- Preserve explicit user instructions and target-journal requirements. If the user has not specified an export format, output **PNG only**. Support explicit SVG, PDF, TIFF and EPS; do not silently add formats.
- Adapt dependencies, path handling and the requested Arial/Times font to the computer; report fallback fonts. Keep the reference image's approximately 4:3 canvas for standalone plots, and let the shared template adjust line weight and marker size to visible point density. Never change the other locked style rules or reassign units to fix an environment issue. Only change the style when the user explicitly requests it.

## Render and inspect

Use `scripts/plot_template.py` as the canonical style source. For a file, run it with `--input`, `--kind`, `--x`, `--y` and `--output` as appropriate; use `--group`, `--value`, `--sheet` or `--index-col` where relevant. Call `render_plot` directly for in-memory tables and arrays. Read [README](../README.md) for complete interface examples. The CLI saves a pinned copy of the template and a reproducibility launcher alongside the exported image; the launcher records the original input path, which must be updated if the data move.

Inspect the resulting image at its intended size: axis labels and units, all four tick sides, real major/minor grids, legend overlap and clipping, color meaning and grayscale distinction. In point-line charts, check that markers remain visible without becoming a solid ribbon; in scatter charts, check that category marks remain distinct. Tune `--line-width` and `--marker-size` when automatic sizing fails, without discarding observations. Fix layout without stretching the size beyond a declared preset. If a figure is too dense, select a larger preset or ask which content to simplify. Report any remaining caveat rather than silently changing the user's visual convention.
Check typography at the **final physical print width**, not at zoomed PNG size: `single` figures should stay near 89 mm and `double` figures near 183 mm. Do not shrink a double-column image into a single column or reduce legend text just to fit it; follow the size-specific typography in the style specification.

When extending chart types, edit central style constants and tests rather than forking visual rules into unrelated scripts. The [source review](references/sources.md) explains how four reference projects informed this original implementation and how to keep attribution honest.
