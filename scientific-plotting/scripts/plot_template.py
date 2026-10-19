"""Reusable, reproducible scientific plotting template and command-line entry."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.collections import PathCollection
from matplotlib import colors, font_manager
from matplotlib.ticker import AutoMinorLocator
import numpy as np
import pandas as pd


SIZES_MM = {"single": (89, 66), "double": (183, 136), "multipanel": (183, 180)}
TEXT_SIZES_PT = {
    "single": {"label": 10, "tick": 8.5, "legend": 8.5, "title": 10.5},
    "double": {"label": 11, "tick": 9.5, "legend": 9.5, "title": 11.5},
    "multipanel": {"label": 11, "tick": 9.5, "legend": 9.5, "title": 11.5},
}
FORMATS = ("png", "svg", "pdf", "tiff", "eps")
KINDS = ("point-line", "line", "bar", "scatter", "heatmap", "violin")
FONTS = {"Arial": "Liberation Sans", "Times New Roman": "Liberation Serif"}
CATEGORICAL_COLORS = ("#126b80", "#b16a25", "#75629b", "#4c8149", "#a65659", "#8c6e45", "#2a8b83", "#566074")
ORDERED_COLORS = ("#c9a61b", "#94b32c", "#58a94b", "#278f70", "#136e85")
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "<")
LINESTYLES = ("-", "--", "-.", ":", (0, (8, 2)), (0, (4, 1)),
              (0, (5, 2, 1, 2, 1, 2)), (0, (2, 1, 2, 3)))


def resolve_font(requested: str) -> str:
    """Pick a specified face or an explicitly reported metric-compatible fallback."""
    if requested not in FONTS:
        raise ValueError(f"Font must be one of: {', '.join(FONTS)}")
    available = {entry.name for entry in font_manager.fontManager.ttflist}
    if requested in available:
        return requested
    fallback = FONTS[requested]
    if fallback not in available:
        raise RuntimeError(f"Neither {requested} nor {fallback} is installed; install one before plotting.")
    warnings.warn(f"{requested} not installed; using {fallback}. Check the final text layout.", stacklevel=2)
    return fallback


def _frame(data: pd.DataFrame | dict | np.ndarray, kind: str) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        frame = data.copy()
    elif isinstance(data, dict):
        frame = pd.DataFrame(data)
    elif kind == "heatmap" and isinstance(data, np.ndarray) and data.ndim == 2:
        frame = pd.DataFrame(data)
    else:
        raise TypeError("Supply a DataFrame or column-to-array mapping; heatmaps also accept a 2D NumPy array.")
    if frame.empty:
        raise ValueError("No data to plot.")
    return frame


def _required(frame: pd.DataFrame, *columns: str | None) -> None:
    missing = [column for column in columns if column is None or column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required column mapping(s): {missing}")
    if frame[list(columns)].isna().any().any():
        raise ValueError("Required columns contain missing values; clean or explicitly exclude them first.")


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    try:
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Column {column!r} must be numeric.") from exc
    if not np.isfinite(values).all():
        raise ValueError(f"Column {column!r} contains non-finite values.")
    return values


def _groups(frame: pd.DataFrame, group: str | None, ordered: bool = False) -> list[tuple[str, pd.DataFrame]]:
    if group is None:
        return [("", frame)]
    _required(frame, group)
    labels = list(pd.unique(frame[group]))
    if ordered and (pd.api.types.is_numeric_dtype(frame[group]) or pd.api.types.is_datetime64_any_dtype(frame[group])):
        labels.sort()
    return [(str(label), frame.loc[frame[group] == label]) for label in labels]


def _ordered_groups(frame: pd.DataFrame, group: str | None, group_kind: str) -> bool:
    if group_kind == "ordered":
        return True
    if group_kind == "categorical" or group is None:
        return False
    series = frame[group]
    return bool(pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series))


def _palette(count: int, ordered: bool) -> list[str]:
    if ordered:
        if count == 1:
            return [ORDERED_COLORS[-1]]
        sequence = colors.LinearSegmentedColormap.from_list("amber_to_teal", ORDERED_COLORS)
        return [colors.to_hex(sequence(shade)) for shade in np.linspace(0, 1, count)]
    return [CATEGORICAL_COLORS[index % len(CATEGORICAL_COLORS)] for index in range(count)]


def _style_axes(axes: mpl.axes.Axes, kind: str) -> None:
    axes.set_facecolor("white")
    axes.set_axisbelow(True)
    for spine in axes.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.95)
        spine.set_color("#292929")
    axes.tick_params(axis="both", which="both", direction="in", top=True, right=True, labeltop=False, labelright=False)
    axes.tick_params(which="major", length=4.5, width=0.85)
    axes.tick_params(which="minor", length=2.5, width=0.65)
    if kind == "heatmap":
        return
    axes.yaxis.set_minor_locator(AutoMinorLocator(2))
    grid_axes = "y" if kind in ("bar", "violin") else "both"
    if grid_axes == "both":
        axes.xaxis.set_minor_locator(AutoMinorLocator(2))
    axes.grid(True, axis=grid_axes, which="major", linestyle="-", linewidth=0.55, color="#b1b1b1")
    axes.grid(True, axis=grid_axes, which="minor", linestyle="--", linewidth=0.45, color="#d1d1d1")


def _adapt_strokes(axes: mpl.axes.Axes, kind: str) -> None:
    if kind not in ("point-line", "line", "scatter"):
        return
    point_sets = [line.get_path().transformed(line.get_transform()).vertices for line in axes.lines]
    point_sets.extend(axes.transData.transform(collection.get_offsets())
                      for collection in axes.collections if isinstance(collection, PathCollection))
    point_sets = [points for points in point_sets if len(points)]
    if not point_sets:
        return
    points = np.concatenate(point_sets)
    sample = points[np.linspace(0, len(points) - 1, min(len(points), 800), dtype=int)]
    if len(sample) > 1:
        distances = np.linalg.norm(sample[:, None, :] - sample[None, :, :], axis=2)
        np.fill_diagonal(distances, np.inf)
        spacing = float(np.median(np.min(distances, axis=1)))
    else:
        spacing = np.inf
    area = axes.get_window_extent().width * axes.get_window_extent().height
    average_spacing = np.sqrt(area / len(points))
    visible_spacing = min(spacing, average_spacing)
    crowded = visible_spacing < 12 or len(point_sets) >= 7
    sparse = visible_spacing >= 26 and len(point_sets) <= 5
    line_width, marker_size, marker_edge = ((1.2, 2.2, 0.4) if crowded else
                                            (1.8, 5.0, 0.8) if sparse else
                                            (1.45, 3.5, 0.7))
    if crowded:
        marker_size = float(np.clip(visible_spacing * 72 / axes.figure.dpi * 0.7, 1.2, 2.2))
    for line in axes.lines:
        line.set_linewidth(line_width)
        if kind == "point-line":
            line.set_markersize(marker_size)
            line.set_markeredgewidth(marker_edge)
            if crowded:
                line.set_markerfacecolor(line.get_color())
    if kind == "scatter":
        for collection in axes.collections:
            if isinstance(collection, PathCollection):
                collection.set_sizes(np.full(len(collection.get_offsets()), marker_size ** 2))
                collection.set_linewidth(marker_edge / 2)


def _line_vertices(axes: mpl.axes.Axes) -> np.ndarray:
    sampled = []
    for line in axes.lines:
        vertices = line.get_path().transformed(line.get_transform()).vertices
        if len(vertices) == 0:
            continue
        sampled.append(vertices)
        if len(vertices) > 1:
            starts, ends = vertices[:-1], vertices[1:]
            distances = np.linalg.norm(ends - starts, axis=1)
            for start, end, distance in zip(starts, ends, distances):
                count = min(200, max(2, int(distance / 5)))
                sampled.append(np.linspace(start, end, count))
    for patch in axes.patches:
        box = patch.get_window_extent()
        sampled.append(np.array([box.p0, box.p1, box.get_points().mean(axis=0)]))
    for collection in axes.collections:
        if hasattr(collection, "get_offsets"):
            offsets = collection.get_offsets()
            if len(offsets):
                sampled.append(axes.transData.transform(offsets))
    return np.concatenate(sampled) if sampled else np.empty((0, 2))


def _place_legend(figure: mpl.figure.Figure, axes: mpl.axes.Axes, size: str) -> None:
    handles, labels = axes.get_legend_handles_labels()
    if not handles:
        return
    renderer = figure.canvas.get_renderer()
    points = _line_vertices(axes)
    axes_box = axes.get_window_extent(renderer)
    legend_size = TEXT_SIZES_PT[size]["legend"]
    locations = ("upper center", "upper right", "upper left", "lower right", "lower left", "lower center", "center right", "center left")
    for columns in range(min(3, len(handles)), 0, -1):
        for location in locations:
            legend = axes.legend(loc=location, ncol=columns, frameon=True, framealpha=1,
                                 facecolor="white", edgecolor="#777777", fontsize=legend_size)
            figure.canvas.draw()
            box = legend.get_window_extent(figure.canvas.get_renderer())
            fits = axes_box.contains(*box.p0) and axes_box.contains(*box.p1)
            hits = int(np.count_nonzero((points[:, 0] >= box.x0 - 3) & (points[:, 0] <= box.x1 + 3)
                                       & (points[:, 1] >= box.y0 - 3) & (points[:, 1] <= box.y1 + 3)))
            if fits and hits == 0:
                return
            legend.remove()
    if size == "single":
        warnings.warn("Legend moved outside the single-column plot; consider --size double to preserve plot area.",
                      stacklevel=2)
    figure.subplots_adjust(right=0.72)
    legend = axes.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=legend_size, frameon=True,
                         facecolor="white", edgecolor="#777777")
    figure.canvas.draw()
    box = legend.get_window_extent(figure.canvas.get_renderer())
    if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
        legend.remove()
        raise ValueError("Legend does not fit this preset; select a larger size or simplify labels.")


def _check_text_layout(figure: mpl.figure.Figure) -> None:
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for panel_axes in figure.axes:
        text_items = [panel_axes.title, panel_axes.xaxis.label, panel_axes.yaxis.label]
        for axis, limits in ((panel_axes.xaxis, panel_axes.get_xlim()),
                             (panel_axes.yaxis, panel_axes.get_ylim())):
            low, high = sorted(limits)
            text_items.extend(tick.label1 for tick in axis.get_major_ticks() if low <= tick.get_loc() <= high)
        for text_item in text_items:
            if not text_item.get_visible() or not text_item.get_text():
                continue
            box = text_item.get_window_extent(renderer)
            if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
                raise ValueError("A label is clipped by this size preset; use a larger preset or shorter labels.")


def render_plot(
    data: pd.DataFrame | dict | np.ndarray,
    *,
    kind: str,
    x: str | None = None,
    y: str | None = None,
    group: str | None = None,
    value: str | None = None,
    group_kind: str = "auto",
    xlabel: str | None = None,
    ylabel: str | None = None,
    title: str | None = None,
    font: str = "Arial",
    size: str = "single",
    output: str | Path | None = None,
    formats: tuple[str, ...] | list[str] | None = None,
    dpi: int = 300,
) -> tuple[mpl.figure.Figure, mpl.axes.Axes, list[Path]]:
    """Draw without changing input data; return figure, axes and exported paths."""
    if kind not in KINDS or size not in SIZES_MM or group_kind not in ("auto", "ordered", "categorical"):
        raise ValueError("Unknown plot kind, size or group kind.")
    chosen_formats = tuple(dict.fromkeys(formats if formats is not None else ("png",)))
    if not chosen_formats or any(format_name not in FORMATS for format_name in chosen_formats):
        raise ValueError(f"Formats must be drawn from {FORMATS}.")
    if not 72 <= dpi <= 1200:
        raise ValueError("DPI must be between 72 and 1200.")
    face = resolve_font(font)
    frame = _frame(data, kind)
    text_sizes = TEXT_SIZES_PT[size]
    with mpl.rc_context({"font.family": face, "font.size": text_sizes["tick"],
                         "axes.labelsize": text_sizes["label"], "axes.titlesize": text_sizes["title"],
                         "xtick.labelsize": text_sizes["tick"], "ytick.labelsize": text_sizes["tick"],
                         "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "savefig.facecolor": "white"}):
        width_mm, height_mm = SIZES_MM[size]
        figure, axes = plt.subplots(figsize=(width_mm / 25.4, height_mm / 25.4), dpi=120)
        _style_axes(axes, kind)
        if kind in ("point-line", "line", "scatter", "bar"):
            _required(frame, x, y)
            if kind in ("point-line", "line", "scatter"):
                ordered = _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                limit = len(MARKERS) * len(LINESTYLES) if kind == "point-line" else len(LINESTYLES)
                if len(values) > limit:
                    raise ValueError("Too many series to distinguish in grayscale; divide them into panels.")
                palette = _palette(len(values), ordered)
                for index, (label, subset) in enumerate(values):
                    x_values, y_values = _numeric(subset, x), _numeric(subset, y)
                    if kind == "scatter":
                        axes.scatter(x_values, y_values, label=label or None, s=24,
                                     marker=MARKERS[index % len(MARKERS)], color=palette[index],
                                     edgecolor="#333333", linewidth=0.35)
                    else:
                        linestyle = (LINESTYLES[(index // len(MARKERS)) % len(LINESTYLES)]
                                     if kind == "point-line" else LINESTYLES[index])
                        axes.plot(x_values, y_values, label=label or None, color=palette[index],
                                  linestyle=linestyle, linewidth=1.5,
                                  marker=MARKERS[index % len(MARKERS)] if kind == "point-line" else None,
                                  markersize=3.5, markerfacecolor="white", markeredgewidth=0.9)
            else:
                _numeric(frame, y)
                ordered = _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                if len(values) > len(CATEGORICAL_COLORS):
                    raise ValueError("Too many bar series to distinguish in grayscale; divide them into panels.")
                if group is None:
                    if frame[x].duplicated().any():
                        raise ValueError("Repeated bar category; aggregate explicitly or specify --group.")
                    axes.bar(frame[x].astype(str), frame[y], color=CATEGORICAL_COLORS[0],
                             edgecolor="#333333", linewidth=0.65)
                else:
                    categories = list(pd.unique(frame[x]))
                    width = 0.8 / len(values)
                    palette = _palette(len(values), ordered)
                    for index, (label, subset) in enumerate(values):
                        if subset[x].duplicated().any():
                            raise ValueError("Repeated group/category; aggregate explicitly before plotting.")
                        positions = np.arange(len(categories)) - 0.4 + width * (index + 0.5)
                        heights = subset.set_index(x)[y].reindex(categories)
                        axes.bar(positions, heights, width=width, label=label, color=palette[index],
                                 edgecolor="#333333", linewidth=0.65,
                                 hatch=("", "//", "..", "xx")[index % 4])
                    axes.set_xticks(np.arange(len(categories)), [str(category) for category in categories])
        elif kind == "heatmap":
            if x is not None or y is not None or value is not None:
                _required(frame, x, y, value)
                _numeric(frame, value)
                if frame.duplicated([y, x]).any():
                    raise ValueError("Duplicate heatmap cells; aggregate explicitly before plotting.")
                rows, columns = list(pd.unique(frame[y])), list(pd.unique(frame[x]))
                frame = frame.pivot(index=y, columns=x, values=value).reindex(index=rows, columns=columns)
            matrix = frame.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
            if not np.isfinite(matrix).all():
                raise ValueError("Heatmap requires a complete finite numeric matrix; handle empty cells first.")
            image = axes.imshow(matrix, cmap="cividis", interpolation="nearest", aspect="auto")
            axes.set_xticks(np.arange(frame.shape[1]), [str(item) for item in frame.columns])
            axes.set_yticks(np.arange(frame.shape[0]), [str(item) for item in frame.index])
            axes.tick_params(which="minor", bottom=False, left=False, top=False, right=False)
            figure.colorbar(image, ax=axes, label=value or "Value", fraction=0.05, pad=0.03)
        else:
            _required(frame, y)
            _numeric(frame, y)
            if x is None:
                categories = ["Data"]
                samples = [frame[y].to_numpy(dtype=float)]
            else:
                _required(frame, x)
                categories = list(pd.unique(frame[x]))
                samples = [frame.loc[frame[x] == category, y].to_numpy(dtype=float) for category in categories]
            parts = axes.violinplot(samples, showmeans=False, showmedians=False)
            for index, body in enumerate(parts["bodies"]):
                body.set_facecolor(CATEGORICAL_COLORS[index % len(CATEGORICAL_COLORS)])
                body.set_edgecolor("#333333")
                body.set_alpha(1)
            for key in ("cbars", "cmins", "cmaxes"):
                parts[key].set_color("#333333")
            axes.set_xticks(np.arange(1, len(categories) + 1), [str(category) for category in categories])
        axes.set_xlabel(xlabel if xlabel is not None else (x or ""))
        axes.set_ylabel(ylabel if ylabel is not None else (y or value or ""))
        if title:
            axes.set_title(title)
        figure.tight_layout(pad=1.0)
        if kind in ("point-line", "line", "scatter"):
            margins = figure.subplotpars
            figure.subplots_adjust(left=max(0.135, margins.left), right=min(0.91, margins.right),
                                   bottom=max(0.13, margins.bottom), top=min(0.95, margins.top))
        figure.canvas.draw()
        _adapt_strokes(axes, kind)
        _place_legend(figure, axes, size)
        _check_text_layout(figure)
        exported = []
        if output is not None:
            target = Path(output)
            if target.suffix.lower().lstrip(".") in FORMATS:
                target = target.with_suffix("")
            target.parent.mkdir(parents=True, exist_ok=True)
            for format_name in chosen_formats:
                destination = target.with_suffix(f".{format_name}")
                figure.savefig(destination, format=format_name, dpi=dpi, facecolor="white")
                exported.append(destination)
        return figure, axes, exported


def _source_script(target: Path, args: list[str]) -> None:
    template = target.with_name(target.stem + "_template.py")
    if template.resolve() == Path(__file__).resolve():
        raise ValueError("Choose an output directory outside the template source directory.")
    shutil.copy2(__file__, template)
    wrapper = target.with_name(target.stem + "_reproduce.py")
    wrapper.write_text(
        "from pathlib import Path\nimport subprocess\nimport sys\n\n"
        "template = Path(__file__).with_name(" + repr(template.name) + ")\n"
        "args = " + repr([*args, "--no-script"]) + "\n"
        "subprocess.run([sys.executable, str(template), *args], check=True)\n",
        encoding="utf-8",
    )


def run_cli(argv: list[str] | None = None) -> list[Path]:
    parser = argparse.ArgumentParser(description="Plot scientific data using a fixed, reusable visual style.")
    parser.add_argument("--input", type=Path, required=True, help="CSV or Excel (.xlsx/.xls) input")
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--x")
    parser.add_argument("--y")
    parser.add_argument("--value", help="Heatmap value column (long-form data)")
    parser.add_argument("--group")
    parser.add_argument("--group-kind", choices=("auto", "ordered", "categorical"), default="auto")
    parser.add_argument("--xlabel")
    parser.add_argument("--ylabel")
    parser.add_argument("--title")
    parser.add_argument("--font", choices=tuple(FONTS), default="Arial")
    parser.add_argument("--size", choices=tuple(SIZES_MM), default="single")
    parser.add_argument("--format", action="append", dest="formats", choices=FORMATS)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    parser.add_argument("--index-col", help="Matrix heatmap row-label column")
    parser.add_argument("--output", type=Path, required=True, help="Output basename; suffix does not override --format")
    parser.add_argument("--no-script", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args(argv)
    source = options.input.resolve()
    if source.suffix.lower() == ".csv":
        frame = pd.read_csv(source, index_col=options.index_col)
    elif source.suffix.lower() in (".xlsx", ".xls"):
        sheet = int(options.sheet) if options.sheet.isdigit() else options.sheet
        frame = pd.read_excel(source, sheet_name=sheet, index_col=options.index_col)
    else:
        parser.error("Input must be .csv, .xlsx or .xls")
    figure, _, paths = render_plot(
        frame, kind=options.kind, x=options.x, y=options.y, group=options.group,
        value=options.value, group_kind=options.group_kind, xlabel=options.xlabel,
        ylabel=options.ylabel, title=options.title, font=options.font, size=options.size,
        output=options.output, formats=options.formats, dpi=options.dpi,
    )
    plt.close(figure)
    if not options.no_script:
        original_args = list(argv if argv is not None else sys.argv[1:])
        original_args[original_args.index("--input") + 1] = str(source)
        original_args[original_args.index("--output") + 1] = str(options.output.resolve())
        target = paths[0].with_suffix("")
        _source_script(target, original_args)
    return paths


if __name__ == "__main__":
    for path in run_cli():
        print(path)
