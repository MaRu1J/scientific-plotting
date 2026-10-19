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
from matplotlib.collections import PathCollection
from matplotlib import colors, font_manager
from matplotlib.ticker import AutoMinorLocator, LogFormatterSciNotation, LogLocator, NullFormatter
import numpy as np
import pandas as pd


SIZES_MM = {"single": (89, 66), "double": (183, 136), "multipanel": (183, 180)}
TEXT_SIZES_PT = {
    "single": {"label": 10, "tick": 8.5, "legend": 8.5, "title": 10.5},
    "double": {"label": 11, "tick": 9.5, "legend": 9.5, "title": 11.5},
    "multipanel": {"label": 11, "tick": 9.5, "legend": 9.5, "title": 11.5},
}
FORMATS = ("png", "svg", "pdf", "tiff", "eps")
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
        return 1.2, 2.6
    if spacing < 12:
        return 1.35, 3.8
    if spacing < 26:
        return 1.45, 5.0
    return 1.8, 6.2


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
    if size == "single":
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
        for text_item in text_items:
            if not text_item.get_visible() or not text_item.get_text():
                continue
            box = text_item.get_window_extent(renderer)
            if not (figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)):
                raise ValueError("A label is clipped by this size preset; use a larger preset or shorter labels.")


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
        for key, maximum, applicable in (("line_width", 8, series_kind != "scatter"),
                                          ("marker_size", 20, series_kind != "line")):
            override = style.get(key)
            if override is not None and (not applicable or not isinstance(override, (int, float))
                                         or not np.isfinite(override) or not 0 < override <= maximum):
                raise ValueError(f"Invalid {key} for series {label!r}; maximum is {maximum} pt.")
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
    line_width: float | None = None,
    marker_size: float | None = None,
    xscale: str = "linear",
    yscale: str = "linear",
    series_styles: dict | None = None,
    error: dict | None = None,
    legend: str = "auto",
) -> tuple[mpl.figure.Figure, mpl.axes.Axes, list[Path]]:
    """Draw without changing input data; return figure, axes and exported paths."""
    if kind not in KINDS or size not in SIZES_MM or group_kind not in ("auto", "ordered", "categorical"):
        raise ValueError("Unknown plot kind, size or group kind.")
    if xscale not in ("linear", "log") or yscale not in ("linear", "log"):
        raise ValueError("xscale and yscale must be linear or log.")
    if legend not in ("auto", "outside"):
        raise ValueError("legend must be auto or outside.")
    if error is not None and kind not in (*SERIES_KINDS, "mixed"):
        raise ValueError("Error panels require line, point-line, scatter or mixed.")
    if kind not in (*SERIES_KINDS, "mixed") and (xscale != "linear" or yscale != "linear" or series_styles is not None):
        raise ValueError("Axis scales and series_styles apply to line, point-line, scatter and mixed only.")
    chosen_formats = tuple(dict.fromkeys(formats if formats is not None else ("png",)))
    if not chosen_formats or any(format_name not in FORMATS for format_name in chosen_formats):
        raise ValueError(f"Formats must be drawn from {FORMATS}.")
    if not 72 <= dpi <= 1200:
        raise ValueError("DPI must be between 72 and 1200.")
    for label, override, allowed, maximum in (("line_width", line_width, ("point-line", "line", "mixed"), 8),
                                             ("marker_size", marker_size, ("point-line", "scatter", "mixed"), 20)):
        if override is not None and (kind not in allowed or not np.isfinite(override) or not 0 < override <= maximum):
            raise ValueError(f"{label} must be a positive finite value up to {maximum} for {allowed}.")
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
    text_sizes = TEXT_SIZES_PT[size]
    with mpl.rc_context({"font.family": face, "font.size": text_sizes["tick"],
                         "axes.labelsize": text_sizes["label"], "axes.titlesize": text_sizes["title"],
                         "xtick.labelsize": text_sizes["tick"], "ytick.labelsize": text_sizes["tick"],
                         "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "savefig.facecolor": "white"}):
        width_mm, height_mm = SIZES_MM[size]
        figure, panels = plt.subplots(2 if error is not None else 1, sharex=error is not None,
                                      figsize=(width_mm / 25.4, height_mm / 25.4), dpi=120,
                                      gridspec_kw={"height_ratios": [2.4, 1]} if error is not None else None)
        axes = panels[0] if error is not None else panels
        error_axes = panels[1] if error is not None else None
        figure.scientific_metadata = {"xscale": xscale, "yscale": yscale, "error": error_metadata if error is not None else None}
        figure.scientific_error_axes = error_axes
        axes.set_xscale(xscale)
        axes.set_yscale(yscale)
        _style_axes(axes, kind)
        artists = {}
        error_artists = {}
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
        label_axes = error_axes if error_axes is not None else axes
        label_axes.set_xlabel(xlabel if xlabel is not None else (x or ""))
        axes.set_ylabel(ylabel if ylabel is not None else (y or value or ""))
        if title:
            axes.set_title(title)
        figure.tight_layout(pad=1.0)
        if kind in (*SERIES_KINDS, "mixed"):
            margins = figure.subplotpars
            figure.subplots_adjust(left=max(0.135, margins.left), right=min(0.91, margins.right),
                                   bottom=max(0.13, margins.bottom), top=min(0.95, margins.top))
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        _place_legend(figure, axes, size, legend)
        figure.canvas.draw()
        for panel_axes in figure.axes:
            _adapt_log_ticks(panel_axes)
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        for label, artist in error_artists.items():
            _copy_identity(artists[label], artist)
        _sync_legend(axes)
        if artists:
            figure.scientific_metadata["series"] = {
                label: {"kind": styles[label]["kind"],
                        "line_width_pt": None if isinstance(artist, PathCollection) else artist.get_linewidth(),
                        "marker_size_pt": float(np.sqrt(artist.get_sizes()[0])) if isinstance(artist, PathCollection)
                        else artist.get_markersize() if styles[label]["kind"] == "point-line" else None}
                for label, artist in artists.items()}
        for panel_axes in figure.axes:
            _hide_edge_grids(panel_axes)
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
            if error is not None:
                target.with_name(target.stem + "_metadata.json").write_text(
                    json.dumps(figure.scientific_metadata, indent=2) + "\n", encoding="utf-8")
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
    parser.add_argument("--zero-reference", choices=("raise",), default="raise")
    parser.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    parser.add_argument("--index-col", help="Matrix heatmap row-label column")
    parser.add_argument("--output", type=Path, required=True, help="Output basename; suffix does not override --format")
    parser.add_argument("--no-script", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args(argv)
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
        error=error, legend=options.legend,
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
