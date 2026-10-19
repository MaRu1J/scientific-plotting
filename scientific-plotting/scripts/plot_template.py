"""Reusable, reproducible scientific plotting template and command-line entry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.container import BarContainer
from matplotlib import colors, font_manager
from matplotlib.ticker import AutoMinorLocator, LogFormatterSciNotation, LogLocator, NullFormatter
import numpy as np
import pandas as pd


SIZES_MM = {
    "single": (90.0, 67.5),
    "medium": (140.0, 105.0),
    "double": (190.0, 142.5),
    "aip-single": (85.0, 63.75),
    "aip-double": (170.0, 127.5),
}
_NARROW_TEXT = {"label": 10, "tick": 8.5, "legend": 8.5, "title": 10.5}
_WIDE_TEXT = {"label": 11, "tick": 9.5, "legend": 9.5, "title": 11.5}
TEXT_SIZES_PT = {
    "single": _NARROW_TEXT,
    "aip-single": _NARROW_TEXT,
    "medium": _WIDE_TEXT,
    "double": _WIDE_TEXT,
    "aip-double": _WIDE_TEXT,
}
FORMATS = ("jpeg", "tiff")
REJECTED_FORMATS = ("png", "svg", "pdf", "eps")
EXPORT_SUFFIX = {"jpeg": ".jpg", "tiff": ".tiff"}
LINE_WIDTH_MIN_PT = 0.5
LINE_WIDTH_MAX_PT = 1.5
HEIGHT_MIN_MM = 40.0
HEIGHT_MAX_MM = 210.0
JPEG_QUALITY = 95
SNAPSHOT_DATE = "2026-10-19"
PANEL_CHROME_MM = 16.0
JOURNALS = {
    "elsevier": {"widths_mm": (90.0, 140.0, 190.0), "default_size": "single", "min_type_pt": 7,
                 "tiff_line_dpi": 1000, "tiff_heatmap_dpi": 500},
    "jfm": {"widths_mm": (90.0,), "default_size": "single", "min_type_pt": 9,
            "tiff_line_dpi": 1200, "tiff_heatmap_dpi": 600},
    "pof": {"widths_mm": (85.0, 170.0), "default_size": "aip-single", "min_type_pt": 8,
            "tiff_line_dpi": 600, "tiff_heatmap_dpi": 600},
}
KINDS = ("point-line", "line", "bar", "scatter", "heatmap", "violin", "mixed")
SERIES_KINDS = ("line", "point-line", "scatter")
FONTS = {"Arial": "Liberation Sans", "Times New Roman": "Liberation Serif"}
# Categorical hues stay apart and dark enough for a thin line on white.
# Ordered stops run amber -> yellow-green -> green -> teal -> deep blue-teal.
CATEGORICAL_COLORS = ("#2F6DB5", "#D35400", "#1B8A4C", "#AA3377", "#6A7020", "#C4453A", "#5C4E9A", "#3A3F46")
ORDERED_COLORS = ("#C46B04", "#578006", "#24782B", "#066955", "#0A5270")
MARKERS = ("o", "s", "^", "D", "v", "p")
SCATTER_DENSE_PT = 5.0
SCATTER_SPARSE_PT = 6.2
LINESTYLES = ("-", "--", "-.", ":", (0, (8, 2)), (0, (4, 1)),
              (0, (5, 2, 1, 2, 1, 2)), (0, (2, 1, 2, 3)))

ERRORBAR_CAPSIZE_PT = 2.2
ERRORBAR_ELINEWIDTH_PT = 0.8
_ERRORBAR_KEYS = frozenset({"x", "y", "x_lower", "x_upper", "y_lower", "y_upper",
                            "capsize", "elinewidth", "definition"})


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


def _linear_srgb(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _encode_srgb(channel: float) -> float:
    channel = float(np.clip(channel, 0, 1))
    return 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def _srgb_to_oklab(color: str) -> np.ndarray:
    linear = np.array([_linear_srgb(channel) for channel in colors.to_rgb(color)])
    cone = np.cbrt(np.array([
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]) @ linear)
    return np.array([
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]) @ cone


def _oklab_to_hex(oklab: np.ndarray) -> str:
    long, medium, short = np.array([
        [1.0, 0.3963377774, 0.2158037573],
        [1.0, -0.1055613458, -0.0638541728],
        [1.0, -0.0894841775, -1.2914855480],
    ]) @ oklab
    linear = np.array([
        [4.0767416621, -3.3077115913, 0.2309699292],
        [-1.2684380046, 2.6097574011, -0.3413193965],
        [-0.0041960863, -0.7034186147, 1.7076147010],
    ]) @ np.array([long, medium, short]) ** 3
    return colors.to_hex(tuple(_encode_srgb(channel) for channel in linear))


def _palette(count: int, ordered: bool) -> list[str]:
    if ordered:
        if count <= 1:
            return [ORDERED_COLORS[-1]]
        if count == len(ORDERED_COLORS):
            return list(ORDERED_COLORS)
        anchors = np.vstack([_srgb_to_oklab(color) for color in ORDERED_COLORS])
        positions = np.linspace(0, 1, len(ORDERED_COLORS))
        mixed = []
        for sample in np.linspace(0, 1, count):
            mixed.append(_oklab_to_hex(np.array([np.interp(sample, positions, anchors[:, channel])
                                                 for channel in range(3)])))
        mixed[0], mixed[-1] = ORDERED_COLORS[0], ORDERED_COLORS[-1]
        return mixed
    return [CATEGORICAL_COLORS[index % len(CATEGORICAL_COLORS)] for index in range(count)]


def connected_stroke(spacing: float) -> tuple[float, float]:
    """Line width and point-line marker diameter, in points, from within-series spacing."""
    if spacing < 4:
        return 0.7, 2.6
    if spacing < 12:
        return 1.0, 3.8
    if spacing < 26:
        return 1.2, 5.0
    return 1.5, 6.2


def _marker_edge(diameter: float) -> tuple[str, float]:
    """White edge separates a filled marker from its line; tiny markers stay solid."""
    if diameter < 3.6:
        return "face", 0.35
    if diameter < 4.6:
        return "white", 0.55
    if diameter < 5.8:
        return "white", 0.7
    return "white", 0.9


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
    grid_axes = "y" if kind in ("bar", "violin") else "both"
    for axis in (axes.yaxis, axes.xaxis) if grid_axes == "both" else (axes.yaxis,):
        if axis.get_scale() == "log":
            axis.set_major_locator(LogLocator(base=10, numticks=1000))
            axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=1000))
            axis.set_major_formatter(LogFormatterSciNotation(base=10))
            axis.set_minor_formatter(NullFormatter())
        else:
            axis.set_minor_locator(AutoMinorLocator(2))
    axes.grid(True, axis=grid_axes, which="major", linestyle="-", linewidth=0.55, color="#b1b1b1")
    axes.grid(True, axis=grid_axes, which="minor", linestyle="--", linewidth=0.45, color="#d1d1d1")


def _adapt_strokes(axes: mpl.axes.Axes, kind: str,
                   line_width: float | None = None, marker_size: float | None = None) -> None:
    if kind not in (*SERIES_KINDS, "mixed"):
        return
    for collection in axes.collections:
        if not isinstance(collection, PathCollection) or not len(collection.get_offsets()):
            continue
        style = getattr(collection, "_scientific_style", {})
        points = axes.transData.transform(collection.get_offsets()) * 120 / axes.figure.dpi
        sample = points[np.linspace(0, len(points) - 1, min(len(points), 800), dtype=int)]
        if len(sample) > 1:
            distances = np.linalg.norm(sample[:, None, :] - sample[None, :, :], axis=2)
            np.fill_diagonal(distances, np.inf)
            spacing = float(np.median(np.min(distances, axis=1)))
        else:
            spacing = np.inf
        override = style.get("marker_size", marker_size)
        diameter = override if override is not None else (SCATTER_DENSE_PT if spacing < 12 else SCATTER_SPARSE_PT)
        collection.set_sizes(np.full(len(collection.get_offsets()), diameter ** 2))
        collection.set_linewidth(0.45 if diameter < 5.5 else 0.6)
        collection.set_edgecolor("#2A2A2A")
        collection.set_alpha(0.85 if spacing < 12 else 1)
    for line in axes.lines:
        if getattr(line, "_scientific_errorbar", False):
            continue
        style = getattr(line, "_scientific_style", {})
        series_kind = style.get("kind", kind)
        vertices = line.get_path().transformed(line.get_transform()).vertices
        border = axes.get_window_extent()
        visible = (np.isfinite(vertices).all(axis=1) & (vertices[:, 0] >= border.x0)
                   & (vertices[:, 0] <= border.x1) & (vertices[:, 1] >= border.y0) & (vertices[:, 1] <= border.y1))
        distances = np.linalg.norm(np.diff(vertices, axis=0), axis=1)[visible[:-1] & visible[1:]]
        spacing = float(np.median(distances) * 120 / axes.figure.dpi) if len(distances) else np.inf
        width, diameter = connected_stroke(spacing)
        width_override = style.get("line_width", line_width)
        marker_override = style.get("marker_size", marker_size)
        line.set_linewidth(width_override if width_override is not None else width)
        if series_kind == "point-line":
            diameter = marker_override if marker_override is not None else diameter
            edge_mode, edge_width = _marker_edge(diameter)
            line.set_markersize(diameter)
            line.set_markerfacecolor(line.get_color())
            line.set_markeredgecolor(line.get_color() if edge_mode == "face" else "white")
            line.set_markeredgewidth(edge_width)


def _adapt_log_ticks(axes) -> None:
    border = axes.get_window_extent()
    for axis, limits, length in ((axes.xaxis, axes.get_xlim(), border.width),
                                  (axes.yaxis, axes.get_ylim(), border.height)):
        if axis.get_scale() != "log":
            continue
        decades = abs(np.diff(np.log10(limits))[0])
        spacing = length * 120 / axes.figure.dpi / decades
        subs = np.arange(2, 10) if spacing >= 60 else (2, 5)
        axis.set_minor_locator(LogLocator(base=10, subs=subs, numticks=1000))


def _hide_edge_grids(axes: mpl.axes.Axes) -> None:
    border = axes.get_window_extent()
    padding = 4 * axes.figure.dpi / 72
    for axis, low, high, coordinate in ((axes.xaxis, border.x0, border.x1, 0),
                                        (axes.yaxis, border.y0, border.y1, 1)):
        for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks()):
            transform = axes.get_xaxis_transform() if coordinate == 0 else axes.get_yaxis_transform()
            position = transform.transform((tick.get_loc(), 0) if coordinate == 0
                                           else (0, tick.get_loc()))[coordinate]
            if min(abs(position - low), abs(position - high)) < padding:
                tick.gridline.set_visible(False)


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


def _extents_overlap(first, second, pad: float) -> bool:
    return not (first.x1 <= second.x0 - pad or second.x1 <= first.x0 - pad
                or first.y1 <= second.y0 - pad or second.y1 <= first.y0 - pad)


def _layout_boxes(figure: mpl.figure.Figure):
    renderer = figure.canvas.get_renderer()
    boxes = []
    for panel in figure.axes:
        boxes.append(panel.get_window_extent(renderer))
        texts = [panel.title, panel.xaxis.label, panel.yaxis.label,
                 panel.xaxis.get_offset_text(), panel.yaxis.get_offset_text()]
        for axis in (panel.xaxis, panel.yaxis):
            texts.extend(tick.label1 for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks()))
        for text in texts:
            if text.get_visible() and text.get_text().strip():
                boxes.append(text.get_window_extent(renderer))
    return boxes


def _outside_legend_is_clear(figure: mpl.figure.Figure, legend) -> bool:
    box = legend.get_window_extent(figure.canvas.get_renderer())
    if box.x0 < 2 or box.y0 < 2 or box.x1 > figure.bbox.x1 - 2 or box.y1 > figure.bbox.y1 - 2:
        return False
    if box.height > figure.bbox.height * 0.35 or figure.subplotpars.top - figure.subplotpars.bottom < 0.4:
        return False
    pad = 4 * figure.dpi / 72
    return all(not _extents_overlap(box, other, pad) for other in _layout_boxes(figure))


def _place_outside_legend(figure: mpl.figure.Figure, axes: mpl.axes.Axes, legend_size: float) -> bool:
    """Put the legend in a top band, then a bottom band. Never use a side column."""
    handles, labels = axes.get_legend_handles_labels()
    saved = (figure.subplotpars.left, figure.subplotpars.bottom, figure.subplotpars.right, figure.subplotpars.top)
    pad = 6 * figure.dpi / 72

    def restore() -> None:
        figure.subplots_adjust(left=saved[0], bottom=saved[1], right=saved[2], top=saved[3])

    for side, loc, anchor in (("top", "upper center", (0.5, 0.99)), ("bottom", "lower center", (0.5, 0.01))):
        for columns in range(len(handles), 0, -1):
            restore()
            legend = axes.legend(handles, labels, loc=loc, bbox_to_anchor=anchor, bbox_transform=figure.transFigure,
                                 ncol=columns, frameon=True, framealpha=1, facecolor="white", edgecolor="#777777",
                                 fontsize=legend_size)
            figure.canvas.draw()
            box = legend.get_window_extent(figure.canvas.get_renderer())
            if box.x0 < 2 or box.x1 > figure.bbox.x1 - 2 or box.height > figure.bbox.height * 0.35:
                legend.remove()
                continue
            if side == "top":
                edge = (box.y0 - pad) / figure.bbox.height
                if edge - saved[1] < 0.4:
                    legend.remove()
                    continue
                figure.subplots_adjust(top=min(saved[3], edge))
            else:
                edge = (box.y1 + pad) / figure.bbox.height
                if saved[3] - edge < 0.4:
                    legend.remove()
                    continue
                figure.subplots_adjust(bottom=max(saved[1], edge))
            figure.canvas.draw()
            box = legend.get_window_extent(figure.canvas.get_renderer())
            intrusion = 0
            for other in _layout_boxes(figure):
                if not _extents_overlap(box, other, pad):
                    continue
                if side == "top":
                    intrusion = max(intrusion, other.y1 + pad - box.y0)
                else:
                    intrusion = max(intrusion, box.y1 + pad - other.y0)
            if intrusion:
                if side == "top":
                    edge = figure.subplotpars.top - intrusion / figure.bbox.height
                    if edge - figure.subplotpars.bottom < 0.4:
                        legend.remove()
                        continue
                    figure.subplots_adjust(top=edge)
                else:
                    edge = figure.subplotpars.bottom + intrusion / figure.bbox.height
                    if figure.subplotpars.top - edge < 0.4:
                        legend.remove()
                        continue
                    figure.subplots_adjust(bottom=edge)
                figure.canvas.draw()
            if _outside_legend_is_clear(figure, legend):
                return True
            legend.remove()
    restore()
    return False


def _place_legend(figure: mpl.figure.Figure, axes: mpl.axes.Axes, size: str,
                  placement: str = "auto") -> None:
    handles, labels = axes.get_legend_handles_labels()
    if not handles:
        return
    renderer = figure.canvas.get_renderer()
    points = _line_vertices(axes)
    axes_box = axes.get_window_extent(renderer)
    radii = [line.get_markersize() / 2 if line.get_marker() not in (None, "None", "", " ")
             else line.get_linewidth() / 2 for line in axes.lines]
    radii.extend(float(np.sqrt(collection.get_sizes().max())) / 2 for collection in axes.collections
                 if isinstance(collection, PathCollection) and len(collection.get_sizes()))
    clearance = max(radii, default=0) * figure.dpi / 72 + 3
    legend_size = TEXT_SIZES_PT[size]["legend"]
    locations = ("upper center", "upper right", "upper left", "lower right", "lower left",
                 "lower center", "center right", "center left")
    for columns in range(min(3, len(handles)), 0, -1) if placement == "auto" else ():
        for location in locations:
            legend = axes.legend(loc=location, ncol=columns, frameon=True, framealpha=1,
                                 facecolor="white", edgecolor="#777777", fontsize=legend_size)
            figure.canvas.draw()
            box = legend.get_window_extent(figure.canvas.get_renderer())
            fits = axes_box.contains(*box.p0) and axes_box.contains(*box.p1)
            hits = int(np.count_nonzero((points[:, 0] >= box.x0 - clearance) & (points[:, 0] <= box.x1 + clearance)
                                       & (points[:, 1] >= box.y0 - clearance) & (points[:, 1] <= box.y1 + clearance)))
            if fits and hits == 0:
                return
            legend.remove()
    if SIZES_MM[size][0] <= 90:
        warnings.warn("Legend moved outside the single-column plot; consider --size double to preserve plot area.",
                      stacklevel=2)
    if _place_outside_legend(figure, axes, legend_size):
        return
    raise ValueError("Legend does not fit this preset; select a larger size or simplify labels.")


def _copy_identity(source, target) -> None:
    if isinstance(source, PathCollection):
        target.set_sizes(source.get_sizes())
        target.set_facecolor(source.get_facecolor())
        target.set_edgecolor(source.get_edgecolor())
        target.set_linewidth(source.get_linewidth())
        target.set_alpha(source.get_alpha())
    elif isinstance(source, BarContainer):
        return
    else:
        target.set_color(source.get_color())
        target.set_linestyle(getattr(source, "_scientific_linestyle", source.get_linestyle()))
        target.set_linewidth(source.get_linewidth())
        target.set_marker(source.get_marker())
        target.set_markersize(source.get_markersize())
        target.set_markerfacecolor(source.get_markerfacecolor())
        target.set_markeredgecolor(source.get_markeredgecolor())
        target.set_markeredgewidth(source.get_markeredgewidth())


def _sync_legend(axes) -> None:
    legend = axes.get_legend()
    if legend is None:
        return
    handles, _ = axes.get_legend_handles_labels()
    for source, target in zip(handles, legend.legend_handles):
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


def _check_text_layout(figure: mpl.figure.Figure) -> None:
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for panel_axes in figure.axes:
        text_items = [panel_axes.title, panel_axes.xaxis.label, panel_axes.yaxis.label]
        legend = panel_axes.get_legend()
        if legend is not None:
            box = legend.get_window_extent(renderer)
            if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
                raise ValueError("Legend is clipped by this size preset.")
        for axis, limits in ((panel_axes.xaxis, panel_axes.get_xlim()),
                             (panel_axes.yaxis, panel_axes.get_ylim())):
            low, high = sorted(limits)
            text_items.append(axis.get_offset_text())
            text_items.extend(tick.label1 for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks())
                              if low <= tick.get_loc() <= high)
        text_items.extend(text for text in panel_axes.texts if getattr(text, "_scientific_panel_letter", False))
        for text_item in text_items:
            if not text_item.get_visible() or not text_item.get_text():
                continue
            box = text_item.get_window_extent(renderer)
            if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
                raise ValueError("A label is clipped by this size preset; use a larger preset or shorter labels.")
    for legend in figure.legends:
        box = legend.get_window_extent(renderer)
        if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
            raise ValueError("Legend is clipped by this size preset.")


def _series_options(values: list, kind: str, series_styles: dict | None,
                    line_width: float | None, marker_size: float | None) -> dict:
    if series_styles is not None and not isinstance(series_styles, dict):
        raise ValueError("series_styles must map string series labels to style objects.")
    styles = series_styles or {}
    labels = {label for label, _ in values}
    if len(labels) != len(values):
        raise ValueError("Series labels are ambiguous after string conversion; use unique string labels.")
    if styles.keys() - labels:
        raise ValueError(f"Unknown series_styles labels: {styles.keys() - labels}")
    if kind == "mixed" and styles.keys() != labels:
        raise ValueError("mixed requires an explicit kind for every series in series_styles.")
    result = {}
    for label, _ in values:
        style = styles.get(label, {})
        if not isinstance(style, dict) or style.keys() - {"kind", "linestyle", "marker", "color", "line_width", "marker_size"}:
            raise ValueError(f"Invalid style keys for series {label!r}.")
        series_kind = style.get("kind", kind)
        if series_kind not in SERIES_KINDS or (kind != "mixed" and series_kind != kind):
            raise ValueError("Per-series kind changes require kind='mixed'; native kinds keep their semantics.")
        if series_kind == "line" and "marker" in style:
            raise ValueError("line series cannot specify a marker; use point-line or mixed explicitly.")
        if series_kind != "scatter" and style.get("linestyle", "-") in (None, "", "None", "none", " "):
            raise ValueError("Connected series require a visible linestyle.")
        if series_kind != "line" and style.get("marker", "o") in (None, "", "None", "none", " "):
            raise ValueError("point-line and scatter require visible markers.")
        if series_kind == "scatter" and "linestyle" in style:
            raise ValueError("scatter series cannot specify a connecting linestyle.")
        for key, applicable in (("line_width", series_kind != "scatter"),
                                ("marker_size", series_kind != "line")):
            override = style.get(key)
            if override is None:
                continue
            numeric = isinstance(override, (int, float)) and not isinstance(override, bool) and np.isfinite(override)
            if key == "line_width":
                allowed = numeric and LINE_WIDTH_MIN_PT <= float(override) <= LINE_WIDTH_MAX_PT
                limit = f"{LINE_WIDTH_MIN_PT:g} to {LINE_WIDTH_MAX_PT:g}"
            else:
                allowed = numeric and 0 < float(override) <= 20
                limit = "20"
            if not applicable or not allowed:
                raise ValueError(f"Invalid {key} for series {label!r}; allowed range is {limit} pt.")
        result[label] = {**style, "kind": series_kind,
                         "line_width": style.get("line_width", line_width),
                         "marker_size": style.get("marker_size", marker_size)}
        if isinstance(style.get("linestyle"), list):
            if len(style["linestyle"]) != 2 or not isinstance(style["linestyle"][1], list):
                raise ValueError("JSON dash patterns must be [offset, [on, off, ...]] in points.")
            result[label]["linestyle"] = (style["linestyle"][0], tuple(style["linestyle"][1]))
    return result


def _draw_series(axes, x_values, y_values, label, style, index, color):
    series_kind = style["kind"]
    color = style.get("color", color)
    marker = style.get("marker", MARKERS[index % len(MARKERS)])
    if series_kind == "scatter":
        artist = axes.scatter(x_values, y_values, label=label or None, s=24, marker=marker,
                              color=color, edgecolor="#333333", linewidth=0.35, zorder=3)
    else:
        linestyle = (LINESTYLES[(index // len(MARKERS)) % len(LINESTYLES)]
                     if series_kind == "point-line" else LINESTYLES[index % len(LINESTYLES)])
        linestyle = style.get("linestyle", linestyle)
        artist, = axes.plot(x_values, y_values, label=label or None, color=color,
                            linestyle=linestyle, linewidth=1.5,
                            marker=marker if series_kind == "point-line" else None,
                            markersize=6.2, markerfacecolor=color, markeredgecolor="white",
                            markeredgewidth=0.9)
        artist._scientific_linestyle = linestyle
    artist._scientific_style = style
    artist._scientific_identity = (
        series_kind,
        colors.to_hex(color),
        None if series_kind == "scatter" else str(artist.get_linestyle()),
        None if series_kind == "line" else str(marker),
    )
    return artist


def _comparison_errors(values: list, x: str, y: str, error: dict | None) -> tuple[list, dict]:
    if error is None:
        return [], {}
    if not isinstance(error, dict) or error.keys() - {"reference", "definition", "interpolation", "zero_reference", "ylabel"}:
        raise ValueError("error must specify reference, definition and optional interpolation/zero_reference.")
    reference = error.get("reference")
    definition = error.get("definition")
    interpolation = error.get("interpolation", "none")
    if definition not in ("signed", "absolute", "relative") or interpolation not in ("none", "linear"):
        raise ValueError("error definition must be signed/absolute/relative; interpolation must be none/linear.")
    if error.get("zero_reference", "raise") != "raise":
        raise ValueError("The only zero_reference policy is 'raise'; no zero values are omitted or replaced.")
    groups = dict(values)
    if reference not in groups or len(groups) < 2:
        raise ValueError("error reference must name a plotted series with at least one comparison series.")
    ref_x, ref_y = _numeric(groups[reference], x), _numeric(groups[reference], y)
    comparisons = []
    records = []
    for label, subset in values:
        if label == reference:
            continue
        coordinates, observed = _numeric(subset, x), _numeric(subset, y)
        method = "exact"
        if np.array_equal(coordinates, ref_x):
            expected = ref_y
        elif interpolation == "none":
            raise ValueError(f"Coordinate mismatch for {label!r}; explicitly request interpolation='linear' if appropriate.")
        else:
            if len(ref_x) < 2 or not (np.diff(ref_x) > 0).all():
                raise ValueError("Linear interpolation requires strictly increasing unique reference coordinates; no sorting is applied.")
            if (coordinates < ref_x[0]).any() or (coordinates > ref_x[-1]).any():
                raise ValueError("Interpolation would extrapolate beyond reference coordinates; refused.")
            expected = np.interp(coordinates, ref_x, ref_y)
            method = "linear (data coordinates; no extrapolation)"
        differences = observed - expected
        if definition == "absolute":
            differences = np.abs(differences)
        elif definition == "relative":
            if (expected == 0).any():
                raise ValueError(f"Relative error for {label!r} has a zero reference value; zero_reference='raise'.")
            differences = differences / np.abs(expected)
        if not np.isfinite(differences).all():
            raise ValueError("Computed error contains non-finite values; refused.")
        comparisons.append((label, coordinates, differences))
        records.append({"series": label, "method": method, "x": coordinates.tolist(), "error": differences.tolist()})
    formula = {"signed": "y - reference", "absolute": "abs(y - reference)",
               "relative": "(y - reference) / abs(reference)"}[definition]
    return comparisons, {"reference": reference, "definition": definition, "formula": formula,
                         "interpolation": interpolation, "zero_reference": "raise", "comparisons": records}


def _error_magnitudes(frame: pd.DataFrame, value, name: str) -> tuple[np.ndarray, str]:
    """Non-negative magnitudes in row order. Nothing is rescaled or imputed."""
    if isinstance(value, str):
        if value not in frame.columns:
            raise ValueError(f"Error bar column {value!r} is missing.")
        values = _numeric(frame, value)
        source = value
    elif isinstance(value, pd.Series):
        if not value.index.equals(frame.index):
            raise ValueError(f"Error bar {name} Series must use the same row index, without reordering.")
        try:
            values = value.to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Error bar {name} must be numeric.") from exc
        if not np.isfinite(values).all():
            raise ValueError(f"Error bar {name} contains non-finite values.")
        source = "array"
    elif isinstance(value, (bool, np.bool_)):
        raise ValueError(f"Error bar {name} must be a column, a constant, or one magnitude per row.")
    elif isinstance(value, (int, float, np.integer, np.floating)):
        if not np.isfinite(value) or float(value) < 0:
            raise ValueError(f"Error bar {name} must be a finite non-negative magnitude.")
        values = np.full(len(frame), float(value))
        source = "constant"
    else:
        try:
            values = np.asarray(value, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Error bar {name} must be a column, a constant, or one magnitude per row.") from exc
        if values.ndim == 0:
            if not np.isfinite(values) or float(values) < 0:
                raise ValueError(f"Error bar {name} must be a finite non-negative magnitude.")
            values = np.full(len(frame), float(values))
            source = "constant"
        elif values.shape != (len(frame),):
            raise ValueError(f"Error bar {name} must provide one magnitude per row, in the current row order.")
        elif not np.isfinite(values).all():
            raise ValueError(f"Error bar {name} contains non-finite values.")
        else:
            source = "array"
    if np.any(values < 0):
        raise ValueError(f"Error bar {name} contains a negative magnitude; supply magnitudes, not signed offsets.")
    return values, source


def _resolve_error_bars(frame: pd.DataFrame, error_bars: dict | None, *, x: str | None, y: str | None,
                        kind: str, xscale: str, yscale: str) -> dict | None:
    if error_bars is None:
        return None
    if not isinstance(error_bars, dict):
        raise ValueError("error_bars must be a mapping of magnitudes and a definition.")
    unknown = set(error_bars) - _ERRORBAR_KEYS
    if unknown:
        raise ValueError(f"Unknown error_bars keys: {sorted(unknown)}")
    if kind not in (*SERIES_KINDS, "mixed", "bar"):
        raise ValueError("Error bars apply to line, point-line, scatter, mixed and bar plots.")
    definition = error_bars.get("definition")
    if not isinstance(definition, str) or not definition.strip():
        raise ValueError("error_bars requires definition describing the magnitudes, such as sample standard deviation.")
    directions = {}
    sources = {}
    for axis_name in ("x", "y"):
        symmetric = error_bars.get(axis_name)
        lower = error_bars.get(f"{axis_name}_lower")
        upper = error_bars.get(f"{axis_name}_upper")
        if symmetric is not None and (lower is not None or upper is not None):
            raise ValueError(f"Use either symmetric {axis_name} or {axis_name}_lower/{axis_name}_upper, not both.")
        if (lower is None) != (upper is None):
            raise ValueError(f"{axis_name} error bars need both lower and upper magnitudes.")
        if symmetric is None and lower is None:
            continue
        if axis_name == "x" and kind == "bar":
            raise ValueError("Bar plots accept y error bars only; x categories are not numeric positions.")
        column = x if axis_name == "x" else y
        if not isinstance(column, str):
            raise ValueError(f"{axis_name} error bars require the plotted {axis_name} column.")
        if symmetric is not None:
            lower_values, source = _error_magnitudes(frame, symmetric, axis_name)
            upper_values = lower_values
            mode = "symmetric"
            sources[axis_name] = source
        else:
            lower_values, lower_source = _error_magnitudes(frame, lower, f"{axis_name}_lower")
            upper_values, upper_source = _error_magnitudes(frame, upper, f"{axis_name}_upper")
            mode = "asymmetric"
            sources[axis_name] = {"lower": lower_source, "upper": upper_source}
        data = _numeric(frame, column)
        scale = xscale if axis_name == "x" else yscale
        if scale == "log" and np.any(data - lower_values <= 0):
            raise ValueError(
                f"A {axis_name} error bar reaches a non-positive value on a log axis; "
                "no whiskers were clipped or removed.")
        for side, magnitudes in (("lower", lower_values), ("upper", upper_values)):
            reserved = f"__scientific_{axis_name}_{side}"
            if reserved in frame.columns:
                raise ValueError(f"Column {reserved} is reserved for error bars.")
            frame[reserved] = magnitudes
        directions[axis_name] = mode
    if not directions:
        raise ValueError("error_bars needs an x or y magnitude.")
    capsize = error_bars.get("capsize", ERRORBAR_CAPSIZE_PT)
    elinewidth = error_bars.get("elinewidth", ERRORBAR_ELINEWIDTH_PT)
    for label, value, maximum in (("capsize", capsize, 8), ("elinewidth", elinewidth, 3)):
        if (isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating))
                or not np.isfinite(value) or not 0 < float(value) <= maximum):
            raise ValueError(f"error_bars {label} must be a positive finite value up to {maximum} pt.")
    return {
        "definition": definition.strip(),
        "capsize_pt": float(capsize),
        "elinewidth_pt": float(elinewidth),
        "x": None if "x" not in directions else {"mode": directions["x"], "source": sources["x"]},
        "y": None if "y" not in directions else {"mode": directions["y"], "source": sources["y"]},
        "directions": directions,
    }


def _axis_errors(frame: pd.DataFrame, axis_name: str, state: dict) -> np.ndarray | None:
    if axis_name not in state["directions"]:
        return None
    return np.vstack([
        frame[f"__scientific_{axis_name}_lower"].to_numpy(dtype=float),
        frame[f"__scientific_{axis_name}_upper"].to_numpy(dtype=float),
    ])


def _errorbar_record(label: str, x_values, y_values, yerr, xerr) -> dict:
    record = {"series": label,
              "x": np.asarray(x_values, dtype=float).tolist(),
              "y": np.asarray(y_values, dtype=float).tolist()}
    if yerr is not None:
        record["y_lower"] = np.asarray(yerr[0], dtype=float).tolist()
        record["y_upper"] = np.asarray(yerr[1], dtype=float).tolist()
    if xerr is not None:
        record["x_lower"] = np.asarray(xerr[0], dtype=float).tolist()
        record["x_upper"] = np.asarray(xerr[1], dtype=float).tolist()
    return record


def _artist_color(artist):
    if isinstance(artist, PathCollection):
        painted = artist.get_facecolor()
        if len(painted) == 0:
            raise ValueError("Scatter series has no face color for error bars.")
        return painted[0]
    return artist.get_color()


def _draw_errorbars(axes, x_values, y_values, *, yerr, xerr, color, capsize: float,
                    elinewidth: float, zorder: float) -> None:
    container = axes.errorbar(
        np.asarray(x_values, dtype=float), np.asarray(y_values, dtype=float),
        yerr=yerr, xerr=xerr, fmt="none", ecolor=color, elinewidth=elinewidth,
        capsize=capsize, capthick=elinewidth, zorder=zorder, label="_nolegend_",
    )
    for artist in container.get_children():
        artist._scientific_errorbar = True
        artist.set_label("_nolegend_")
        artist.set_zorder(zorder)
        artist.set_color(color)
        if not isinstance(artist, LineCollection):
            artist.set_markeredgecolor(color)
            artist.set_markerfacecolor(color)


def _finding(severity: str, rule: str, message: str, measured=None, expected=None) -> dict:
    finding = {"severity": severity, "rule": rule, "message": message, "snapshot_date": SNAPSHOT_DATE}
    if measured is not None:
        finding["measured"] = measured
    if expected is not None:
        finding["expected"] = expected
    return finding


def resolve_size(size: str | None, journal: str) -> str:
    """Pick a named width. An explicit width is never replaced by the journal."""
    if journal not in JOURNALS:
        raise ValueError(f"journal must be one of: {', '.join(JOURNALS)}.")
    if size == "multipanel":
        raise ValueError("size 'multipanel' was removed; use render_multipanel().")
    if size is None:
        size = JOURNALS[journal]["default_size"]
    if size not in SIZES_MM:
        raise ValueError(f"Unknown size {size!r}. Use one of: {', '.join(SIZES_MM)}.")
    return size


def resolve_height(size: str, height_mm: float | None) -> float:
    if height_mm is None:
        return SIZES_MM[size][1]
    if isinstance(height_mm, bool) or not isinstance(height_mm, (int, float, np.floating)) or not np.isfinite(height_mm):
        raise ValueError("height_mm must be a finite number from 40 to 210.")
    if not HEIGHT_MIN_MM <= float(height_mm) <= HEIGHT_MAX_MM:
        raise ValueError("height_mm must be between 40 and 210 mm.")
    return float(height_mm)


def resolve_formats(formats) -> tuple[str, ...]:
    chosen = tuple(dict.fromkeys(formats if formats is not None else ("jpeg",)))
    if not chosen:
        raise ValueError("At least one format is required.")
    rejected = [name for name in chosen if name in REJECTED_FORMATS]
    if rejected:
        raise ValueError("Only JPEG and TIFF can be exported; PNG, SVG, PDF and EPS are not supported. "
                         f"Refused: {', '.join(rejected)}.")
    unknown = [name for name in chosen if name not in FORMATS]
    if unknown:
        raise ValueError(f"Formats must be jpeg or tiff, not {', '.join(unknown)}.")
    return chosen


def submission_tiff_dpi(journal: str, heatmap: bool) -> int:
    preset = JOURNALS[journal]
    return preset["tiff_heatmap_dpi"] if heatmap else preset["tiff_line_dpi"]


def resolve_dpi(dpi: int | None, formats: tuple[str, ...], journal: str, heatmap: bool) -> dict[str, int]:
    if dpi is not None and (isinstance(dpi, bool) or not isinstance(dpi, (int, np.integer)) or not 72 <= int(dpi) <= 1200):
        raise ValueError("DPI must be between 72 and 1200.")
    resolved = {}
    for name in formats:
        if name == "jpeg" or dpi is not None:
            resolved[name] = 300 if dpi is None else int(dpi)
        else:
            resolved[name] = submission_tiff_dpi(journal, heatmap)
    return resolved


def _log_spans(figure: mpl.figure.Figure) -> list[float]:
    spans = []
    for axes in figure.axes:
        for axis, limits in ((axes.xaxis, axes.get_xlim()), (axes.yaxis, axes.get_ylim())):
            if axis.get_scale() != "log":
                continue
            low, high = sorted(float(value) for value in limits)
            if low > 0 and high > 0:
                spans.append(abs(np.log10(high) - np.log10(low)))
    return spans


def _near(width: float, candidates: tuple[float, ...]) -> bool:
    return any(abs(width - candidate) < 0.2 for candidate in candidates)


def review_figure(figure: mpl.figure.Figure, *, journal: str | None = None) -> list[dict]:
    """Report differences from the dated journal snapshot. Never a compliance verdict."""
    metadata = getattr(figure, "scientific_metadata", {}) or {}
    journal = journal or metadata.get("journal") or "elsevier"
    if journal not in JOURNALS:
        raise ValueError(f"journal must be one of: {', '.join(JOURNALS)}.")
    preset = JOURNALS[journal]
    findings = []
    width = float(metadata.get("width_mm", figure.get_figwidth() * 25.4))
    height = float(metadata.get("height_mm", figure.get_figheight() * 25.4))
    if not _near(width, preset["widths_mm"]):
        findings.append(_finding(
            "warn", "width",
            f"{width:g} mm is outside the {journal} snapshot widths "
            f"{', '.join(f'{item:g}' for item in preset['widths_mm'])} mm. The requested width was kept.",
            measured=width, expected=list(preset["widths_mm"])))
    if journal == "jfm":
        findings.append(_finding(
            "info", "width",
            "JFM is a single-column journal. The 2026-10-19 instructions did not state a millimetre text width, "
            "so 90 mm is used until that width is confirmed.",
            measured=width, expected=90))
        findings.append(_finding(
            "info", "color",
            "The JFM instructions file specifies RGB, while the Cambridge artwork guide specifies CMYK. "
            "This figure stays RGB and is not converted.",
            measured="RGB", expected="RGB and CMYK disagree"))
    if journal == "pof" and _near(width, (170,)):
        findings.append(_finding(
            "info", "width",
            "170 mm is about 0.1 mm wider than AIP's stated 6.69 in (169.9 mm).",
            measured=170, expected=169.9))
    if height > HEIGHT_MAX_MM + 0.05 or height < HEIGHT_MIN_MM - 0.05:
        findings.append(_finding(
            "warn", "height",
            f"Figure height {height:g} mm is outside 40–210 mm.",
            measured=height, expected=[HEIGHT_MIN_MM, HEIGHT_MAX_MM]))
    if metadata.get("height_clamped"):
        findings.append(_finding(
            "warn", "aspect",
            "The 4:3 panel height exceeded 210 mm, so the figure height was stopped at 210 mm.",
            measured=metadata.get("target_height_mm"), expected=HEIGHT_MAX_MM))
    elif not metadata.get("multipanel") and metadata.get("size") in SIZES_MM and abs(height - SIZES_MM[metadata["size"]][1]) > 0.05:
        findings.append(_finding(
            "info", "aspect",
            "Height leaves the 4:3 preset. Record why 4:3 could not show the data.",
            measured=height, expected=SIZES_MM[metadata["size"]][1]))
    sizes = []
    for axes in figure.axes:
        candidates = [axes.xaxis.label, axes.yaxis.label, *axes.get_xticklabels(), *axes.get_yticklabels()]
        legend = axes.get_legend()
        if legend is not None:
            candidates.extend(legend.get_texts())
        for text in candidates:
            if text.get_visible() and text.get_text().strip():
                sizes.append(float(text.get_fontsize()))
    for legend in figure.legends:
        sizes.extend(float(text.get_fontsize()) for text in legend.get_texts() if text.get_text().strip())
    if sizes and min(sizes) + 1e-6 < preset["min_type_pt"]:
        findings.append(_finding(
            "warn", "type",
            f"Smallest text is {min(sizes):g} pt, below the {journal} snapshot minimum of {preset['min_type_pt']} pt.",
            measured=min(sizes), expected=preset["min_type_pt"]))
    for axes in figure.axes:
        for line in axes.lines:
            if getattr(line, "_scientific_errorbar", False):
                continue
            width_pt = float(line.get_linewidth())
            if width_pt < LINE_WIDTH_MIN_PT - 1e-6 or width_pt > LINE_WIDTH_MAX_PT + 1e-6:
                findings.append(_finding(
                    "warn", "line_width",
                    f"A data line is {width_pt:g} pt, outside 0.5–1.5 pt.",
                    measured=width_pt, expected=[LINE_WIDTH_MIN_PT, LINE_WIDTH_MAX_PT]))
                break
    if journal == "jfm":
        findings.append(_finding(
            "info", "grid",
            "Minor gridlines stay at 0.45 pt, slightly under the JFM 0.5 pt minimum. They were not changed.",
            measured=0.45, expected=0.5))
    spans = _log_spans(figure)
    if any(span >= 6 for span in spans):
        findings.append(_finding(
            "info", "grid",
            "A log axis spans 6 or more decades. The minor grid stays on; turn it off only if it covers the data.",
            measured=max(spans), expected=6))
    if any(span >= 4 for span in spans) and metadata.get("size") in SIZES_MM and abs(height - SIZES_MM[metadata["size"]][1]) <= 0.05:
        findings.append(_finding(
            "info", "aspect",
            "A log axis spans at least 4 decades on a 4:3 canvas. Set height_mm if that ratio cannot show the data.",
            measured=max(spans), expected=4))
    formats = list(metadata.get("formats") or [])
    if journal == "jfm" and "jpeg" in formats:
        findings.append(_finding(
            "warn", "format",
            "JFM asks for EPS or TIFF. This skill cannot write EPS. JPEG is not a JFM submission file; request TIFF instead.",
            measured=formats, expected=["tiff"]))
    dpi_by_format = metadata.get("dpi_by_format") or {}
    if "tiff" in dpi_by_format:
        required = submission_tiff_dpi(journal, bool(metadata.get("heatmap")))
        used = int(dpi_by_format["tiff"])
        if used < required:
            findings.append(_finding(
                "warn", "dpi",
                f"TIFF is {used} dpi, below the {journal} snapshot of {required} dpi.",
                measured=used, expected=required))
    if metadata.get("multipanel"):
        present = [text.get_text() for axes in figure.axes for text in axes.texts]
        present.extend(text.get_text() for text in figure.texts)
        missing = [letter for letter in metadata.get("panel_letters", []) if letter not in present]
        if missing:
            findings.append(_finding(
                "warn", "panel",
                f"Missing panel letters: {', '.join(missing)}.",
                measured=present, expected=metadata.get("panel_letters")))
        labeled = any(label for axes in figure.axes for label in axes.get_legend_handles_labels()[1])
        if metadata.get("legend_mode") == "shared" and labeled:
            count = len(figure.legends) + sum(axes.get_legend() is not None for axes in figure.axes)
            if count != 1:
                findings.append(_finding(
                    "warn", "panel",
                    "A shared multi-panel legend should be the only legend.",
                    measured=count, expected=1))
    figure.scientific_review = findings
    return findings


def _export_figure(figure, output, formats, dpi_by_format, metadata, write_metadata: bool) -> list[Path]:
    if output is None:
        return []
    target = Path(output)
    if target.suffix.lower() in {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".svg", ".pdf", ".eps"}:
        target = target.with_suffix("")
    target.parent.mkdir(parents=True, exist_ok=True)
    exported = []
    for format_name in formats:
        destination = target.with_suffix(EXPORT_SUFFIX[format_name])
        save_kwargs = {"format": format_name, "dpi": dpi_by_format[format_name], "facecolor": "white"}
        if format_name == "jpeg":
            save_kwargs["pil_kwargs"] = {"quality": JPEG_QUALITY, "subsampling": 0}
        figure.savefig(destination, **save_kwargs)
        exported.append(destination)
    if write_metadata:
        target.with_name(target.stem + "_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return exported


def _place_panel_letter(axes: mpl.axes.Axes, letter: str, fontsize: float) -> None:
    text = axes.text(-0.04, 1.02, letter, transform=axes.transAxes, ha="right", va="bottom",
                     fontsize=fontsize, fontweight="bold", clip_on=False, zorder=6)
    text._scientific_panel_letter = True
    axes.figure.canvas.draw()
    box = text.get_window_extent(axes.figure.canvas.get_renderer())
    figure = axes.figure
    if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
        text.set_position((0.04, 0.96))
        text.set_ha("left")
        text.set_va("top")


def _place_shared_legend(figure: mpl.figure.Figure, axes_list: list, legend_size: float) -> None:
    handles = []
    labels = []
    seen = {}
    for axes in axes_list:
        for handle, label in zip(*axes.get_legend_handles_labels()):
            if not label or label.startswith("_"):
                continue
            identity = getattr(handle, "_scientific_identity", None)
            if label in seen and seen[label] != identity:
                raise ValueError(f"Series {label!r} has different styles in different panels.")
            if label in seen:
                continue
            seen[label] = identity
            handles.append(handle)
            labels.append(label)
        existing = axes.get_legend()
        if existing is not None:
            existing.remove()
    if not handles:
        return
    legend = figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
                           ncol=min(len(handles), 4), frameon=True, framealpha=1, facecolor="white",
                           edgecolor="#777777", fontsize=legend_size)
    figure.canvas.draw()
    box = legend.get_window_extent(figure.canvas.get_renderer())
    pad = 6 * figure.dpi / 72
    top = (box.y0 - pad) / figure.bbox.height
    if top < 0.45:
        legend.remove()
        raise ValueError("Legend does not fit this preset; select a larger size or simplify labels.")
    figure.subplots_adjust(top=min(figure.subplotpars.top, max(top, 0.5)))
    figure.canvas.draw()
    for source, target in zip(handles, legend.legend_handles):
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


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
    size: str | None = None,
    output: str | Path | None = None,
    formats: tuple[str, ...] | list[str] | None = None,
    dpi: int | None = None,
    line_width: float | None = None,
    marker_size: float | None = None,
    xscale: str = "linear",
    yscale: str = "linear",
    series_styles: dict | None = None,
    error: dict | None = None,
    error_bars: dict | None = None,
    legend: str = "auto",
    journal: str = "elsevier",
    height_mm: float | None = None,
    host_axes: mpl.axes.Axes | None = None,
    host_error_axes: mpl.axes.Axes | None = None,
    apply_layout: bool = True,
    draw_legend: bool = True,
) -> tuple[mpl.figure.Figure, mpl.axes.Axes, list[Path]]:
    """Draw without changing input data; return figure, axes and exported paths."""
    if kind not in KINDS or group_kind not in ("auto", "ordered", "categorical"):
        raise ValueError("Unknown plot kind or group kind.")
    size = resolve_size(size, journal)
    if xscale not in ("linear", "log") or yscale not in ("linear", "log"):
        raise ValueError("xscale and yscale must be linear or log.")
    if legend not in ("auto", "outside"):
        raise ValueError("legend must be auto or outside.")
    if error is not None and kind not in (*SERIES_KINDS, "mixed"):
        raise ValueError("Error panels require line, point-line, scatter or mixed.")
    if kind not in (*SERIES_KINDS, "mixed") and (xscale != "linear" or yscale != "linear" or series_styles is not None):
        raise ValueError("Axis scales and series_styles apply to line, point-line, scatter and mixed only.")
    chosen_formats = resolve_formats(formats)
    dpi_by_format = resolve_dpi(dpi, chosen_formats, journal, kind == "heatmap")
    if line_width is not None and (kind not in ("point-line", "line", "mixed") or isinstance(line_width, bool)
                                   or not np.isfinite(line_width)
                                   or not LINE_WIDTH_MIN_PT <= float(line_width) <= LINE_WIDTH_MAX_PT):
        raise ValueError(f"line_width must be between {LINE_WIDTH_MIN_PT:g} and {LINE_WIDTH_MAX_PT:g} pt "
                         "for point-line, line and mixed.")
    if marker_size is not None and (kind not in ("point-line", "scatter", "mixed") or isinstance(marker_size, bool)
                                    or not np.isfinite(marker_size) or not 0 < float(marker_size) <= 20):
        raise ValueError("marker_size must be a positive finite value up to 20 for point-line, scatter and mixed.")
    face = resolve_font(font)
    frame = _frame(data, kind)
    if kind in (*SERIES_KINDS, "mixed"):
        _required(frame, x, y)
        for column, scale in ((x, xscale), (y, yscale)):
            numeric = _numeric(frame, column)
            if scale == "log" and np.any(numeric <= 0):
                raise ValueError(f"Log axis column {column!r} contains non-positive values; no rows were removed.")
        ordered = _ordered_groups(frame, group, group_kind)
        values = _groups(frame, group, ordered)
        styles = _series_options(values, kind, series_styles, line_width, marker_size)
        comparisons, error_metadata = _comparison_errors(values, x, y, error)
    error_bar_state = _resolve_error_bars(frame, error_bars, x=x, y=y, kind=kind, xscale=xscale, yscale=yscale)
    text_sizes = TEXT_SIZES_PT[size]
    with mpl.rc_context({"font.family": face, "font.size": text_sizes["tick"],
                         "axes.labelsize": text_sizes["label"], "axes.titlesize": text_sizes["title"],
                         "xtick.labelsize": text_sizes["tick"], "ytick.labelsize": text_sizes["tick"],
                         "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "savefig.facecolor": "white"}):
        width_mm, _preset_height = SIZES_MM[size]
        resolved_height = resolve_height(size, height_mm)
        hosted = host_axes is not None
        if hosted:
            axes = host_axes
            figure = axes.figure
            error_axes = host_error_axes
            if (error is not None) != (error_axes is not None):
                raise ValueError("host_error_axes is required exactly when a panel draws a reference-error panel.")
        else:
            figure, panels = plt.subplots(2 if error is not None else 1, sharex=error is not None,
                                          figsize=(width_mm / 25.4, resolved_height / 25.4), dpi=120,
                                          gridspec_kw={"height_ratios": [2.4, 1]} if error is not None else None)
            axes = panels[0] if error is not None else panels
            error_axes = panels[1] if error is not None else None
            figure.scientific_error_axes = error_axes
        metadata = {
            "xscale": xscale, "yscale": yscale,
            "size": size, "journal": journal,
            "width_mm": width_mm, "height_mm": resolved_height,
            "formats": list(chosen_formats), "dpi_by_format": dpi_by_format,
            "heatmap": kind == "heatmap",
            "error": error_metadata if error is not None else None,
            "error_bars": None if error_bar_state is None else {
                "definition": error_bar_state["definition"],
                "capsize_pt": error_bar_state["capsize_pt"],
                "elinewidth_pt": error_bar_state["elinewidth_pt"],
                "x": error_bar_state["x"],
                "y": error_bar_state["y"],
                "series": [],
            },
        }
        if hosted:
            axes._scientific_panel = metadata
        else:
            figure.scientific_metadata = metadata
        axes.set_xscale(xscale)
        axes.set_yscale(yscale)
        _style_axes(axes, kind)
        artists = {}
        error_artists = {}
        error_bar_records = []

        def draw_uncertainty(x_values, y_values, yerr, xerr, color, label, zorder) -> None:
            if error_bar_state is None or (yerr is None and xerr is None):
                return
            _draw_errorbars(axes, x_values, y_values, yerr=yerr, xerr=xerr, color=color,
                            capsize=error_bar_state["capsize_pt"], elinewidth=error_bar_state["elinewidth_pt"],
                            zorder=zorder)
            error_bar_records.append(_errorbar_record(label, x_values, y_values, yerr, xerr))

        if kind in ("point-line", "line", "scatter", "bar", "mixed"):
            _required(frame, x, y)
            if kind in (*SERIES_KINDS, "mixed"):
                ordered = _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                limit = len(MARKERS) * len(LINESTYLES) if kind in ("point-line", "mixed") else len(LINESTYLES)
                if len(values) > limit:
                    raise ValueError("Too many series to distinguish in grayscale; divide them into panels.")
                palette = _palette(len(values), ordered)
                for index, (label, subset) in enumerate(values):
                    x_values, y_values = _numeric(subset, x), _numeric(subset, y)
                    artists[label] = _draw_series(axes, x_values, y_values, label, styles[label], index, palette[index])
                    if error_bar_state is not None:
                        artist = artists[label]
                        draw_uncertainty(x_values, y_values, _axis_errors(subset, "y", error_bar_state),
                                         _axis_errors(subset, "x", error_bar_state), _artist_color(artist), label,
                                         2.5 if isinstance(artist, PathCollection) else 1.5)
                if error_axes is not None:
                    error_axes.set_xscale(xscale)
                    _style_axes(error_axes, kind)
                    for label, coordinates, differences in comparisons:
                        index = next(index for index, (name, _) in enumerate(values) if name == label)
                        error_artists[label] = _draw_series(error_axes, coordinates, differences, label,
                                                           styles[label], index, palette[index])
                    error_axes.set_ylabel(error.get("ylabel", {"signed": "Signed error", "absolute": "Absolute error",
                                                               "relative": "Relative error (-)"}[error_metadata["definition"]]))
            else:
                _numeric(frame, y)
                ordered = _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                if len(values) > len(CATEGORICAL_COLORS):
                    raise ValueError("Too many bar series to distinguish in grayscale; divide them into panels.")
                if group is None:
                    if frame[x].duplicated().any():
                        raise ValueError("Repeated bar category; aggregate explicitly or specify --group.")
                    bars = axes.bar(frame[x].astype(str), frame[y], color=CATEGORICAL_COLORS[0],
                                    edgecolor="#333333", linewidth=0.65)
                    if error_bar_state is not None:
                        centers = [patch.get_x() + patch.get_width() / 2 for patch in bars]
                        heights = [patch.get_height() for patch in bars]
                        draw_uncertainty(centers, heights, _axis_errors(frame, "y", error_bar_state), None,
                                         "#333333", "", 3)
                else:
                    categories = list(pd.unique(frame[x]))
                    width = 0.8 / len(values)
                    palette = _palette(len(values), ordered)
                    for index, (label, subset) in enumerate(values):
                        if subset[x].duplicated().any():
                            raise ValueError("Repeated group/category; aggregate explicitly before plotting.")
                        positions = np.arange(len(categories)) - 0.4 + width * (index + 0.5)
                        indexed = subset.set_index(x)
                        heights = indexed[y].reindex(categories)
                        bars = axes.bar(positions, heights, width=width, label=label, color=palette[index],
                                        edgecolor="#333333", linewidth=0.65,
                                        hatch=("", "//", "..", "xx")[index % 4])
                        if error_bar_state is not None:
                            lower = indexed["__scientific_y_lower"].reindex(categories)
                            upper = indexed["__scientific_y_upper"].reindex(categories)
                            if heights.isna().any() or lower.isna().any() or upper.isna().any():
                                raise ValueError("Missing group/category for error bars; complete or aggregate the table explicitly.")
                            centers = [patch.get_x() + patch.get_width() / 2 for patch in bars]
                            plotted = [patch.get_height() for patch in bars]
                            yerr = np.vstack([lower.to_numpy(dtype=float), upper.to_numpy(dtype=float)])
                            draw_uncertainty(centers, plotted, yerr, None, "#333333", label, 3)
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
        label_axes = error_axes if error_axes is not None else axes
        label_axes.set_xlabel(xlabel if xlabel is not None else (x or ""))
        axes.set_ylabel(ylabel if ylabel is not None else (y or value or ""))
        if title:
            axes.set_title(title)
        if apply_layout:
            figure.tight_layout(pad=1.0)
            if kind in (*SERIES_KINDS, "mixed"):
                margins = figure.subplotpars
                figure.subplots_adjust(left=max(0.135, margins.left), right=min(0.91, margins.right),
                                       bottom=max(0.13, margins.bottom), top=min(0.95, margins.top))
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        if draw_legend:
            _place_legend(figure, axes, size, legend)
        figure.canvas.draw()
        for panel_axes in figure.axes:
            _adapt_log_ticks(panel_axes)
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        for label, artist in error_artists.items():
            _copy_identity(artists[label], artist)
        _sync_legend(axes)
        if error_bar_state is not None:
            metadata["error_bars"]["series"] = error_bar_records
        if artists:
            metadata["series"] = {
                label: {"kind": styles[label]["kind"],
                        "line_width_pt": None if isinstance(artist, PathCollection) else artist.get_linewidth(),
                        "marker_size_pt": float(np.sqrt(artist.get_sizes()[0])) if isinstance(artist, PathCollection)
                        else artist.get_markersize() if styles[label]["kind"] == "point-line" else None}
                for label, artist in artists.items()}
        for panel_axes in ((axes, error_axes) if hosted else figure.axes):
            if panel_axes is not None:
                _hide_edge_grids(panel_axes)
        if apply_layout:
            _check_text_layout(figure)
        exported = []
        if not hosted:
            figure.scientific_review = review_figure(figure, journal=journal)
            exported = _export_figure(figure, output, chosen_formats, dpi_by_format, metadata,
                                      error is not None or error_bar_state is not None)
        return figure, axes, exported


def _copy_matching_artists(source_axes, target_axes) -> None:
    sources = {}
    for artist in (*source_axes.lines, *source_axes.collections):
        label = artist.get_label()
        if label and not str(label).startswith("_"):
            sources[label] = artist
    for artist in (*target_axes.lines, *target_axes.collections):
        source = sources.get(artist.get_label())
        if source is not None:
            _copy_identity(source, artist)


def _sync_figure_legend(figure: mpl.figure.Figure) -> None:
    if not figure.legends:
        return
    legend = figure.legends[0]
    sources = {}
    for axes in figure.axes:
        for artist in (*axes.lines, *axes.collections):
            label = artist.get_label()
            if label and not str(label).startswith("_") and label not in sources:
                sources[label] = artist
    for target, text in zip(legend.legend_handles, legend.get_texts()):
        source = sources.get(text.get_text())
        if source is None:
            continue
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


def render_multipanel(
    panels: list[dict],
    *,
    ncols: int | None = None,
    size: str | None = None,
    journal: str = "elsevier",
    height_mm: float | None = None,
    sharex: bool = False,
    sharey: bool = False,
    legend: str = "shared",
    output: str | Path | None = None,
    formats: tuple[str, ...] | list[str] | None = None,
    dpi: int | None = None,
    font: str = "Arial",
) -> tuple[mpl.figure.Figure, list, list[Path]]:
    """Compose real panels on one journal-width canvas. Titles stay in the caption."""
    if not panels:
        raise ValueError("render_multipanel needs at least one panel.")
    if legend not in ("shared", "each", "none"):
        raise ValueError("Multipanel legend must be shared, each or none.")
    if journal not in JOURNALS:
        raise ValueError(f"journal must be one of: {', '.join(JOURNALS)}.")
    if size is None:
        size = {"elsevier": "double", "jfm": "single", "pof": "aip-double"}[journal]
    size = resolve_size(size, journal)
    width_mm = SIZES_MM[size][0]
    count = len(panels)
    if ncols is None:
        ncols = 2 if width_mm >= 140 and 2 <= count <= 4 else 1
    if isinstance(ncols, bool) or not isinstance(ncols, int) or not 1 <= ncols <= count:
        raise ValueError("ncols must be an integer from 1 through the panel count.")
    nrows = int(np.ceil(count / ncols))
    if height_mm is None:
        target_height = nrows * (width_mm / ncols) * 0.75 + PANEL_CHROME_MM
        resolved_height = min(max(target_height, HEIGHT_MIN_MM), HEIGHT_MAX_MM)
        height_clamped = target_height > HEIGHT_MAX_MM + 1e-6
    else:
        target_height = resolved_height = resolve_height(size, height_mm)
        height_clamped = False
    for panel in panels:
        if not isinstance(panel, dict) or "data" not in panel or "kind" not in panel:
            raise ValueError("Each panel needs data and kind.")
        if panel.get("title"):
            raise ValueError("Multi-panel figures do not draw an in-figure title; put it in the caption.")
    chosen_formats = resolve_formats(formats)
    heatmap = any(panel.get("kind") == "heatmap" for panel in panels)
    dpi_by_format = resolve_dpi(dpi, chosen_formats, journal, heatmap)
    face = resolve_font(font)
    text_sizes = TEXT_SIZES_PT[size]
    letters = [f"({chr(ord('a') + index)})" for index in range(count)]
    draw_keys = ("kind", "x", "y", "group", "value", "group_kind", "xlabel", "ylabel", "line_width",
                 "marker_size", "xscale", "yscale", "series_styles", "error", "error_bars", "legend")
    with mpl.rc_context({"font.family": face, "font.size": text_sizes["tick"],
                         "axes.labelsize": text_sizes["label"], "axes.titlesize": text_sizes["title"],
                         "xtick.labelsize": text_sizes["tick"], "ytick.labelsize": text_sizes["tick"],
                         "savefig.facecolor": "white"}):
        figure = plt.figure(figsize=(width_mm / 25.4, resolved_height / 25.4), dpi=120)
        figure.scientific_error_axes = None
        figure.scientific_metadata = {
            "multipanel": True, "size": size, "journal": journal,
            "width_mm": width_mm, "height_mm": resolved_height,
            "formats": list(chosen_formats), "dpi_by_format": dpi_by_format,
            "heatmap": heatmap, "legend_mode": legend, "panel_letters": letters,
            "height_clamped": height_clamped, "target_height_mm": target_height,
            "xscale": None, "yscale": None, "error": None, "error_bars": None,
        }
        grid = figure.add_gridspec(nrows, ncols, hspace=0.55, wspace=0.38)
        figure.subplots_adjust(left=0.16, right=0.97, bottom=0.16, top=0.90)
        created = []
        share_x_anchor = None
        share_y_anchor = None
        for index, panel in enumerate(panels):
            row, column = divmod(index, ncols)
            share_kwargs = {}
            if sharex and share_x_anchor is not None:
                share_kwargs["sharex"] = share_x_anchor
            if sharey and share_y_anchor is not None:
                share_kwargs["sharey"] = share_y_anchor
            if panel.get("error") is not None:
                sub = grid[row, column].subgridspec(2, 1, height_ratios=[2.4, 1], hspace=0.08)
                axes = figure.add_subplot(sub[0], **share_kwargs)
                error_axes = figure.add_subplot(sub[1], sharex=axes)
            else:
                axes = figure.add_subplot(grid[row, column], **share_kwargs)
                error_axes = None
            if share_x_anchor is None:
                share_x_anchor = axes
            if share_y_anchor is None:
                share_y_anchor = axes
            kwargs = {key: panel[key] for key in draw_keys if key in panel}
            render_plot(panel["data"], journal=journal, size=size, font=font, host_axes=axes,
                        host_error_axes=error_axes, apply_layout=False,
                        draw_legend=legend == "each", **kwargs)
            if sharex and row != nrows - 1:
                axes.tick_params(labelbottom=False)
                if error_axes is not None:
                    error_axes.tick_params(labelbottom=False)
                    error_axes.set_xlabel("")
                else:
                    axes.set_xlabel("")
            if sharey and column != 0:
                axes.tick_params(labelleft=False)
                axes.set_ylabel("")
            created.append((axes, error_axes, panel))
        for index, (axes, _error_axes, _panel) in enumerate(created):
            _place_panel_letter(axes, letters[index], text_sizes["title"])
        if legend == "shared":
            _place_shared_legend(figure, [item[0] for item in created], text_sizes["legend"])
        elif legend == "none":
            for axes in figure.axes:
                existing = axes.get_legend()
                if existing is not None:
                    existing.remove()
        figure.canvas.draw()
        for axes, error_axes, panel in created:
            _adapt_strokes(axes, panel["kind"], panel.get("line_width"), panel.get("marker_size"))
            if error_axes is not None:
                _copy_matching_artists(axes, error_axes)
        for panel_axes in figure.axes:
            _adapt_log_ticks(panel_axes)
            _hide_edge_grids(panel_axes)
        _sync_figure_legend(figure)
        _check_text_layout(figure)
        figure.scientific_review = review_figure(figure, journal=journal)
        exported = _export_figure(figure, output, chosen_formats, dpi_by_format, figure.scientific_metadata, False)
    return figure, [item[0] for item in created], exported


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


def _cli_error_bars(options, parser) -> dict | None:
    payload = {}
    for key, value in (("y", options.yerr), ("x", options.xerr),
                       ("y_lower", options.yerr_lower), ("y_upper", options.yerr_upper),
                       ("x_lower", options.xerr_lower), ("x_upper", options.xerr_upper)):
        if value is not None:
            payload[key] = value
    if options.errorbar_capsize is not None:
        payload["capsize"] = options.errorbar_capsize
    if options.errorbar_elinewidth is not None:
        payload["elinewidth"] = options.errorbar_elinewidth
    if options.errorbar_definition is not None:
        payload["definition"] = options.errorbar_definition
    if not payload:
        return None
    if not payload.keys() & {"x", "y", "x_lower", "x_upper", "y_lower", "y_upper"}:
        parser.error("error-bar cap size or definition requires --yerr/--xerr or a lower/upper pair")
    if "definition" not in payload:
        parser.error("--errorbar-definition is required when error bars are requested")
    return payload


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
    parser.add_argument("--size", choices=(*SIZES_MM, "multipanel"), default=None)
    parser.add_argument("--journal", choices=tuple(JOURNALS), default="elsevier")
    parser.add_argument("--height-mm", type=float, dest="height_mm")
    parser.add_argument("--format", action="append", dest="formats", choices=(*FORMATS, *REJECTED_FORMATS))
    parser.add_argument("--dpi", type=int, default=None)
    parser.add_argument("--line-width", type=float, help="Line stroke width in points (line and point-line)")
    parser.add_argument("--marker-size", type=float, help="Marker diameter in points (point-line and scatter)")
    parser.add_argument("--xscale", choices=("linear", "log"), default="linear")
    parser.add_argument("--yscale", choices=("linear", "log"), default="linear")
    parser.add_argument("--series-config", type=Path, help="JSON mapping of string series labels to styles; mixed requires kind for each")
    parser.add_argument("--legend", choices=("auto", "outside"), default="auto")
    parser.add_argument("--error-reference", help="Reference series label; adds a shared-x, linear-y error panel")
    parser.add_argument("--error-definition", choices=("signed", "absolute", "relative"))
    parser.add_argument("--error-interpolation", choices=("none", "linear"), default="none")
    parser.add_argument("--error-ylabel", help="Error-axis label, including original y units for signed/absolute error")
    parser.add_argument("--yerr", help="Symmetric y error-bar column; non-negative magnitude, not a computed statistic")
    parser.add_argument("--xerr", help="Symmetric x error-bar column; non-negative magnitude")
    parser.add_argument("--yerr-lower", help="Asymmetric y error bar, lower magnitude")
    parser.add_argument("--yerr-upper", help="Asymmetric y error bar, upper magnitude")
    parser.add_argument("--xerr-lower", help="Asymmetric x error bar, lower magnitude")
    parser.add_argument("--xerr-upper", help="Asymmetric x error bar, upper magnitude")
    parser.add_argument("--errorbar-capsize", type=float, help="Error-bar cap half-length in points")
    parser.add_argument("--errorbar-elinewidth", type=float, help="Error-bar stroke width in points")
    parser.add_argument("--errorbar-definition", help="Required with error bars: what the magnitudes mean")
    parser.add_argument("--zero-reference", choices=("raise",), default="raise")
    parser.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    parser.add_argument("--index-col", help="Matrix heatmap row-label column")
    parser.add_argument("--output", type=Path, required=True, help="Output basename; suffix does not override --format")
    parser.add_argument("--no-script", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args(argv)
    if options.size == "multipanel":
        parser.error("size 'multipanel' was removed; use render_multipanel().")
    if bool(options.error_reference is not None) != bool(options.error_definition is not None):
        parser.error("--error-reference and --error-definition must be supplied together")
    error = ({"reference": options.error_reference, "definition": options.error_definition,
              "interpolation": options.error_interpolation, "zero_reference": options.zero_reference}
             if options.error_reference is not None else None)
    if options.error_ylabel is not None:
        if error is None:
            parser.error("--error-ylabel requires --error-reference and --error-definition")
        error["ylabel"] = options.error_ylabel
    if error is None and options.error_interpolation != "none":
        parser.error("--error-interpolation requires --error-reference and --error-definition")
    series_styles = json.loads(options.series_config.read_text(encoding="utf-8")) if options.series_config else None
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
        line_width=options.line_width, marker_size=options.marker_size,
        xscale=options.xscale, yscale=options.yscale, series_styles=series_styles,
        error=error, error_bars=_cli_error_bars(options, parser), legend=options.legend,
        journal=options.journal, height_mm=options.height_mm,
    )
    plt.close(figure)
    if not options.no_script:
        original_args = list(argv if argv is not None else sys.argv[1:])
        original_args[original_args.index("--input") + 1] = str(source)
        original_args[original_args.index("--output") + 1] = str(options.output.resolve())
        target = paths[0].with_suffix("")
        if options.series_config:
            config_path = target.with_name(target.stem + "_series.json")
            config_path.write_text(json.dumps(series_styles, indent=2) + "\n", encoding="utf-8")
            original_args[original_args.index("--series-config") + 1] = str(config_path.resolve())
        _source_script(target, original_args)
    return paths


if __name__ == "__main__":
    for path in run_cli():
        print(path)
