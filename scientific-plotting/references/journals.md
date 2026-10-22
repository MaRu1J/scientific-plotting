# Journal snapshots

Checked 2026-10-19. These notes drive review warnings. They are not journal templates, and a figure is never reported as compliant, accepted, or ready for submission solely because the review list is empty.

## Elsevier widths

Used for JCP, CMAME, IJHMT and ATE.

- Presets: `single` 90 × 67.5 mm, `medium` 140 × 105 mm, `double` 190 × 142.5 mm. Height is width × 3/4 because the artwork pages do not fix an aspect ratio.
- Type warning starts below 7 pt.
- TIFF, when dpi is omitted: 1000 dpi for line-like figures, 500 dpi if the figure contains a heatmap.
- Elsevier's own artwork list is EPS, PDF, TIFF and JPEG. This skill writes JPEG by default and TIFF on request. It does not write EPS or PDF.
- Source: [Elsevier artwork and media instructions](https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions).

## Journal of Fluid Mechanics

- Treated as a single-column journal. The instructions checked on this date did not state a millimetre text width, so the skill uses the 90 mm `single` preset and the review says to confirm the current text width.
- Type warning starts below 9 pt, from the Cambridge artwork guide's 9 pt recommendation. The skill does not enlarge the 8.5 pt tick and legend text to silence that warning.
- JFM asks for EPS or high-resolution TIFF. This skill cannot write EPS. A JPEG export is warned. TIFF line art uses 1200 dpi, or 600 dpi when a heatmap is present, unless dpi is set explicitly.
- The JFM instructions file specifies RGB. The Cambridge artwork guide specifies CMYK. The review records that disagreement and does not convert the file.
- Minor gridlines remain 0.45 pt. The review notes that this is under JFM's 0.5 pt line minimum.
- Sources: [JFM instructions for contributors](https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/information/instructions-contributors) and the [Cambridge journals artwork guide](https://www.cambridge.org/core/services/authors/journals/journals-artwork-guide).

## Physics of Fluids

- Optional presets: `aip-single` 85 × 63.75 mm and `aip-double` 170 × 127.5 mm. These follow the requested rounding of AIP's 3.37 in and 6.69 in figures. The review notes that 170 mm is about 0.1 mm wider than 6.69 in (169.9 mm).
- Asking for PoF without a size selects `aip-single`. An explicit Elsevier width is not replaced; the review warns instead.
- Type warning starts below 8 pt. Omitted TIFF dpi is 600.
- The width and depth limits are the general AIP figure guidance used for journals other than the separately listed exceptions, checked through AIP's preparing-illustrations guidance on 2026-10-19. Maximum depth used by this skill for every journal is 210 mm, just under AIP's 8.25 in.

## Multi-panel figures

`render_multipanel` places real axes on one of the widths above. Two to four panels on a width of at least 140 mm use two columns unless `ncols` is set. Each row targets a 4:3 panel plus a small label allowance. Total height stops at 210 mm, and the review says when that cap replaced 4:3. Panel letters are `(a)`, `(b)`, `(c)`. The default legend is one shared row just above the panels and no wider than the outer left and right spines. The same series name with a different color, line style, or marker is an error. No title is drawn inside the figure.
