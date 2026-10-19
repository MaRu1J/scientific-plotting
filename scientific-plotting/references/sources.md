# Source review and reuse boundary

Snapshot: 2026-10-19. Star counts below are the figures shown on each repository page that day (8.6k, 9.3k, 11.6k, 2.1k). The GitHub API did not return a fresh count in this session, and the K-Dense page text did not include a star total. Stars change and are only a reason to look, not a reason to copy.

This round looked for widely recommended plotting practice, then kept only what does not fight the locked frame, grid, canvas, legend, type, and export rules. No code, style file, image, or palette table was copied.

| Source | What was worth learning | What was not taken |
| --- | --- | --- |
| [ChenLiu-1996/figures4papers](https://github.com/ChenLiu-1996/figures4papers) (about 8.6k, MIT), `scientific-figure-making/references/design-theory.md` | Filled markers with a white edge; separate series by color, shape, and size together; avoid the default Matplotlib cycle; check the figure at column width. | Its palette, serif defaults, and any instruction to emit PDF alongside PNG. |
| [garrettj403/SciencePlots](https://github.com/garrettj403/SciencePlots) (about 9.3k, MIT) | Keep a named color cycle separate from the base style, and do not pretend a style file is a journal's official template. Paul Tol's bright cycle is the usual publication recommendation, but its yellow and cyan are too light for thin lines on white. | Serif text, outward or absent spines, and grid-off defaults. |
| [rougier/scientific-visualization-book](https://github.com/rougier/scientific-visualization-book) (about 11.6k) | Choose the chart for the question, put color on the data rather than the chrome, and do not add decoration that is not in the data. | Direct labels in place of the legend rule, and any of the book's figure geometry. |
| [jbmouret/matplotlib_for_papers](https://github.com/jbmouret/matplotlib_for_papers) (about 2.1k) | Subplot craft and the reminder that a house style is a choice, not a law. | Its visual theme. |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | The repository is a large public collection of scientific skills, including figure guidance that warns against rainbow scales and unstated uncertainty. The skill text was not vendored. | Viridis-as-default, direct-label-only legends, and any instruction that would replace this template. |

The earlier low-star skills (`xiao-yuling/sci-figure` 22, `HututuWorks/academic-figure` 8, `Techd81/SciFig` 7, `O0000-code/SSCI-Plots` 6, all as of the first snapshot) remain useful only as a record of what was considered first. Their outward ticks and major-grid-only advice lost to the locked frame and grid. Nothing was copied from them either.

Color and point-line markers were the part opened for revision. Ordered series stay on an amber → yellow-green → green → deep blue-teal path, but the stops are darker and more evenly separated in lightness than the first mustard ramp. Other counts are blended in Oklab so the mix does not turn brown in sRGB. Methods use eight hues that are actually apart: blue, orange, green, magenta, olive, red, indigo, gray. Point-line symbols are filled circles, squares, triangles, diamonds, down-triangles, and pentagons, with a white edge once the marker is large enough to keep that edge from eating the fill. Plus, cross, and sideways-triangle markers were dropped because they do not survive at a few points.

These choices are not claimed as a certified color-vision palette. A red-green ramp cannot be made fully robust and still be amber-to-teal; shape and line style are the backup. Heatmaps stay on Matplotlib's `cividis` rather than a rainbow map. Do not invent error bars, bands, or significance marks to make a figure look finished.
