# Source review and reuse boundary

Snapshot: 2026-10-19, GitHub repository API `stargazers_count` and SPDX license fields. Stars change; check the snapshot again when revisiting the reference set. They determine consultation priority, not correctness or permission to copy. At this snapshot the proportional reference weights are 22:8:7:6 (sum 43); an explicit user preference or scientific constraint takes precedence regardless of weight.

| Repository | Stars | License | What we consulted |
| --- | ---: | --- | --- |
| [xiao-yuling/sci-figure](https://github.com/xiao-yuling/sci-figure) | 22 | MIT | `references/style-guide.md`: complete frame, low-saturation comparisons, grayscale checks, and 1.2 pt minimum line recommendation; also basic research chart/export workflow. |
| [HututuWorks/academic-figure](https://github.com/HututuWorks/academic-figure) | 8 | Apache-2.0 | `skills/academic-figure/SKILL.md`: keep reference figures as *style-only* examples, verify scientific meaning and figure delivery before claiming a result. |
| [Techd81/SciFig](https://github.com/Techd81/SciFig) | 7 | MIT | `scifig/resources/palette-presets.md`: stable semantic colors, grayscale checks, and marker/line redundancy instead of cycling indistinguishable colors. |
| [O0000-code/SSCI-Plots](https://github.com/O0000-code/SSCI-Plots) | 6 | MIT | `references/color-system.md`: separate ordered versus categorical decisions, consider group count and color-vision accessibility; style/size defaults are centralized in its plotting helpers. |

For the reference image supplied in this thread, the canvas measures 1336 × 994 px (ratio about 1.344). The new standalone presets approximate this ratio while retaining 89/183 mm column widths. Its five ordered yellow→teal hues motivated an independently selected, slightly more restrained five-anchor gradient; unrelated methods keep their own categorical colors. The highest-starred source's recommendation to keep strokes at least 1.2 pt is applied to dense lines. Its outward-only ticks and major-grid-only suggestions conflict with the user's explicit inward four-sided ticks and solid-major/dashed-minor grids, so the user's choices prevail.

This repository does **not** import or copy code, palettes, images, or example datasets from these projects; the Python template and examples here are independently written. Source repositories may use additional third-party resources with different licenses, so do not copy their assets or specific third-party palettes without a separate check. These custom colors are not represented as formally color-vision-tested; marker and line-style redundancy plus actual grayscale review remain necessary.
