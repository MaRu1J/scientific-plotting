# Optional delivery review and portable reproduction

Read this reference only when saving a review or preparing a relocatable delivery. Both APIs retain the established style, data semantics and `(figure, axes, image_paths)` return. JPEG remains the only default export; TIFF is explicit, and other image formats remain unsupported. No fitting, scientific metric calculation or automatic restyling is added.

## Interfaces

Both `render_plot` and `render_multipanel` accept:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `report` | `False` | Save `<basename>_review.json` and `<basename>_review.md`. |
| `bundle` | `None` | Create a directory-based portable delivery; implies a saved review. |
| `include_data` | `False` | Explicit permission to include only used-data snapshots; requires `bundle`. |

Review and bundle requests require an explicit `output`. Bundle targets must be absent or empty, and original exports must lie outside that target. Failures do not leave a partially assembled, apparently complete bundle. Existing exports and reports are not removed on failure. A report/bundle for hosted panels belongs on the outer `render_multipanel`, not an individual `host_axes` call.

The returned paths contain **images only**. Read `figure.scientific_report_paths`, `figure.scientific_report` and, when requested, `figure.scientific_bundle_path` for delivery information. `review_figure` still returns a list of findings; `figure.scientific_review` includes the extended findings when reporting is enabled.

Single-plot CLI examples (use your own existing CSV; no example performance is implied):

```bash
python plot_template.py --input observations.csv --kind point-line \
  --x spacing --y error --xscale log --yscale log \
  --output figures/convergence --report

# Default: no input data in the bundle.
python plot_template.py --input observations.csv --kind line \
  --x time --y residual --output figures/residual --bundle delivery

# Explicit permission: snapshots of used columns, not the whole source file.
python plot_template.py --input results.xlsx --sheet convergence --kind line \
  --x spacing --y error --output figures/convergence \
  --bundle authorized-delivery --include-data
```

`--include-data` without `--bundle` is rejected. The legacy CLI launcher and configuration copies remain available beside original exports; they are not the portable bundle and still refer to original paths. Its saved command omits the bundle flags so it does not try to overwrite a completed bundle.

## Review: what is checked

- Actual files are opened and fully decoded using Pillow. The report records their decoded format, mode, dimensions, DPI, inferred physical dimensions and SHA-256. Pixels are compared with requested millimetres × DPI / 25.4, allowing one pixel of rendering rounding (a 0.01-pixel floating-point margin). DPI metadata has a 0.05-DPI tolerance for encoding precision.
- Unreadable images, mismatched JPEG/TIFF format, dimensions beyond tolerance, and missing/incorrect DPI are **errors**. Both reports are saved before raising `ValueError`; generated images remain available for diagnosis. Ordinary snapshot, font and grayscale warnings do not fail delivery. There is no additional strict mode.
- RGB JPEG and RGB or fully opaque RGBA TIFF are normal. An opaque TIFF alpha channel is not corruption. Unexpected modes/transparency are recorded and flagged for inspection, never converted behind the user's back.
- Dated journal checks include panel labels, visible typography (also shared colorbars, legends and child zoom axes), data-line widths and existing format/size reminders. Reports distinguish `journal_snapshot`, `actual_file`, `runtime` and `heuristic` findings and list separate manual checks. The snapshot date is recorded; the report is not a submission verdict.
- Separate `style` reminders flag visible standard figure/panel/inset titles and standalone text beginning with `Source:`, `Sources:`, `Data source:` or Chinese source equivalents (ASCII/full-width colons). These are default-style reminders, not journal requirements; confirm explicit permission or move the text to an external caption. Nothing is removed automatically. Axis labels, legend entries, panel letters and ordinary data annotations are not treated as source footers. Arbitrary prose/subtitles and attribution without a recognized prefix still require visual inspection. Rerun `review_figure` after manual edits; already saved reports do not update themselves.
- Requested and resolved text font families, font file basenames and obtainable SHA-256 values are recorded. Runtime notices, including font substitutions and unregistered series, remain warnings and are also written to the review. Resolved font files are not proof of per-glyph or mathematical-font coverage; inspect these manually.

### Grayscale screening

Within each main data axes, registered line/point-line/scatter artists are compared using
`abs(delta(0.2126 R + 0.7152 G + 0.0722 B))` on encoded sRGB components. Distances below **0.08** are flagged. Different effective markers or dashes give an informational reminder; no marker/dash backup gives a warning. References, error bars, zoom duplicates, and heatmap cells are not independent series in this screen. Bars/violins require manual grayscale inspection.

This is a deliberately simple brightness heuristic, not a perceptual color model, print simulation or accessibility certification. It does not check dash visibility under overlap, marker size, transparency or all color-vision deficiencies. No style or data is changed. Inspect identified series at the actual publication width.

Reports contain no original sample arrays. Labels, series names, schema/row counts, figures and runtime messages may still disclose plotted information; review them before external sharing. Existing `_metadata.json` sidecars beside original exports can contain arrays and are **not** copied into bundles.

## One replay mechanism for both APIs

This example uses **synthetic demonstration data**, not a solver validation or paper reproduction. Import the copied `plot_template.py` from your script directory:

```python
import pandas as pd
from plot_template import render_plot, render_multipanel

data = pd.DataFrame({"step": [3, 1, 2], "residual": [0.08, 0.3, 0.15]})
figure, axes, paths = render_plot(
    data, kind="point-line", x="step", y="residual",
    output="figures/synthetic", bundle="synthetic-delivery", include_data=True,
)

figure, axes, paths = render_multipanel(
    [
        {"id": "trace", "data": data, "kind": "point-line", "x": "step", "y": "residual"},
        {"id": "map1", "data": [[1, 2], [3, 4]], "kind": "heatmap", "quantity": "demo", "unit": "-"},
        {"id": "map2", "data": [[2, 3], [4, 5]], "kind": "heatmap", "quantity": "demo", "unit": "-"},
    ],
    layout=[["trace", "trace"], ["map1", "map2"]],
    shared_colorbar={"vmin": 0, "vmax": 5, "label": "Synthetic value (-)"},
    output="figures/synthetic_panels", bundle="synthetic-panels-delivery", include_data=True,
)
```

Both use the same recipe/input-reference mechanism. Order, index, grouping, selected columns, error arrays, series identity, explicit guides, error panels, inset limits, layout and shared colorbar options are preserved. No panel CLI schema is introduced.

### Bundle contents and schema

Schema version **1**, independently checked for manifest and table snapshots:

```text
delivery/
  plot_template.py             # pinned single-file drawing logic
  reproduce.py                 # stdlib integrity checks before template import
  recipe.json                  # renderer/options; tables replaced with input IDs
  manifest.json                # input schema, versions/fonts, SHA-256 per managed file
  requirements-recorded.txt    # actual recorded dependency versions, not an installer
  README.md
  artifacts/                   # original exported images and both review reports
  inputs/                      # exists only with include_data=True
    main.json                  # or panel_0.json, panel_1.json, ...
    main_yerr.json             # separate input for an array-valued y error magnitude
```

The manifest is the integrity index, not its own checksum entry or a signed attestation. Managed file checksums detect accidental changes, **not provenance/authenticity**; coordinated edits to the manifest and files cannot be detected. Treat the template/launcher as executable code from a trusted supplier, not a security sandbox.

Only relative managed paths are used. The bundle does not reference the repository, original working directory, original input path or original configuration JSON. It does not copy fonts, a virtual environment or an entire workbook. Original figure filenames and labels are retained.

Python and actual Matplotlib/NumPy/pandas/Pillow versions are recorded; loaded optional table dependencies are recorded when available. Required dependencies must already be installed. Replay does not request the network or install anything. Missing dependencies stop with a manual-install message, and version/font differences produce warnings. Font-file hashes compare resolved text faces, not licensed font redistribution.

### Default: data excluded

`include_data=False` writes no table snapshots and no hidden numeric arrays in recipe, manifest or report. The manifest explicitly states `include_data: false`, `self_contained: false`. **This is not a self-contained bundle**: users must provide each input ID before replay can proceed.

```bash
python /new/location/delivery/reproduce.py --input main=/safe/used_columns.csv
# With array-valued error bars, also provide the listed auxiliary input:
python /new/location/delivery/reproduce.py \
  --input main=/safe/used_columns.csv --input main_yerr=/safe/y_magnitudes.csv
```

IDs are `main` for a single table, `panel_0`, `panel_1`, … in input-panel order, and `<ID>_<direction>err` for separately supplied error arrays (for example `main_y_lowererr`). Read `manifest.json` for the exact required IDs, columns and dtypes. Missing/unknown/duplicate IDs stop before rendering. Additional unused columns in an externally supplied ordinary table are ignored; matrix inputs must supply the complete expected columns.

Replacement formats are explicit CSV or this template's typed snapshot JSON. CSV ordinary tables have a header and no index column; auxiliary errors have one column named `magnitude`; matrix CSVs must include their first row-label/index column. CSV does not preserve all Python types, numeric column labels, categorical metadata or index semantics: use typed JSON if these matter, rather than silently coercing them. Export the intended Excel sheet explicitly if supplying replacement data; replay does not reopen a whole workbook. Replacements can also explicitly override authorized snapshots.

### Explicit permission: data included

`include_data=True` stores the tables actually passed to rendering after selecting used columns, plus needed error-array inputs. CSV/Excel sources are snapshotted as the selected in-memory table; unused sheets/columns are never copied. Matrix heatmaps retain their required rows/columns. Input objects are not mutated.

The UTF-8 JSON snapshot is column-oriented and records dtype, column/index structures, categorical levels/order and tagged scalar/missing-value representations. It does not use pickle or serialize arbitrary objects. Exact DataFrame roundtrip verification is required before accepting a snapshot. Unsupported types or types that cannot roundtrip faithfully produce an explicit error rather than an approximate conversion. Portable does not mean every pandas extension dtype is supported.

```bash
python /new/location/authorized-delivery/reproduce.py
python /new/location/authorized-delivery/reproduce.py --output-dir /new/empty/output
```

Replay verifies managed file checksums before loading inputs/rendering. Default output goes to `replayed/figure` inside the moved bundle; an existing nonempty output directory or managed-file location is refused. Original images are not overwritten. Later replays require a fresh output directory. Review reports are regenerated for replayed exports.

An authorized bundle is self-contained **with respect to plotted data**, not the Python runtime or fonts. Version records do not automatically recreate an environment; dependency/font differences require inspection. Scientific values, series order, configuration and export properties are the meaningful comparison targets. Cross-system image-byte identity is not guaranteed.
