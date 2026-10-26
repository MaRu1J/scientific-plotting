"""Reusable, reproducible scientific plotting template and command-line entry."""

from __future__ import annotations

import argparse
from functools import wraps
import hashlib
from importlib import metadata as package_metadata
import inspect
import json
import platform
from pathlib import Path
import re
import shutil
import sys
import tempfile
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.container import BarContainer
from matplotlib.patches import StepPatch
from matplotlib import colors, font_manager
from matplotlib.ticker import AutoMinorLocator, LogFormatterSciNotation, LogLocator, NullFormatter
from mpl_toolkits.axes_grid1.inset_locator import mark_inset
import numpy as np
import pandas as pd
from PIL import Image


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
ANALYSIS_KINDS = ("histogram", "ecdf", "box", "joint", "trajectory", "contribution")
KINDS = ("point-line", "line", "bar", "scatter", "heatmap", "violin", "mixed", *ANALYSIS_KINDS)
SERIES_KINDS = ("line", "point-line", "scatter")
_FONT_CANDIDATES = {
    "Arial": (("Arial",), ("Liberation Sans",)),
    "Times New Roman": (("Times New Roman",), ("Liberation Serif",)),
    "思源黑体": (("Noto Sans CJK SC", "Source Han Sans SC", "思源黑体"), ("WenQuanYi Micro Hei",)),
    "思源宋体": (("Noto Serif CJK SC", "Source Han Serif SC", "思源宋体"), ("AR PL UMing CN",)),
}
_FONT_ALIASES = {
    "Noto Sans CJK SC": "思源黑体",
    "Source Han Sans SC": "思源黑体",
    "Noto Serif CJK SC": "思源宋体",
    "Source Han Serif SC": "思源宋体",
}
FONT_CHOICES = (
    "Arial", "Times New Roman", "思源黑体", "思源宋体",
    "Noto Sans CJK SC", "Source Han Sans SC", "Noto Serif CJK SC", "Source Han Serif SC",
)
_CJK_FACES = frozenset(name for preferred, fallbacks in (
    _FONT_CANDIDATES["思源黑体"], _FONT_CANDIDATES["思源宋体"]) for name in (*preferred, *fallbacks))
# Categorical hues stay apart and dark enough for a thin line on white.
# Ordered stops run amber -> yellow-green -> green -> teal -> deep blue-teal.
CATEGORICAL_COLORS = ("#2F6DB5", "#D35400", "#1B8A4C", "#AA3377", "#6A7020", "#C4453A", "#5C4E9A", "#3A3F46")
ORDERED_COLORS = ("#C46B04", "#578006", "#24782B", "#066955", "#0A5270")
PALETTES = {
    "classic": CATEGORICAL_COLORS,
    "jewel": ("#315DB0", "#00836F", "#C45618", "#A33278", "#8C7218", "#6550AA", "#AD4245", "#424C59"),
    "muted": ("#52759B", "#A65F3B", "#4F7C66", "#8E6185", "#82752F", "#AC5552", "#706E9B", "#515B65"),
    "focus": ("#315DB0", "#717984"),
    # Reference-inspired hues, darkened for fine strokes on white paper.
    "soft": ("#4C6C9A", "#B95670", "#4B8C89", "#8870AE", "#A77C35", "#59616D"),
    "coastal": ("#315F8C", "#238B9D", "#54836B", "#8B73AA", "#B86879"),
}
MARKERS = ("o", "s", "^", "D", "v", "p")
SCATTER_DENSE_PT = 5.0
SCATTER_SPARSE_PT = 6.2
LINESTYLES = ("-", "--", "-.", ":", (0, (8, 2)), (0, (4, 1)),
              (0, (5, 2, 1, 2, 1, 2)), (0, (2, 1, 2, 3)))

ERRORBAR_CAPSIZE_PT = 2.2
ERRORBAR_ELINEWIDTH_PT = 0.8
_ERRORBAR_KEYS = frozenset({"x", "y", "x_lower", "x_upper", "y_lower", "y_upper",
                            "capsize", "elinewidth", "definition", "display", "alpha"})
DELIVERY_SCHEMA_VERSION = 1
GRAYSCALE_DISTANCE = 0.08


def resolve_font(requested: str) -> str:
    """Pick a specified face, or an explicitly reported fallback when it is missing."""
    canonical = _FONT_ALIASES.get(requested, requested)
    if canonical not in _FONT_CANDIDATES:
        raise ValueError(f"Font must be one of: {', '.join(FONT_CHOICES)}")
    preferred, fallbacks = _FONT_CANDIDATES[canonical]
    available = {entry.name for entry in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            return name
    for name in fallbacks:
        if name in available:
            warnings.warn(f"{canonical} not installed; using {name}. Check the final text layout.", stacklevel=2)
            return name
    tried = ", ".join((*preferred, *fallbacks))
    raise RuntimeError(f"Neither {canonical} nor a fallback is installed (tried {tried}).")


def _font_families(face: str | list | tuple) -> tuple[str, ...]:
    if isinstance(face, (list, tuple)):
        return tuple(str(item) for item in face)
    return (str(face),)


def _face_has_glyph(family: str, character: str) -> bool:
    try:
        path = font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
    except ValueError:
        return False
    return font_manager.get_font(path).get_char_index(ord(character)) != 0


def _ensure_cjk_font(text: str, families: tuple[str, ...]) -> None:
    character = next((char for char in text if "\u4e00" <= char <= "\u9fff"), None)
    if character is None or any(_face_has_glyph(family, character) for family in families):
        return
    raise ValueError(
        f"Chinese text cannot be drawn with {', '.join(families)}. Choose font '思源黑体' or '思源宋体'.")


def _closed_math(part: str) -> bool:
    if not part.endswith("$") or part.endswith("\\$"):
        return False
    count = 0
    escaped = False
    for char in part:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "$":
            count += 1
    return count > 0 and count % 2 == 0


def _add_plain(parts: list[str], text: str) -> None:
    if parts and not _closed_math(parts[-1]):
        parts[-1] += text
    else:
        parts.append(text)


def _is_script_base(char: str) -> bool:
    if char.isascii() and char.isalnum():
        return True
    code = ord(char)
    return 0x0370 <= code <= 0x03FF or 0x1F00 <= code <= 0x1FFF


def _read_script(source: str, start: int) -> tuple[str, int] | None:
    if start >= len(source):
        return None
    char = source[start]
    if char == "{":
        depth = 0
        for cursor, item in enumerate(source[start:], start):
            if item == "{":
                depth += 1
            elif item == "}":
                depth -= 1
                if depth == 0:
                    return source[start:cursor + 1], cursor + 1
        return None
    if char == "\\":
        cursor = start + 1
        while cursor < len(source) and source[cursor].isascii() and source[cursor].isalpha():
            cursor += 1
        if cursor == start + 1:
            return None
        return source[start:cursor], cursor
    if char in "*+":
        return char, start + 1
    if char == "-" and start + 1 < len(source) and source[start + 1].isdigit():
        cursor = start + 1
        while cursor < len(source) and source[cursor].isdigit():
            cursor += 1
        return source[start:cursor], cursor
    if char.isdigit():
        cursor = start
        while cursor < len(source) and source[cursor].isdigit():
            cursor += 1
        return source[start:cursor], cursor
    if _is_script_base(char):
        return char, start + 1
    return None


def _attach_script(parts: list[str], operator: str, script: str) -> None:
    token = operator + (script if script.startswith("{") else "{" + script + "}")
    if parts and _closed_math(parts[-1]):
        parts[-1] = parts[-1][:-1] + token + "$"
        return
    head = parts[-1] if parts else ""
    base_at = len(head)
    while base_at > 0 and _is_script_base(head[base_at - 1]):
        base_at -= 1
    base = head[base_at:]
    if parts:
        parts[-1] = head[:base_at]
        if not parts[-1]:
            parts.pop()
    parts.append(f"${base}{token}$")


def format_axis_label(text: str | None) -> str:
    """Convert t^*, t^+, subscripts, and \\(...\\) into Matplotlib mathtext."""
    source = "" if text is None else str(text)
    parts: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        if source.startswith(r"\(", index) or source.startswith(r"\[", index):
            closer = r"\)" if source.startswith(r"\(", index) else r"\]"
            end = source.find(closer, index + 2)
            if end != -1:
                inner = source[index + 2:end].strip()
                if inner:
                    parts.append(f"${inner}$")
                index = end + 2
                continue
        if source[index] == "$":
            delimiter = "$$" if source.startswith("$$", index) else "$"
            cursor = index + len(delimiter)
            closed = False
            while cursor < length:
                if source[cursor] == "\\" and cursor + 1 < length:
                    cursor += 2
                    continue
                if source.startswith(delimiter, cursor):
                    cursor += len(delimiter)
                    closed = True
                    break
                cursor += 1
            if not closed:
                parts.append(source[index:])
                break
            parts.append(source[index:cursor])
            index = cursor
            continue
        if source[index] == "\\" and index + 1 < length and source[index + 1] in "^_":
            _add_plain(parts, source[index + 1])
            index += 2
            continue
        if source[index] in "^_":
            found = _read_script(source, index + 1)
            if found is not None:
                operator = source[index]
                script, index = found
                _attach_script(parts, operator, script)
                continue
        _add_plain(parts, source[index])
        index += 1
    return "".join(parts)


def _prepare_label(text: str | None, families: tuple[str, ...]) -> str:
    formatted = format_axis_label(text)
    _ensure_cjk_font(formatted, families)
    return formatted


def _rc_for_font(face: str | list | tuple, text_sizes: dict, *, embed: bool) -> dict:
    rc = {"font.family": face, "font.size": text_sizes["tick"],
          "axes.labelsize": text_sizes["label"], "axes.titlesize": text_sizes["title"],
          "xtick.labelsize": text_sizes["tick"], "ytick.labelsize": text_sizes["tick"],
          "savefig.facecolor": "white"}
    if embed:
        rc.update({"svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42})
    if any(family in _CJK_FACES for family in _font_families(face)):
        rc["axes.unicode_minus"] = False
    return rc


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


def _palette(count: int, ordered: bool, palette: str = "classic", focus_index: int | None = None) -> list[str]:
    if not isinstance(palette, str) or palette not in PALETTES:
        raise ValueError(f"Unknown palette; choose from {', '.join(PALETTES)}.")
    if ordered and palette != "classic":
        raise ValueError("Named categorical palettes require group_kind='categorical'; ordered groups retain their ramp.")
    if palette == "focus":
        return [PALETTES[palette][0 if index == focus_index else 1] for index in range(count)]
    if palette != "classic":
        if count > len(PALETTES[palette]):
            raise ValueError("Palette capacity exceeded; divide categories into panels instead of repeating colors.")
        return list(PALETTES[palette][:count])
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
    grid_axes = "y" if kind in ("bar", "violin", "box", "contribution") else "both"
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
        if style.get("fillstyle") == "none":
            collection.set_facecolor("none")
            collection.set_edgecolor(style["color"])
            collection.set_linewidth(0.85)
    for line in axes.lines:
        if getattr(line, "_scientific_errorbar", False) or getattr(line, "_scientific_guide", False):
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
            hollow = style.get("fillstyle") == "none"
            line.set_fillstyle("none" if hollow else "full")
            line.set_markerfacecolor("none" if hollow else line.get_color())
            line.set_markeredgecolor(line.get_color() if hollow or edge_mode == "face" else "white")
            line.set_markeredgewidth(0.85 if hollow else edge_width)


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
        if isinstance(patch, StepPatch):
            vertices = patch.get_path().interpolated(10).transformed(patch.get_transform()).vertices
            sampled.append(vertices)
            continue
        box = patch.get_window_extent()
        sampled.append(np.array([box.p0, box.p1, box.get_points().mean(axis=0)]))
    for collection in axes.collections:
        if hasattr(collection, "get_offsets"):
            offsets = collection.get_offsets()
            if len(offsets):
                sampled.append(axes.transData.transform(offsets))
    for child in axes.child_axes:
        box = child.get_window_extent()
        horizontal = np.linspace(box.x0, box.x1, 30)
        vertical = np.linspace(box.y0, box.y1, 30)
        sampled.append(np.array(np.meshgrid(horizontal, vertical)).reshape(2, -1).T)
    return np.concatenate(sampled) if sampled else np.empty((0, 2))


def _extents_overlap(first, second, pad: float) -> bool:
    return not (first.x1 <= second.x0 - pad or second.x1 <= first.x0 - pad
                or first.y1 <= second.y0 - pad or second.y1 <= first.y0 - pad)


def _layout_text_boxes(figure: mpl.figure.Figure):
    renderer = figure.canvas.get_renderer()
    boxes = []
    for panel in figure.axes:
        texts = [panel.title, panel.xaxis.label, panel.yaxis.label,
                 panel.xaxis.get_offset_text(), panel.yaxis.get_offset_text()]
        texts.extend(text for text in panel.texts if getattr(text, "_scientific_panel_letter", False))
        for axis, limits in ((panel.xaxis, panel.get_xlim()), (panel.yaxis, panel.get_ylim())):
            low, high = sorted(limits)
            for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks()):
                loc = tick.get_loc()
                if not tick.get_visible() or loc is None or not np.isfinite(loc) or not low <= loc <= high:
                    continue
                texts.extend((tick.label1, tick.label2))
        for text in texts:
            if text.get_visible() and text.get_text().strip():
                boxes.append(text.get_window_extent(renderer))
    return boxes


def _layout_boxes(figure: mpl.figure.Figure):
    renderer = figure.canvas.get_renderer()
    boxes = [panel.get_window_extent(renderer) for panel in figure.axes]
    boxes.extend(_layout_text_boxes(figure))
    return boxes


def _foreign_axes_boxes(figure: mpl.figure.Figure, hosts: list):
    children = {child for host in hosts for child in getattr(host, "child_axes", ())}
    allowed = set(hosts) | children
    renderer = figure.canvas.get_renderer()
    return [panel.get_window_extent(renderer) for panel in figure.axes if panel not in allowed]


def _outside_legend_is_clear(figure: mpl.figure.Figure, legend, host=None) -> bool:
    box = legend.get_window_extent(figure.canvas.get_renderer())
    if box.x0 < 2 or box.y0 < 2 or box.x1 > figure.bbox.x1 - 2 or box.y1 > figure.bbox.y1 - 2:
        return False
    if host is not None and (box.x0 < host.x0 - 1 or box.x1 > host.x1 + 1):
        return False
    if box.height > figure.bbox.height * 0.35:
        return False
    pad = 4 * figure.dpi / 72
    return all(not _extents_overlap(box, other, pad) for other in _layout_boxes(figure))


def _host_spine_box(figure: mpl.figure.Figure, hosts: list):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    boxes = [axes.get_window_extent(renderer) for axes in hosts]
    host = boxes[0]
    for box in boxes[1:]:
        host = host.union((host, box))
    return host


def _spine_edge(side: str, host, boxes, reach: float) -> float:
    """Label edge just beyond this spine. Ignore text that belongs to another panel."""
    if side == "top":
        edge = host.y1
        for box in boxes:
            if box.x1 <= host.x0 or box.x0 >= host.x1 or box.y1 <= host.y1 or box.y0 > host.y1 + reach:
                continue
            edge = max(edge, box.y1)
        return edge
    edge = host.y0
    for box in boxes:
        if box.x1 <= host.x0 or box.x0 >= host.x1 or box.y0 >= host.y0 or box.y1 < host.y0 - reach:
            continue
        edge = min(edge, box.y0)
    return edge


def _fit_outside_band(figure: mpl.figure.Figure, hosts: list, make_legend, entry_count: int, *,
                      sides: tuple[str, ...] = ("top", "bottom"), min_fraction: float = 0.4):
    """Keep an outside legend against the spines and no wider than those spines."""
    saved = (figure.subplotpars.left, figure.subplotpars.bottom, figure.subplotpars.right, figure.subplotpars.top)
    pad = 4 * figure.dpi / 72

    def restore() -> None:
        figure.subplots_adjust(left=saved[0], bottom=saved[1], right=saved[2], top=saved[3])

    for side in sides:
        for columns in range(entry_count, 0, -1):
            restore()
            extra_gap = 0.0
            legend = None
            rejected = False
            for _attempt in range(8):
                if legend is not None:
                    legend.remove()
                host = _host_spine_box(figure, hosts)
                edge = _spine_edge(side, host, _layout_text_boxes(figure), 24 * figure.dpi / 72)
                if side == "top":
                    loc, anchor_y = "lower center", edge + pad + extra_gap
                else:
                    loc, anchor_y = "upper center", edge - pad - extra_gap
                anchor = ((host.x0 + host.x1) / 2 / figure.bbox.width, anchor_y / figure.bbox.height)
                legend = make_legend(columns, loc, anchor)
                figure.canvas.draw()
                box = legend.get_window_extent(figure.canvas.get_renderer())
                host = _host_spine_box(figure, hosts)
                if box.height > figure.bbox.height * 0.35:
                    rejected = "tall"
                    break
                if box.x0 < host.x0 - 1 or box.x1 > host.x1 + 1 or box.width > host.width + 1:
                    rejected = "wide"
                    break
                if any(_extents_overlap(box, other, pad) for other in _foreign_axes_boxes(figure, hosts)):
                    rejected = "blocked"
                    break
                if side == "top":
                    overflow = box.y1 - (figure.bbox.y1 - 2)
                    if overflow > 0.5:
                        updated = figure.subplotpars.top - overflow / figure.bbox.height
                        if updated - figure.subplotpars.bottom < min_fraction:
                            rejected = True
                            break
                        figure.subplots_adjust(top=updated)
                        continue
                else:
                    overflow = 2 - box.y0
                    if overflow > 0.5:
                        updated = figure.subplotpars.bottom + overflow / figure.bbox.height
                        if figure.subplotpars.top - updated < min_fraction:
                            rejected = True
                            break
                        figure.subplots_adjust(bottom=updated)
                        continue
                if _outside_legend_is_clear(figure, legend, host):
                    return legend
                intrusion = 0.0
                for other in _layout_boxes(figure):
                    if not _extents_overlap(box, other, pad):
                        continue
                    if side == "top":
                        intrusion = max(intrusion, other.y1 + pad - box.y0)
                    else:
                        intrusion = max(intrusion, box.y1 + pad - other.y0)
                if intrusion <= 0.5:
                    rejected = True
                    break
                extra_gap += intrusion
            if legend is not None:
                legend.remove()
            if rejected in ("tall", "blocked"):
                break
    restore()
    return None


def _place_outside_legend(figure: mpl.figure.Figure, axes: mpl.axes.Axes, legend_size: float) -> bool:
    """Put the legend just above the spines, then just below. Never use a side column."""
    handles, labels = _legend_entries(axes)

    def make_legend(columns: int, loc: str, anchor: tuple[float, float]):
        return _series_axes(axes)[-1].legend(
            handles, labels, loc=loc, bbox_to_anchor=anchor, bbox_transform=figure.transFigure,
            ncol=columns, frameon=True, framealpha=1, facecolor="white", edgecolor="#777777",
            fontsize=legend_size, borderaxespad=0)

    return _fit_outside_band(figure, [axes], make_legend, len(handles)) is not None


def _place_legend(figure: mpl.figure.Figure, axes: mpl.axes.Axes, size: str,
                  placement: str = "auto") -> None:
    handles, labels = _legend_entries(axes)
    if not handles:
        return
    renderer = figure.canvas.get_renderer()
    points = np.vstack([_line_vertices(panel) for panel in _series_axes(axes)])
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
            legend = _series_axes(axes)[-1].legend(handles, labels, loc=location, ncol=columns, frameon=True, framealpha=1,
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
    elif isinstance(source, StepPatch):
        target.set_color(source.get_edgecolor())
        target.set_linewidth(source.get_linewidth())
        target.set_linestyle(source.get_linestyle())
    elif isinstance(source, BarContainer):
        return
    else:
        target.set_color(source.get_color())
        target.set_linestyle(getattr(source, "_scientific_linestyle", source.get_linestyle()))
        target.set_linewidth(source.get_linewidth())
        target.set_marker(source.get_marker())
        target.set_fillstyle(source.get_fillstyle())
        target.set_markersize(source.get_markersize())
        target.set_markerfacecolor(source.get_markerfacecolor())
        target.set_markeredgecolor(source.get_markeredgecolor())
        target.set_markeredgewidth(source.get_markeredgewidth())


def _sync_legend(axes) -> None:
    legend = _series_axes(axes)[-1].get_legend()
    if legend is None:
        return
    handles, _ = _legend_entries(axes)
    for source, target in zip(handles, legend.legend_handles):
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


def _check_text_layout(figure: mpl.figure.Figure) -> None:
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for panel_axes in [axes for parent in figure.axes for axes in (parent, *parent.child_axes)]:
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
            text_items.extend(label for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks())
                              if low <= tick.get_loc() <= high for label in (tick.label1, tick.label2))
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


def _encoding_styles(encoding, values: list, palette: str, focus: str | None) -> tuple[dict, dict | None]:
    if encoding is None:
        return {}, None
    allowed = {"categories", "metrics", "series", "category_label", "metric_label", "legend", "reason"}
    if not isinstance(encoding, dict) or encoding.keys() - allowed:
        raise ValueError("encoding requires explicit categories, metrics and series roles; unknown keys are refused.")
    for key, style_keys in (("categories", {"color", "marker"}), ("metrics", {"linestyle", "fillstyle", "quantity", "unit"})):
        entries = encoding.get(key)
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"encoding needs nonempty {key}.")
        for label, style in entries.items():
            if not isinstance(label, str) or not label.strip() or not isinstance(style, dict) or style.keys() - style_keys:
                raise ValueError(f"Invalid {key} role or style keys.")
            if key == "metrics" and ("quantity" in style or "unit" in style):
                if any(not isinstance(style.get(field), str) or not style[field].strip() for field in ("quantity", "unit")):
                    raise ValueError("A typed metric needs both nonempty quantity and unit; units are never inferred.")
    roles = encoding.get("series")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("encoding.series must explicitly map series labels to category and metric.")
    for label, role in roles.items():
        if (not isinstance(label, str) or not isinstance(role, dict) or role.keys() != {"category", "metric"}
                or not isinstance(role["category"], str) or not isinstance(role["metric"], str)
                or role["category"] not in encoding["categories"] or role["metric"] not in encoding["metrics"]):
            raise ValueError("Each encoding series needs known category and metric roles.")
    if {label for label, _ in values} - roles.keys():
        raise ValueError("encoding.series must cover every plotted series; roles are never inferred from labels.")
    legend_mode = encoding.get("legend", "factorized")
    if legend_mode not in ("factorized", "combined"):
        raise ValueError("encoding.legend must be factorized or combined.")
    for key, default in (("category_label", "Category"), ("metric_label", "Metric"), ("reason", "Explicit category/metric roles")):
        if not isinstance(encoding.get(key, default), str) or not encoding.get(key, default).strip():
            raise ValueError(f"encoding.{key} must be nonempty text.")
    categories = list(encoding["categories"])
    if palette == "focus" and focus not in categories:
        raise ValueError("With encoding, focus must name a declared category, not a combined series.")
    category_colors = _palette(len(categories), False, palette, categories.index(focus) if focus in categories else None)
    category_styles = {category: {"color": category_colors[index], "marker": MARKERS[index % len(MARKERS)], **style}
                       for index, (category, style) in enumerate(encoding["categories"].items())}
    metric_styles = {metric: {"linestyle": "-", "fillstyle": "full", **style}
                     for metric, style in encoding["metrics"].items()}
    styles = {label: {**category_styles[roles[label]["category"]],
                      **{key: value for key, value in metric_styles[roles[label]["metric"]].items() if key not in ("quantity", "unit")}}
              for label, _ in values}
    observed = [dict(series=label, **roles[label]) for label, _ in values]
    metadata = {"category_label": encoding.get("category_label", "Category"),
                "metric_label": encoding.get("metric_label", "Metric"), "legend": legend_mode,
                "reason": encoding.get("reason", "Explicit category/metric roles"),
                "categories": category_styles, "metrics": metric_styles, "observed": observed}
    return styles, metadata


def _series_axes(axes) -> list:
    secondary = getattr(axes, "scientific_secondary_axes", None)
    return [axes] if secondary is None else [axes, secondary]


def _resolve_secondary_y(spec, values: list, *, kind: str, ylabel, yscale: str, error, inset, guides, encoding) -> dict | None:
    if spec is None:
        return None
    required = {"series", "label", "quantity", "unit", "limits", "primary", "reason"}
    if not isinstance(spec, dict) or not required.issubset(spec) or spec.keys() - (required | {"scale"}):
        raise ValueError("secondary_y requires series, label, quantity, unit, limits, primary and reason.")
    if kind not in SERIES_KINDS:
        raise ValueError("secondary_y supports native line, point-line and scatter only; mixed is not supported yet.")
    if error is not None or inset is not None or guides:
        raise ValueError("secondary_y cannot yet combine with reference-error panels, inset or reference_guides; use facets.")
    for key in ("label", "quantity", "unit", "reason"):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f"secondary_y.{key} needs nonempty explicit text.")
    primary = spec["primary"]
    if not isinstance(primary, dict) or primary.keys() != {"quantity", "unit", "limits"}:
        raise ValueError("secondary_y.primary requires quantity, unit and limits.")
    if not isinstance(ylabel, str) or not ylabel.strip():
        raise ValueError("secondary_y requires an explicit primary ylabel including units.")
    if any(not isinstance(primary[key], str) or not primary[key].strip() for key in ("quantity", "unit")):
        raise ValueError("Both axes require explicit quantity and unit; use '-' for dimensionless values.")
    if primary["quantity"].strip().casefold() == spec["quantity"].strip().casefold():
        raise ValueError("The same quantity should share an axis or use a reversible unit-conversion axis, not independent dual axes.")
    scale = spec.get("scale", "linear")
    if scale not in ("linear", "log"):
        raise ValueError("secondary_y.scale must be linear or log.")
    selected = spec["series"]
    labels = {label for label, _ in values}
    if (not isinstance(selected, list) or not selected or any(not isinstance(label, str) for label in selected)
            or len(set(selected)) != len(selected) or not set(selected) < labels):
        raise ValueError("secondary_y.series must be a nonempty unique proper subset of plotted series labels.")
    if encoding is not None:
        metrics = {}
        for record in encoding["observed"]:
            axis_name = "right" if record["series"] in selected else "left"
            metric = record["metric"]
            if metric in metrics and metrics[metric] != axis_name:
                raise ValueError("A semantic metric cannot be split across the left and right axes.")
            metrics[metric] = axis_name
            declared = encoding["metrics"][metric]
            axis_spec = spec if axis_name == "right" else primary
            if "quantity" in declared and any(declared[field] != axis_spec[field] for field in ("quantity", "unit")):
                raise ValueError("Metric quantity/unit disagrees with its explicit dual-axis assignment.")
    return {**spec, "series": list(selected), "scale": scale,
            "limits": _interval(spec["limits"], "secondary_y.limits", positive=scale == "log"),
            "primary": {**primary, "limits": _interval(primary["limits"], "primary.limits", positive=yscale == "log")}}


def _legend_entries(axes) -> tuple[list, list]:
    handles, labels = [], []
    for panel in _series_axes(axes):
        panel_handles, panel_labels = panel.get_legend_handles_labels()
        handles.extend(panel_handles)
        labels.extend(panel_labels)
    spec = getattr(axes, "_scientific_encoding", None)
    if spec is None or spec["legend"] == "combined":
        return handles, labels
    role_handles = [handle for handle in handles if hasattr(handle, "_scientific_roles")]
    if not role_handles:
        return handles, labels
    if len({handle._scientific_identity[0] for handle in role_handles}) != 1:
        raise ValueError("Factorized legend requires a consistent series kind; use encoding.legend='combined'.")
    seen = {"category": {}, "metric": {}}
    pairs = set()
    for handle in role_handles:
        role = handle._scientific_roles
        pair = (role["category"], role["metric"])
        if pair in pairs:
            raise ValueError("Duplicate category/metric pair is ambiguous; use combined legend or explicit replicate roles.")
        pairs.add(pair)
        style = handle._scientific_style
        identities = {"category": (colors.to_hex(style["color"]), style.get("marker")),
                      "metric": (str(style.get("linestyle")), style.get("fillstyle"))}
        for key in seen:
            label = role[key]
            if label in seen[key] and seen[key][label][0] != identities[key]:
                raise ValueError("Styles cannot be factorized consistently; use encoding.legend='combined'.")
            seen[key][label] = (identities[key], style)
    proxies, proxy_labels = [], []
    series_kind = role_handles[0]._scientific_identity[0]
    for key, definitions in (("category", spec["categories"]), ("metric", spec["metrics"])):
        if len({identity for identity, _style in seen[key].values()}) != len(seen[key]):
            raise ValueError(f"Distinct {key} roles need distinct visible encodings; use facets or revise styles.")
        for label in definitions:
            if label not in seen[key]:
                continue
            identity, style = seen[key][label]
            color = style["color"] if key == "category" else "#424C59"
            marker = (style.get("marker", "o") if key == "category" else "o") if series_kind != "line" else None
            linestyle = style.get("linestyle", "-") if key == "metric" else "-"
            if series_kind == "scatter":
                linestyle = "None"
            fillstyle = style.get("fillstyle", "full") if key == "metric" else "full"
            proxy = Line2D([], [], color=color, marker=marker, linestyle=linestyle, fillstyle=fillstyle,
                           markerfacecolor="none" if fillstyle == "none" else color,
                           markeredgecolor=color, markeredgewidth=0.85, markersize=5, linewidth=1.2)
            proxy._scientific_identity = ("role", key, identity, series_kind)
            proxy._scientific_linestyle = linestyle
            proxies.append(proxy)
            proxy_labels.append(f"{spec[key + '_label']}: {label}")
    extras = [(handle, label) for handle, label in zip(handles, labels) if handle not in role_handles]
    return proxies + [handle for handle, _ in extras], proxy_labels + [label for _, label in extras]


def _registry_styles(style_registry: dict | None, palette: str = "classic", focus: str | None = None) -> dict:
    if style_registry is None:
        return {}
    if not isinstance(style_registry, dict):
        raise ValueError("style_registry must map string series labels to style objects.")
    labels = list(style_registry)
    palette_colors = _palette(len(labels), False, palette, labels.index(focus) if focus in labels else None)
    resolved = {}
    for index, (label, style) in enumerate(style_registry.items()):
        if not isinstance(label, str) or not isinstance(style, dict):
            raise ValueError("style_registry needs string labels and style objects.")
        if style.keys() - {"color", "marker", "linestyle", "fillstyle"}:
            raise ValueError("style_registry accepts color, marker, linestyle and fillstyle only; kinds stay per figure.")
        resolved[label] = {
            "color": palette_colors[index],
            "marker": MARKERS[index % len(MARKERS)],
            "linestyle": LINESTYLES[index % len(LINESTYLES)],
            **style,
        }
    return resolved


def _series_options(values: list, kind: str, series_styles: dict | None,
                    line_width: float | None, marker_size: float | None,
                    style_registry: dict | None = None, palette: str = "classic", focus: str | None = None,
                    role_styles: dict | None = None) -> dict:
    if series_styles is not None and not isinstance(series_styles, dict):
        raise ValueError("series_styles must map string series labels to style objects.")
    styles = series_styles or {}
    registry = _registry_styles(style_registry, "classic" if role_styles else palette, focus)
    labels = {label for label, _ in values}
    if len(labels) != len(values):
        raise ValueError("Series labels are ambiguous after string conversion; use unique string labels.")
    if styles.keys() - labels:
        raise ValueError(f"Unknown series_styles labels: {styles.keys() - labels}")
    if kind == "mixed" and styles.keys() != labels:
        raise ValueError("mixed requires an explicit kind for every series in series_styles.")
    if style_registry is not None and labels - registry.keys():
        warnings.warn("Unregistered series use automatic styles; add them to style_registry for cross-figure "
                      f"consistency: {', '.join(sorted(labels - registry.keys()))}.", UserWarning, stacklevel=3)
    result = {}
    for label, _ in values:
        style = styles.get(label, {})
        if not isinstance(style, dict) or style.keys() - {"kind", "linestyle", "marker", "color", "line_width", "marker_size", "fillstyle"}:
            raise ValueError(f"Invalid style keys for series {label!r}.")
        series_kind = style.get("kind", kind)
        if series_kind not in SERIES_KINDS or (kind != "mixed" and series_kind != kind):
            raise ValueError("Per-series kind changes require kind='mixed'; native kinds keep their semantics.")
        registered = dict(registry.get(label, {}))
        if role_styles:
            registered = {key: value for key, value in registered.items() if key in (style_registry or {}).get(label, {})}
        if series_kind == "line":
            registered.pop("marker", None)
        if series_kind == "scatter":
            registered.pop("linestyle", None)
        semantic = dict((role_styles or {}).get(label, {}))
        if series_kind == "line":
            semantic.pop("marker", None)
            if semantic.get("fillstyle", "full") == "full":
                semantic.pop("fillstyle", None)
        if series_kind == "scatter":
            semantic.pop("linestyle", None)
        style = {**semantic, **registered, **style}
        if "fillstyle" in style and (style["fillstyle"] not in ("full", "none") or series_kind == "line"):
            raise ValueError("fillstyle must be full or none on point-line/scatter series only.")
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
                              facecolor="none" if style.get("fillstyle") == "none" else color,
                              edgecolor=color if style.get("fillstyle") == "none" else "#333333", linewidth=0.35, zorder=3)
    else:
        linestyle = (LINESTYLES[(index // len(MARKERS)) % len(LINESTYLES)]
                     if series_kind == "point-line" else LINESTYLES[index % len(LINESTYLES)])
        linestyle = style.get("linestyle", linestyle)
        artist, = axes.plot(x_values, y_values, label=label or None, color=color,
                            linestyle=linestyle, linewidth=1.5,
                            marker=marker if series_kind == "point-line" else None,
                            fillstyle=style.get("fillstyle", "full"),
                            markersize=6.2, markerfacecolor=color, markeredgecolor="white",
                            markeredgewidth=0.9)
        artist._scientific_linestyle = linestyle
    artist._scientific_style = style
    if "fillstyle" in style:
        style["color"] = color
    artist._scientific_identity = (
        series_kind,
        colors.to_hex(color),
        None if series_kind == "scatter" else str(linestyle),
        None if series_kind == "line" else str(marker),
    )
    if style.get("fillstyle") == "none":
        artist._scientific_identity += ("none",)
    return artist


def _finite_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)


def _interval(value, name: str, *, positive: bool = False) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} requires two increasing finite numbers.")
    lower, upper = [_finite_number(item, name) for item in value]
    if lower >= upper or (positive and lower <= 0):
        raise ValueError(f"{name} must increase and be strictly positive on a log axis.")
    return [lower, upper]


def _resolve_guides(reference_guides, kind: str, xscale: str, yscale: str) -> list[dict]:
    if reference_guides is None:
        return []
    if kind not in (*SERIES_KINDS, "mixed") or not isinstance(reference_guides, list):
        raise ValueError("reference_guides requires a list on line, point-line, scatter or mixed plots.")
    result = []
    for guide in reference_guides:
        if not isinstance(guide, dict) or guide.keys() - {"kind", "axis", "value", "order", "anchor", "range", "label"}:
            raise ValueError("Invalid reference guide keys.")
        if not isinstance(guide.get("label"), str) or not guide["label"].strip() or guide["label"].startswith("_"):
            raise ValueError("Each reference guide needs a visible label describing its meaning.")
        resolved = dict(guide)
        if guide.get("kind") == "constant":
            if guide.keys() - {"kind", "axis", "value", "label"} or guide.get("axis") not in ("x", "y"):
                raise ValueError("constant guides require axis='x' or 'y', value and label.")
            resolved["value"] = _finite_number(guide.get("value"), "guide value")
            scale = xscale if guide["axis"] == "x" else yscale
            if scale == "log" and resolved["value"] <= 0:
                raise ValueError("A log-axis reference guide must be strictly positive.")
        elif guide.get("kind") == "power":
            if guide.keys() - {"kind", "order", "anchor", "range", "label"} or (xscale, yscale) != ("log", "log"):
                raise ValueError("power guides require log x and y axes, order, anchor, range and label.")
            resolved["order"] = _finite_number(guide.get("order"), "guide order")
            anchor = guide.get("anchor")
            if not isinstance(anchor, (list, tuple)) or len(anchor) != 2:
                raise ValueError("power guide anchor must be [x0, y0].")
            resolved["anchor"] = [_finite_number(item, "guide anchor") for item in anchor]
            if min(resolved["anchor"]) <= 0:
                raise ValueError("power guide anchor must be strictly positive.")
            resolved["range"] = _interval(guide.get("range"), "guide range", positive=True)
        else:
            raise ValueError("Reference guide kind must be constant or power.")
        result.append(resolved)
    return result


def _draw_guides(axes, guides: list[dict]) -> None:
    for guide in guides:
        kwargs = {"label": guide["label"], "color": "#3A3F46", "linestyle": "--", "linewidth": 0.8}
        if guide["kind"] == "constant":
            draw = axes.axhline if guide["axis"] == "y" else axes.axvline
            artist = draw(guide["value"], **kwargs)
        else:
            coordinates = np.geomspace(*guide["range"], 100)
            anchor_x, anchor_y = guide["anchor"]
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                values = anchor_y * (coordinates / anchor_x) ** guide["order"]
            if not np.isfinite(values).all() or np.any(values <= 0):
                raise ValueError("power guide values must remain finite and strictly positive.")
            artist, = axes.plot(coordinates, values, **kwargs)
        artist._scientific_guide = True
        artist._scientific_identity = ("guide", json.dumps(guide, sort_keys=True))


def _resolve_inset(inset, kind: str, xscale: str, yscale: str) -> dict | None:
    if inset is None:
        return None
    if kind not in (*SERIES_KINDS, "mixed") or not isinstance(inset, dict):
        raise ValueError("inset requires a configuration on line, point-line, scatter or mixed plots.")
    if inset.keys() != {"xlim", "ylim", "bounds"}:
        raise ValueError("inset requires xlim, ylim and bounds=[left, bottom, width, height] in axes fractions.")
    bounds = inset["bounds"]
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ValueError("inset bounds must contain four finite axes fractions.")
    left, bottom, width, height = [_finite_number(item, "inset bounds") for item in bounds]
    if min(left, bottom) < 0 or min(width, height) <= 0 or left + width > 1 or bottom + height > 1:
        raise ValueError("inset bounds must fit inside the main axes.")
    return {"xlim": _interval(inset["xlim"], "inset xlim", positive=xscale == "log"),
            "ylim": _interval(inset["ylim"], "inset ylim", positive=yscale == "log"),
            "bounds": [left, bottom, width, height]}


def _refresh_inset(axes) -> None:
    spec = getattr(axes, "_scientific_inset_spec", None)
    if spec is None:
        return
    for connector in getattr(axes, "scientific_inset_connectors", ()):
        connector.remove()
    zoom = getattr(axes, "scientific_inset_axes", None)
    if zoom is None:
        zoom = axes.inset_axes(spec["bounds"], zorder=5)
        axes.scientific_inset_axes = zoom
    else:
        zoom.clear()
    zoom.set_xscale(axes.get_xscale())
    zoom.set_yscale(axes.get_yscale())
    _style_axes(zoom, "line")
    for source in axes.lines:
        if getattr(source, "_scientific_guide", False):
            continue
        target = Line2D([], [])
        target.update_from(source)
        target.set_data(source.get_xdata(), source.get_ydata())
        target.set_transform(zoom.transData)
        target.set_clip_path(zoom.patch)
        target.set_label("_nolegend_")
        zoom.add_line(target)
    for source in axes.collections:
        if isinstance(source, PathCollection):
            offsets = np.asarray(source.get_offsets())
            target = zoom.scatter(offsets[:, 0], offsets[:, 1])
            target.set_paths(source.get_paths())
            _copy_identity(source, target)
        elif isinstance(source, LineCollection):
            target = LineCollection(source.get_segments(), colors=source.get_colors(),
                                    linewidths=source.get_linewidths(), linestyles=source.get_linestyles())
            zoom.add_collection(target)
        else:
            continue
        target.set_zorder(source.get_zorder())
        target.set_label("_nolegend_")
    zoom.set_xlim(spec["xlim"])
    zoom.set_ylim(spec["ylim"])
    _adapt_log_ticks(zoom)
    _hide_edge_grids(zoom)
    region = axes.transAxes.inverted().transform(axes.transData.transform([
        [spec["xlim"][0], spec["ylim"][0]], [spec["xlim"][1], spec["ylim"][1]]]))
    left, bottom, width, height = spec["bounds"]
    delta = region.mean(axis=0) - np.array([left + width / 2, bottom + height / 2])
    if abs(delta[1]) >= abs(delta[0]):
        corners = (1, 2) if delta[1] >= 0 else (3, 4)
    else:
        corners = (1, 4) if delta[0] >= 0 else (2, 3)
    axes.scientific_inset_connectors = mark_inset(axes, zoom, loc1=corners[0], loc2=corners[1],
                                                 fc="none", ec="#777777", linewidth=0.7)


def _heatmap_limits(heatmap_scale) -> dict:
    if heatmap_scale is None:
        return {}
    if not isinstance(heatmap_scale, dict) or heatmap_scale.keys() != {"vmin", "vmax"}:
        raise ValueError("heatmap_scale requires vmin and vmax.")
    lower, upper = _interval([heatmap_scale["vmin"], heatmap_scale["vmax"]], "heatmap_scale")
    return {"vmin": lower, "vmax": upper}


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
    display = error_bars.get("display", "bars")
    if display not in ("bars", "band"):
        raise ValueError("error_bars display must be 'bars' or 'band'.")
    alpha = error_bars.get("alpha", 0.18)
    if display == "band":
        if kind not in ("line", "point-line"):
            raise ValueError("Uncertainty bands require line or point-line plots.")
        if any(error_bars.get(key) is not None for key in ("x", "x_lower", "x_upper")):
            raise ValueError("Uncertainty bands accept y magnitudes only.")
        if any(key in error_bars for key in ("capsize", "elinewidth")):
            raise ValueError("Band display does not use capsize or elinewidth.")
        if (isinstance(alpha, (bool, np.bool_)) or not isinstance(alpha, (int, float))
                or not np.isfinite(alpha) or not 0 < alpha <= 0.35):
            raise ValueError("Band alpha must be finite and in (0, 0.35].")
    elif "alpha" in error_bars:
        raise ValueError("error_bars alpha applies only to band display.")
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
        "display": display,
        "alpha": float(alpha) if display == "band" else None,
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
            painted = artist.get_edgecolor()
        if len(painted) == 0:
            raise ValueError("Scatter series has no face or edge color for error bars.")
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


def _all_axes(figure) -> list:
    result = []

    def visit(axes):
        result.append(axes)
        for child in axes.child_axes:
            visit(child)

    for axes in figure.axes:
        visit(axes)
    return result


def _visible_text(figure) -> list:
    texts = [text for text in figure.texts if text.get_visible()]
    for axes in _all_axes(figure):
        texts.extend([axes.title, axes._left_title, axes._right_title, axes.xaxis.label, axes.yaxis.label,
                      axes.xaxis.get_offset_text(), axes.yaxis.get_offset_text(), *axes.texts,
                      *axes.get_xticklabels(which="both"), *axes.get_yticklabels(which="both")])
        legend = axes.get_legend()
        if legend is not None:
            texts.extend(legend.get_texts())
    for legend in figure.legends:
        texts.extend(legend.get_texts())
    return [text for text in texts if text.get_visible() and text.get_text().strip()]


def _canvas_text_findings(figure) -> list[dict]:
    titles = []
    annotations = [text for text in figure.texts if text.get_visible()]
    suptitle = getattr(figure, "_suptitle", None)
    if suptitle is not None and suptitle.get_visible() and suptitle.get_text().strip():
        titles.append(suptitle.get_text())
    for axes in _all_axes(figure):
        if not axes.get_visible():
            continue
        titles.extend(text.get_text() for text in (axes.title, axes._left_title, axes._right_title)
                      if text.get_visible() and text.get_text().strip())
        annotations.extend(text for text in axes.texts if text.get_visible())
    findings = []
    if titles:
        findings.append({**_finding(
            "warn", "canvas_title", "Visible figure/panel/inset titles are not part of the default style. "
            "Confirm they were explicitly requested; otherwise move them to an external caption. Titles were kept.",
            measured=list(dict.fromkeys(titles))), "category": "style"})
    sources = [text.get_text() for text in annotations if re.search(
        r"^\s*(?:sources?|data\s+sources?|来源|数据来源|数据源)\s*[:：]", text.get_text(), re.IGNORECASE | re.MULTILINE)]
    if sources:
        findings.append({**_finding(
            "warn", "canvas_source", "Source/citation text on the canvas is not part of the default style. "
            "Preserve attribution in an external caption or metadata unless explicitly requested on the image. Text was kept.",
            measured=list(dict.fromkeys(sources))), "category": "style"})
    return findings


def review_figure(figure: mpl.figure.Figure, *, journal: str | None = None) -> list[dict]:
    """Report snapshot differences and default-style reminders, never a compliance verdict."""
    metadata = getattr(figure, "scientific_metadata", {}) or {}
    journal = journal or metadata.get("journal") or "elsevier"
    if journal not in JOURNALS:
        raise ValueError(f"journal must be one of: {', '.join(JOURNALS)}.")
    preset = JOURNALS[journal]
    findings = _canvas_text_findings(figure) + _semantic_findings(figure)
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
    sizes = [float(text.get_fontsize()) for text in _visible_text(figure)]
    if sizes and min(sizes) + 1e-6 < preset["min_type_pt"]:
        findings.append(_finding(
            "warn", "type",
            f"Smallest text is {min(sizes):g} pt, below the {journal} snapshot minimum of {preset['min_type_pt']} pt.",
            measured=min(sizes), expected=preset["min_type_pt"]))
    for axes in _all_axes(figure):
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _font_record(figure, requested: str) -> dict:
    faces = {}
    for text in _visible_text(figure):
        path = Path(font_manager.findfont(text.get_fontproperties()))
        key = path.name
        if key not in faces:
            faces[key] = {"family": font_manager.FontProperties(fname=str(path)).get_name(),
                          "file": key, "sha256": _sha256(path) if path.is_file() else None}
    return {"requested": requested, "resolved": list(faces.values()),
            "limitation": "Font files describe resolved text faces; per-glyph and math fallback require visual inspection."}


def _semantic_findings(figure) -> list[dict]:
    findings = []
    candidates = [axes for axes in figure.axes if not hasattr(axes, "_scientific_primary_axes")
                  and (getattr(axes, "_scientific_encoding", None) is not None
                       or getattr(axes, "scientific_secondary_axes", None) is not None
                       or any(getattr(artist, "_scientific_style", {}).get("fillstyle") == "none"
                              for artist in (*axes.lines, *axes.collections)))]
    if not candidates:
        return findings
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for axes in candidates:
        spec = getattr(axes, "_scientific_encoding", None)
        if spec is not None:
            findings.append(_finding("info", "encoding", spec["reason"], measured={
                "legend": spec["legend"], "observed": spec["observed"]}))
            observed = {(record["category"], record["metric"]) for record in spec["observed"]}
            metrics = {record["metric"] for record in spec["observed"]}
            if len(metrics) > 1 and any("quantity" not in spec["metrics"][metric] for metric in metrics):
                findings.append(_finding("warn", "metric_units",
                                         "Some metric quantities/units are undeclared; compatibility was not inferred. Confirm units before sharing a y axis."))
            missing = [(category, metric) for category in spec["categories"] for metric in spec["metrics"]
                       if (category, metric) not in observed]
            if missing:
                findings.append(_finding("info", "missing_combinations",
                                         "Role keys do not imply a complete factorial dataset; unobserved pairs were not fabricated.",
                                         measured=missing))
        for panel in _series_axes(axes):
            for artist in (*panel.lines, *panel.collections):
                style = getattr(artist, "_scientific_style", {})
                if style.get("fillstyle") != "none":
                    continue
                diameter = (float(np.sqrt(artist.get_sizes()[0])) if isinstance(artist, PathCollection)
                            else artist.get_markersize())
                if diameter < 3.6:
                    findings.append(_finding("warn", "hollow_marker",
                                             f"Series {artist.get_label()!r}: hollow markers may be unreadable; use facets or explicit larger markers, not dropped rows.",
                                             measured=diameter, expected=3.6))
        right = getattr(axes, "scientific_secondary_axes", None)
        if right is not None:
            metadata = getattr(axes, "_scientific_panel", getattr(figure, "scientific_metadata", {}))
            dual = metadata.get("secondary_y") or {}
            findings.append(_finding("info", "dual_axis",
                                     "Independent y axes: intersections, slopes and visual alignment do not establish equality or correlation. "
                                     + dual.get("reason", ""), measured={"left_limits": list(axes.get_ylim()),
                                                                        "right_limits": list(right.get_ylim())}))
            for panel, expected in ((axes, dual.get("primary", {}).get("limits")), (right, dual.get("limits"))):
                if expected is not None and not np.allclose(panel.get_ylim(), expected):
                    findings.append(_finding("warn", "dual_limits", "Dual-axis limits changed after explicit validation; review the reason and coverage.",
                                             measured=list(panel.get_ylim()), expected=expected))
            if any(tick.gridline.get_visible() for axis in (right.xaxis, right.yaxis)
                   for tick in (*axis.get_major_ticks(), *axis.get_minor_ticks())):
                findings.append(_finding("warn", "dual_grid", "Secondary gridlines are visible; use one primary grid to avoid false correspondences."))
            label_box = right.yaxis.label.get_window_extent(renderer)
            for neighbor in figure.axes:
                if neighbor not in _series_axes(axes) and not hasattr(neighbor, "_scientific_primary_axes"):
                    if _extents_overlap(label_box, neighbor.get_window_extent(renderer), 2):
                        findings.append(_finding("warn", "dual_label_overlap", "Secondary y label overlaps another panel; increase spacing or use facets."))
    return findings


def _grayscale_findings(figure) -> list[dict]:
    findings = []
    for panel_number, axes in enumerate(figure.axes, 1):
        if hasattr(axes, "_scientific_primary_axes"):
            continue
        series = [artist for panel in _series_axes(axes) for artist in (*panel.lines, *panel.collections)
                  if hasattr(artist, "_scientific_identity") and not getattr(artist, "_scientific_guide", False)]
        for index, first in enumerate(series):
            for second in series[index + 1:]:
                first_id, second_id = first._scientific_identity, second._scientific_identity
                luminance = [sum(channel * weight for channel, weight in
                                 zip(colors.to_rgb(identity[1]), (0.2126, 0.7152, 0.0722)))
                             for identity in (first_id, second_id)]
                distance = abs(luminance[0] - luminance[1])
                if distance >= GRAYSCALE_DISTANCE:
                    continue
                redundant = first_id[2:] != second_id[2:]
                labels = [first.get_label(), second.get_label()]
                finding = _finding("info" if redundant else "warn", "grayscale",
                                   f"Panel {panel_number}, series {labels!r}: similar grayscale luminance; "
                                   + ("marker/dash differences provide backup; inspect at print width."
                                      if redundant else "no distinct marker/dash backup; inspect at print width."),
                                   measured={"series": labels, "luminance_distance": distance,
                                             "marker_or_dash_backup": redundant}, expected=GRAYSCALE_DISTANCE)
                finding["category"] = "heuristic"
                findings.append(finding)
    return findings


def _inspect_export(path: Path, figure, format_name: str, dpi: int) -> tuple[dict, list]:
    record = {"file": path.name, "requested_format": format_name, "requested_dpi": dpi}
    findings = []

    def error(rule, message, measured=None, expected=None):
        finding = _finding("error", rule, f"{path.name}: {message}", measured, expected)
        finding["category"] = "actual_file"
        findings.append(finding)

    try:
        with Image.open(path) as image:
            image.load()
            try:
                resolutions = [float(value) for value in image.info.get("dpi", ())]
            except (TypeError, ValueError, OverflowError):
                resolutions = []
            record.update({"format": image.format, "mode": image.mode, "pixels": list(image.size),
                           "dpi": [value if np.isfinite(value) else None for value in resolutions],
                           "opaque_alpha": image.getchannel("A").getextrema() == (255, 255)
                           if "A" in image.getbands() else None})
        metadata = getattr(figure, "scientific_metadata", {})
        requested_mm = [metadata.get("width_mm", figure.get_figwidth() * 25.4),
                        metadata.get("height_mm", figure.get_figheight() * 25.4)]
        expected_pixels = [float(size) / 25.4 * dpi for size in requested_mm]
        record.update(requested_physical_mm=requested_mm, requested_pixels=expected_pixels)
        if record["format"] != {"jpeg": "JPEG", "tiff": "TIFF"}[format_name]:
            error("file_format", "actual format differs from the request.", record["format"], format_name)
        if any(abs(actual - expected) > 1.01 for actual, expected in zip(record["pixels"], expected_pixels)):
            error("file_pixels", "pixel dimensions differ from the request (one-pixel tolerance).",
                  record["pixels"], expected_pixels)
        actual_dpi = record["dpi"]
        if len(actual_dpi) != 2 or any(value is None or value <= 0 or abs(value - dpi) > 0.05
                                       for value in actual_dpi):
            error("file_dpi", "DPI is missing or differs from the request.", actual_dpi, dpi)
        else:
            record["physical_mm"] = [pixels / resolution * 25.4
                                     for pixels, resolution in zip(record["pixels"], actual_dpi)]
        expected_modes = ("RGB", "RGBA") if format_name == "tiff" else ("RGB",)
        if record["mode"] not in expected_modes or record["opaque_alpha"] is False:
            finding = _finding("warn", "file_color", f"{path.name}: inspect unexpected color mode or transparency.",
                               measured=record["mode"], expected=list(expected_modes))
            finding["category"] = "actual_file"
            findings.append(finding)
        record["sha256"] = _sha256(path)
    except (OSError, ValueError, TypeError, SyntaxError) as exc:
        error("file_decode", f"cannot fully decode exported image ({type(exc).__name__}).")
    return record, findings


def _write_review(figure, paths: list[Path], requested_font: str, notices: list[str]) -> list[Path]:
    metadata = figure.scientific_metadata
    findings = [{"category": "journal_snapshot", **finding} for finding in review_figure(figure)]
    findings.extend(_grayscale_findings(figure))
    for message in dict.fromkeys(notices):
        finding = _finding("warn", "runtime_notice", message)
        finding["category"] = "runtime"
        findings.append(finding)
    exports = []
    for path, format_name in zip(paths, metadata["formats"]):
        record, file_findings = _inspect_export(path, figure, format_name, metadata["dpi_by_format"][format_name])
        exports.append(record)
        findings.extend(file_findings)
    fonts = _font_record(figure, requested_font)
    manual = ["Check units, reference identity, scientific meaning and caption against the source data.",
              "Inspect legend/data overlap, inset placement and grayscale distinction at final physical width.",
              "Inspect glyph/math fallback and any journal requirements absent from this dated snapshot."]
    report = {"schema_version": DELIVERY_SCHEMA_VERSION, "snapshot_date": SNAPSHOT_DATE,
              "journal": metadata["journal"], "scope": "Figure properties and actual JPEG/TIFF exports; not a submission verdict.",
              "fonts": fonts, "exports": exports, "findings": findings, "manual_checks": manual,
              "grayscale_heuristic": {"threshold": GRAYSCALE_DISTANCE,
                                      "formula": "abs(delta(0.2126 R + 0.7152 G + 0.0722 B)), encoded sRGB",
                                      "limitation": "Series-only screening, not a color-vision certification; no automatic styling changes."}}
    decisions = [{"panel": index, **{key: panel.get(key) for key in ("palette", "focus", "encoding", "secondary_y")}}
                 for index, panel in enumerate(metadata.get("panels", [metadata]), 1)
                 if panel.get("encoding") is not None or panel.get("secondary_y") is not None or panel.get("palette", "classic") != "classic"]
    if decisions:
        report["visual_decisions"] = decisions
    analyses = [{"panel": index, "analysis": panel["analysis"]}
                for index, panel in enumerate(metadata.get("panels", [metadata]), 1) if panel.get("analysis") is not None]
    if analyses:
        report["quantitative_analysis"] = analyses
    uncertainties = [{"panel": index, "definition": panel["error_bars"]["definition"],
                      "display": panel["error_bars"]["display"], "alpha": panel["error_bars"]["alpha"]}
                     for index, panel in enumerate(metadata.get("panels", [metadata]), 1)
                     if panel.get("error_bars") is not None]
    if uncertainties:
        report["uncertainty"] = uncertainties
    target = paths[0].with_suffix("")
    report_paths = [target.with_name(target.name + "_review.json"), target.with_name(target.name + "_review.md")]
    _json_write(report_paths[0], report)
    lines = ["# Figure delivery review", "", report["scope"],
             f"", f"Rule snapshot: {SNAPSHOT_DATE}; journal: {metadata['journal']}", "", "## Actual files"]
    for record in exports:
        lines.append(f"- {record['file']}: {record.get('format', 'unreadable')}; mode={record.get('mode')}; "
                     f"pixels={record.get('pixels')}; DPI={record.get('dpi')}; mm={record.get('physical_mm')}")
    lines.extend(["", "## Fonts", f"- Requested: {requested_font}"])
    lines.extend(f"- Resolved: {face['family']} ({face['file']}); SHA-256: {face['sha256']}" for face in fonts["resolved"])
    lines.extend(["", "## Findings"])
    lines.extend(f"- [{finding['severity']}] {finding['category']}/{finding['rule']}: {finding['message']}"
                 for finding in findings)
    if not findings:
        lines.append("- No findings from implemented checks; manual inspection is still required.")
    if decisions:
        lines.extend(["", "## Visual decisions"])
        for decision in decisions:
            lines.append(f"- Panel {decision['panel']}: palette={decision['palette']}; focus={decision['focus']!r}")
            if decision["encoding"] is not None:
                lines.append(f"  - Encoding: {decision['encoding']['reason']}")
            if decision["secondary_y"] is not None:
                dual = decision["secondary_y"]
                lines.append(f"  - Independent axes: {dual['reason']}")
    if analyses:
        lines.extend(["", "## Quantitative analysis"])
        for record in analyses:
            lines.append(f"- Panel {record['panel']}: " + json.dumps(record["analysis"], ensure_ascii=False))
    if uncertainties:
        lines.extend(["", "## Uncertainty"])
        for record in uncertainties:
            lines.append(f"- Panel {record['panel']}: {record['display']}; {record['definition']}; alpha={record['alpha']}")
    lines.extend(["", "## Manual checks", *[f"- {item}" for item in manual], "",
                  "Grayscale screening uses encoded-sRGB luminance distance < 0.08 plus marker/dash backup; "
                  "it is heuristic, not certification."])
    report_paths[1].write_text("\n".join(lines) + "\n", encoding="utf-8")
    figure.scientific_report = report
    figure.scientific_report_paths = report_paths
    figure.scientific_review = findings
    if any(finding["severity"] == "error" for finding in findings):
        raise ValueError(f"Export verification failed; saved reports at {report_paths[0]} and {report_paths[1]}.")
    return report_paths


def _delivery(function):
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        options = bound.arguments
        bundle = options["bundle"]
        if options["include_data"] and bundle is None:
            raise ValueError("include_data requires an explicit bundle directory.")
        enabled = options["report"] or bundle is not None
        if not enabled:
            return function(*args, **kwargs)
        if options["output"] is None:
            raise ValueError("report and bundle require an explicit output path.")
        if options.get("host_axes") is not None:
            raise ValueError("Request report/bundle on the outer figure, not host_axes.")
        if bundle is not None:
            destination = Path(bundle).resolve()
            if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
                raise ValueError("Bundle destination must be absent or an empty directory.")
            if Path(options["output"]).resolve().is_relative_to(destination):
                raise ValueError("Output must be outside the bundle destination.")
        captured = []
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", UserWarning)
                result = function(*args, **kwargs)
                figure, _, paths = result
                _write_review(figure, paths, options["font"], [str(item.message) for item in captured])
                if bundle is not None:
                    _write_bundle(figure, paths, options, function.__name__, destination)
        finally:
            for item in captured:
                warnings.warn_explicit(item.message, item.category, item.filename, item.lineno)
        return result

    return wrapped


def _encode_scalar(value):
    if value is pd.NA:
        return {"scalar": "NA"}
    if value is pd.NaT:
        return {"scalar": "NaT"}
    if isinstance(value, pd.Timestamp):
        return {"scalar": "timestamp", "value": value.isoformat()}
    if isinstance(value, pd.Timedelta):
        return {"scalar": "timedelta", "value": value.value}
    if isinstance(value, np.generic):
        scalar = value.item()
        if isinstance(scalar, np.generic):
            raise ValueError(f"Cannot losslessly snapshot scalar dtype {value.dtype}; no implicit conversion was applied.")
        return _encode_scalar(scalar)
    if isinstance(value, float) and not np.isfinite(value):
        return {"scalar": "float", "value": repr(value)}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, tuple):
        return {"scalar": "tuple", "value": [_encode_scalar(item) for item in value]}
    raise ValueError(f"Cannot losslessly snapshot scalar type {type(value).__name__}; provide a supported table explicitly.")


def _decode_scalar(value):
    if not isinstance(value, dict):
        return value
    kind = value.get("scalar")
    if kind == "NA":
        return pd.NA
    if kind == "NaT":
        return pd.NaT
    if kind == "timestamp":
        return pd.Timestamp(value["value"])
    if kind == "timedelta":
        return pd.Timedelta(value["value"], unit="ns")
    if kind == "float" and value.get("value") in ("nan", "inf", "-inf"):
        return float(value["value"])
    if kind == "tuple":
        return tuple(_decode_scalar(item) for item in value["value"])
    raise ValueError("Unsupported snapshot scalar encoding.")


def _encode_vector(series: pd.Series) -> dict:
    result = {"dtype": str(series.dtype), "values": [_encode_scalar(value) for value in series]}
    if isinstance(series.dtype, pd.CategoricalDtype):
        result["categories"] = _encode_index(series.cat.categories)
        result["ordered"] = series.cat.ordered
    if isinstance(series.dtype, pd.StringDtype):
        result["string_storage"] = series.dtype.storage
        result["string_na"] = _encode_scalar(series.dtype.na_value)
    return result


def _decode_vector(spec: dict) -> pd.Series:
    values = [_decode_scalar(value) for value in spec["values"]]
    dtype = spec["dtype"]
    if dtype == "category":
        dtype = pd.CategoricalDtype(_decode_index(spec["categories"]), ordered=spec["ordered"])
    elif "string_storage" in spec:
        string_options = {"storage": spec["string_storage"]}
        if "na_value" in inspect.signature(pd.StringDtype).parameters:
            string_options["na_value"] = _decode_scalar(spec["string_na"])
        elif spec["string_na"] != {"scalar": "NA"}:
            raise ValueError("This pandas version cannot preserve the snapshot string missing-value semantics.")
        dtype = pd.StringDtype(**string_options)
    return pd.Series(values, dtype=dtype)


def _encode_index(index: pd.Index) -> dict:
    if isinstance(index, pd.MultiIndex):
        return {"kind": "multi", "levels": [_encode_index(level) for level in index.levels],
                "codes": [code.tolist() for code in index.codes], "names": [_encode_scalar(name) for name in index.names]}
    if isinstance(index, pd.RangeIndex):
        return {"kind": "range", "start": index.start, "stop": index.stop, "step": index.step,
                "name": _encode_scalar(index.name)}
    result = {"kind": "index", "vector": _encode_vector(pd.Series(index)), "name": _encode_scalar(index.name)}
    if isinstance(index, (pd.DatetimeIndex, pd.TimedeltaIndex)):
        result["frequency"] = index.freqstr
    return result


def _decode_index(spec: dict) -> pd.Index:
    if spec["kind"] == "multi":
        return pd.MultiIndex(levels=[_decode_index(level) for level in spec["levels"]], codes=spec["codes"],
                             names=[_decode_scalar(name) for name in spec["names"]])
    if spec["kind"] == "range":
        return pd.RangeIndex(spec["start"], spec["stop"], spec["step"], name=_decode_scalar(spec["name"]))
    index = pd.Index(_decode_vector(spec["vector"]).array, name=_decode_scalar(spec["name"]))
    if spec.get("frequency") is not None:
        index.freq = spec["frequency"]
    return index


def _snapshot_payload(frame: pd.DataFrame) -> dict:
    payload = {"schema_version": DELIVERY_SCHEMA_VERSION, "columns": _encode_index(frame.columns),
               "index": _encode_index(frame.index),
               "vectors": [_encode_vector(frame.iloc[:, index]) for index in range(frame.shape[1])]}
    try:
        restored = _snapshot_frame(payload)
        pd.testing.assert_frame_equal(frame, restored, check_exact=True)
    except (TypeError, ValueError, AssertionError) as exc:
        raise ValueError("Cannot losslessly snapshot this table; no lossy conversion was applied.") from exc
    return payload


def _snapshot_frame(payload: dict) -> pd.DataFrame:
    if payload.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        raise ValueError("Unsupported snapshot schema version.")
    frame = pd.concat([_decode_vector(vector) for vector in payload["vectors"]], axis=1)
    frame.columns = _decode_index(payload["columns"])
    frame.index = _decode_index(payload["index"])
    return frame


def _config_value(value):
    if isinstance(value, np.generic):
        return _config_value(value.item())
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_config_value(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _config_value(item) for key, item in value.items()}
    raise ValueError(f"Unsupported bundle configuration type {type(value).__name__}; no implicit conversion was applied.")


def _recipe_inputs(options: dict, renderer: str) -> tuple[dict, dict]:
    inputs = {}
    excluded = {"output", "report", "bundle", "include_data", "data", "panels", "host_axes", "host_error_axes"}
    recipe = {"renderer": renderer,
              "options": {key: value for key, value in options.items() if key not in excluded}}
    panel_keys = {"id", "kind", "x", "y", "group", "value", "group_kind", "xlabel", "ylabel", "line_width",
                  "marker_size", "xscale", "yscale", "series_styles", "error", "error_bars", "legend",
                  "reference_guides", "inset", "heatmap_scale", "quantity", "unit", "palette", "focus", "encoding", "secondary_y", "analysis"}

    def panel_recipe(data, settings, identifier):
        settings = dict(settings)
        frame = _frame(data, settings["kind"])
        matrix = settings["kind"] == "heatmap" and not any(settings.get(key) is not None for key in ("x", "y", "value"))
        if not matrix:
            mapping_keys = ("x", "y", "value") if settings["kind"] == "heatmap" else ("x", "y", "group")
            if settings["kind"] == "violin":
                mapping_keys = ("x", "y")
            columns = [settings[key] for key in mapping_keys if settings.get(key) is not None]
            analysis = settings.get("analysis") or {}
            columns.extend(analysis[key] for key in ("weight", "order") if analysis.get(key) is not None)
            error_bars = settings.get("error_bars")
            if error_bars is not None:
                error_bars = dict(error_bars)
                for key in ("x", "y", "x_lower", "x_upper", "y_lower", "y_upper"):
                    if key not in error_bars:
                        continue
                    magnitude = error_bars[key]
                    if isinstance(magnitude, str):
                        columns.append(magnitude)
                    elif not np.isscalar(magnitude) and np.asarray(magnitude).ndim != 0:
                        auxiliary_id = identifier + "_" + key + "err"
                        inputs[auxiliary_id] = (pd.DataFrame({"magnitude": np.asarray(magnitude, dtype=float)}), False, True)
                        error_bars[key] = {"__bundle_input__": auxiliary_id}
                    else:
                        error_bars[key] = float(np.asarray(magnitude))
                settings["error_bars"] = error_bars
            frame = frame.loc[:, list(dict.fromkeys(columns))]
        inputs[identifier] = (frame, matrix, False)
        settings["data"] = {"__bundle_input__": identifier}
        return settings

    if renderer == "render_plot":
        panel = panel_recipe(options["data"], recipe["options"], "main")
        recipe["options"] = panel
    else:
        recipe["panels"] = [panel_recipe(panel["data"], {key: value for key, value in panel.items() if key in panel_keys},
                                                f"panel_{index}") for index, panel in enumerate(options["panels"])]
    return _config_value(recipe), inputs


def _environment_record(package_names=None) -> dict:
    versions = {}
    names = list(package_names) if package_names is not None else ["matplotlib", "numpy", "pandas", "Pillow"]
    if package_names is None:
        names.extend(name for name in ("pyarrow", "openpyxl", "xlrd") if name in sys.modules)
    for name in names:
        try:
            versions[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "packages": versions}


_REPLAY_LAUNCHER = '''from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parent
try:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported bundle schema version")
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Missing or unsafe managed path: " + name)
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1048576), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Checksum mismatch: " + name)
except (OSError, ValueError, KeyError, TypeError) as error:
    raise SystemExit("Bundle verification failed: " + str(error))
try:
    from plot_template import replay_bundle
except ImportError as error:
    raise SystemExit("Missing runtime dependency: " + str(error) + ". Install dependencies manually; see requirements-recorded.txt.")
replay_bundle(root, sys.argv[1:])
'''


def _write_bundle(figure, paths: list[Path], options: dict, renderer: str, destination: Path) -> None:
    recipe, inputs = _recipe_inputs(options, renderer)
    snapshots = {identifier: _snapshot_payload(frame) for identifier, (frame, _, _) in inputs.items()} if options["include_data"] else {}
    environment = _environment_record()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".plot-bundle-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        shutil.copy2(Path(__file__).resolve(), staging / "plot_template.py")
        (staging / "reproduce.py").write_text(_REPLAY_LAUNCHER, encoding="utf-8")
        _json_write(staging / "recipe.json", recipe)
        entries = []
        for identifier, (frame, matrix, auxiliary) in inputs.items():
            filename = f"inputs/{identifier}.json" if options["include_data"] else None
            entries.append({"id": identifier, "file": filename, "matrix": matrix, "auxiliary": auxiliary,
                            "columns": [_encode_scalar(column) for column in frame.columns],
                            "rows": len(frame), "dtypes": [str(dtype) for dtype in frame.dtypes]})
            if filename is not None:
                (staging / "inputs").mkdir(exist_ok=True)
                _json_write(staging / filename, snapshots[identifier])
        artifacts = staging / "artifacts"
        artifacts.mkdir()
        for path in [*paths, *figure.scientific_report_paths]:
            shutil.copy2(path, artifacts / path.name)
        requirements = [f"{name}=={version}" for name, version in environment["packages"].items() if version is not None]
        (staging / "requirements-recorded.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
        (staging / "README.md").write_text(
            "# Scientific plotting delivery bundle\n\n"
            + ("Input snapshots are included with explicit permission.\n" if options["include_data"] else
               "Inputs are NOT included. This is NOT a self-contained replay bundle.\n")
            + "\nRun `python reproduce.py`; missing inputs require `--input ID=PATH` for every listed ID.\n"
            "External inputs: snapshot JSON or CSV; matrix CSVs must include a first row-label column.\n"
            "Array-valued error bars have separate one-column magnitude inputs. IDs are in manifest.json.\n"
            "Default output is replayed/figure; use --output-dir DIR to select a fresh output directory.\n"
            "Managed files are verified before importing the pinned template. Do not edit them for replay.\n"
            "Nothing downloads or installs automatically. Install dependencies yourself when necessary.\n"
            "Recorded versions do not restore an environment. Fonts are recorded, not copied.\n"
            "Checksums detect changes, not authenticity. Across environments byte-identical images are not promised.\n"
            "Only used table columns and the selected Excel sheet are snapshotted, never the whole workbook.\n"
            "Reports/images and labels still disclose plotted information; review the bundle before sharing.\n",
            encoding="utf-8")
        managed = {path.relative_to(staging).as_posix(): _sha256(path) for path in sorted(staging.rglob("*")) if path.is_file()}
        manifest = {"schema_version": DELIVERY_SCHEMA_VERSION, "include_data": bool(options["include_data"]),
                    "self_contained": bool(options["include_data"]), "inputs": entries, "environment": environment,
                    "fonts": figure.scientific_report["fonts"], "files": managed,
                    "snapshot_date": SNAPSHOT_DATE, "recipe": "recipe.json"}
        _json_write(staging / "manifest.json", manifest)
        if destination.exists():
            if any(destination.iterdir()):
                raise ValueError("Bundle destination is no longer empty; nothing was overwritten.")
            destination.rmdir()
        staging.rename(destination)
    figure.scientific_bundle_path = destination


def _bundle_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Unsafe bundle path.")
    return path


def _verify_bundle(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        raise ValueError("Unsupported bundle schema version.")
    for name, expected in manifest["files"].items():
        path = _bundle_path(root, name)
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"Bundle checksum mismatch or missing file: {name}")
    return manifest


def replay_bundle(root: str | Path, argv: list[str] | None = None):
    """Verify a delivery bundle and replay from snapshots or explicit external inputs."""
    root = Path(root).resolve()
    manifest = _verify_bundle(root)
    parser = argparse.ArgumentParser(description="Replay a verified scientific-plotting delivery bundle without downloads.")
    parser.add_argument("--input", action="append", default=[], help="Explicit replacement input ID=PATH (CSV or snapshot JSON)")
    parser.add_argument("--output-dir", type=Path, default=root / "replayed")
    arguments = parser.parse_args(argv)
    replacements = {}
    for mapping in arguments.input:
        identifier, separator, filename = mapping.partition("=")
        if not separator or not filename or identifier in replacements:
            parser.error("Use one --input ID=PATH for each replacement input.")
        replacements[identifier] = Path(filename)
    expected_ids = {entry["id"] for entry in manifest["inputs"]}
    if replacements.keys() - expected_ids:
        parser.error(f"Unknown input IDs: {sorted(replacements.keys() - expected_ids)}")
    missing = [entry["id"] for entry in manifest["inputs"] if entry["file"] is None and entry["id"] not in replacements]
    if missing:
        parser.error("Missing inputs; supply --input ID=PATH for: " + ", ".join(missing))
    inputs = {}
    for entry in manifest["inputs"]:
        path = replacements.get(entry["id"])
        if path is None:
            path = _bundle_path(root, entry["file"])
        if path.suffix.lower() == ".json":
            frame = _snapshot_frame(json.loads(path.read_text(encoding="utf-8")))
        elif path.suffix.lower() == ".csv":
            frame = pd.read_csv(path, index_col=0 if entry["matrix"] else None, float_precision="round_trip")
        else:
            raise ValueError("Replay inputs must be snapshot JSON or CSV; export the selected Excel sheet explicitly.")
        columns = [_decode_scalar(column) for column in entry["columns"]]
        if list(frame.columns) != columns:
            if not entry["matrix"] and set(columns).issubset(frame.columns):
                frame = frame.loc[:, columns]
            else:
                raise ValueError(f"Input columns differ for {entry['id']}; use a typed snapshot for non-string labels.")
        inputs[entry["id"]] = frame.iloc[:, 0].to_numpy(dtype=float) if entry["auxiliary"] else frame
    output_dir = arguments.output_dir.resolve()
    protected = [_bundle_path(root, name) for name in manifest["files"]]
    if any(path.is_relative_to(output_dir) for path in protected) or (output_dir.exists() and
            (not output_dir.is_dir() or any(output_dir.iterdir()))):
        raise ValueError("Replay output must be a fresh/empty directory, separate from managed bundle files.")
    current = _environment_record(manifest["environment"]["packages"])
    if current != manifest["environment"]:
        warnings.warn("Runtime versions differ from the recorded environment; no dependencies were installed automatically.", UserWarning)
    recipe = json.loads(_bundle_path(root, manifest["recipe"]).read_text(encoding="utf-8"))

    def restore(value):
        if isinstance(value, dict):
            if value.keys() == {"__bundle_input__"}:
                return inputs[value["__bundle_input__"]]
            return {key: restore(item) for key, item in value.items()}
        if isinstance(value, list):
            return [restore(item) for item in value]
        return value

    options = restore(recipe["options"])
    options.update(output=output_dir / "figure", report=True)
    if recipe["renderer"] == "render_plot":
        result = render_plot(**options)
    elif recipe["renderer"] == "render_multipanel":
        result = render_multipanel(restore(recipe["panels"]), **options)
    else:
        raise ValueError("Unsupported bundle renderer.")
    if result[0].scientific_report["fonts"] != manifest["fonts"]:
        warnings.warn("Resolved fonts differ from the bundle; inspect the regenerated text layout.", UserWarning)
    return result


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
        for handle, label in zip(*_legend_entries(axes)):
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
        for panel in _series_axes(axes):
            existing = panel.get_legend()
            if existing is not None:
                existing.remove()
    if not handles:
        return
    def make_legend(columns: int, loc: str, anchor: tuple[float, float]):
        return figure.legend(handles, labels, loc=loc, bbox_to_anchor=anchor, bbox_transform=figure.transFigure,
                             ncol=columns, frameon=True, framealpha=1, facecolor="white", edgecolor="#777777",
                             fontsize=legend_size, borderaxespad=0)

    legend = _fit_outside_band(figure, axes_list, make_legend, len(handles), sides=("top",), min_fraction=0.35)
    if legend is None:
        raise ValueError("Legend does not fit this preset; select a larger size or simplify labels.")
    for source, target in zip(handles, legend.legend_handles):
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


def _analysis_edges(values: np.ndarray, bins, name: str) -> np.ndarray:
    if isinstance(bins, (int, np.integer)) and not isinstance(bins, (bool, np.bool_)):
        if not 1 <= bins <= 1000:
            raise ValueError(f"{name} requires 1 to 1000 bins.")
        return np.histogram_bin_edges(values, bins=int(bins))
    try:
        edges = np.asarray(bins, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} requires an integer or explicit increasing edges.") from exc
    if (edges.ndim != 1 or not 2 <= len(edges) <= 1001 or not np.isfinite(edges).all()
            or np.any(np.diff(edges) <= 0)):
        raise ValueError(f"{name} requires finite, strictly increasing edges (1 to 1000 bins).")
    if values.min() < edges[0] or values.max() > edges[-1]:
        raise ValueError(f"{name} edges exclude observations; no rows were removed.")
    return edges


def _analysis_spec(frame, kind, x, y, group, analysis, group_kind):
    allowed = {
        "histogram": {"bins", "statistic", "weight", "weight_definition"},
        "ecdf": {"weight", "weight_definition"},
        "box": {"whis"},
        "joint": {"bins", "statistic", "weight", "weight_definition", "vmax"},
        "trajectory": {"order", "arrows"},
        "contribution": {"definition"},
    }
    if analysis is None:
        analysis = {}
    if not isinstance(analysis, dict) or analysis.keys() - allowed[kind]:
        raise ValueError(f"analysis for {kind} accepts only {sorted(allowed[kind])}.")
    _required(frame, x)
    if kind not in ("joint", "trajectory", "contribution") and y is not None:
        raise ValueError(f"{kind} uses x for samples and group for categories; omit y.")
    if kind in ("joint", "trajectory", "contribution"):
        _required(frame, y)
        _numeric(frame, y)
    if kind != "contribution":
        _numeric(frame, x)
    if group is not None:
        _required(frame, group)
    ordered = _ordered_groups(frame, group, group_kind)
    groups = _groups(frame, group, ordered)
    if group is not None and frame[group].map(str).nunique() != frame[group].nunique():
        raise ValueError("Group labels must remain distinct when converted to strings.")
    if kind == "joint" and group is not None:
        raise ValueError("joint requires one population per panel; use facets instead of overlaying densities.")
    if len(groups) > len(CATEGORICAL_COLORS):
        raise ValueError("Too many analysis groups; divide them into panels.")
    spec = dict(analysis)
    spec["groups"] = groups
    spec["ordered"] = ordered
    metadata = {"kind": kind, "sample_sizes": {label: len(subset) for label, subset in groups},
                "processing": "No smoothing, fitting, row exclusion or resampling."}
    weight = spec.get("weight")
    if weight is not None:
        _required(frame, weight)
        weights = _numeric(frame, weight)
        if np.any(weights < 0):
            raise ValueError("Weights must be nonnegative.")
        definition = spec.get("weight_definition")
        if not isinstance(definition, str) or not definition.strip():
            raise ValueError("Weighted distributions require weight_definition (e.g. cell volume).")
        for _, subset in groups:
            total = _numeric(subset, weight).sum()
            if not np.isfinite(total) or total <= 0:
                raise ValueError("Each population requires positive finite total weight.")
        metadata.update(weight=weight, weight_definition=definition,
                        weight_sums={label: float(_numeric(subset, weight).sum()) for label, subset in groups})
    elif "weight_definition" in spec:
        raise ValueError("weight_definition requires a weight column.")
    if kind in ("histogram", "joint"):
        if "bins" not in spec or "statistic" not in spec:
            raise ValueError(f"{kind} requires explicit bins and statistic (count, probability or density).")
        if spec["statistic"] not in ("count", "probability", "density"):
            raise ValueError("statistic must be count, probability or density.")
        if kind == "joint":
            if not isinstance(spec["bins"], (list, tuple)) or len(spec["bins"]) != 2:
                raise ValueError("joint bins must contain [x_bins, y_bins].")
            spec["edges"] = [_analysis_edges(_numeric(frame, column), bins, column)
                             for column, bins in zip((x, y), spec["bins"])]
            if np.prod([len(edges) - 1 for edges in spec["edges"]]) > 250000:
                raise ValueError("joint supports at most 250000 cells; choose coarser bins.")
            metadata["bin_edges"] = [edges.tolist() for edges in spec["edges"]]
            if "vmax" in spec:
                maximum = _finite_number(spec["vmax"], "joint vmax")
                if isinstance(spec["vmax"], bool) or maximum <= 0:
                    raise ValueError("joint vmax must be positive and finite.")
                spec["vmax"] = maximum
        else:
            spec["edges"] = _analysis_edges(_numeric(frame, x), spec["bins"], "bins")
            metadata["bin_edges"] = spec["edges"].tolist()
        metadata.update(statistic=spec["statistic"], normalization="Per population; all observations included.")
    if kind == "ecdf":
        metadata.update(statistic="empirical cumulative probability",
                        processing="Stable sample sort for ECDF only; ties combined; no smoothing or row exclusion.")
    if kind == "box":
        whis = spec.get("whis", 1.5)
        if isinstance(whis, bool) or not np.isscalar(whis) or not np.isfinite(float(whis)) or float(whis) <= 0:
            raise ValueError("box whis must be a positive finite IQR multiplier.")
        spec["whis"] = float(whis)
        metadata.update(whis=spec["whis"], definition="Median, Q1/Q3; whiskers within whis * IQR; all fliers shown.")
    if kind == "trajectory":
        order = spec.get("order")
        arrows = spec.get("arrows", [])
        if not isinstance(arrows, (list, tuple)) or any(isinstance(index, bool) or not isinstance(index, (int, np.integer))
                                                      or index < 0 for index in arrows) or len(set(arrows)) != len(arrows):
            raise ValueError("trajectory arrows must be unique nonnegative segment indices.")
        for _, subset in groups:
            if len(subset) < 2:
                raise ValueError("Each trajectory requires at least two observations.")
            if order is not None:
                _required(subset, order)
                if np.any(np.diff(_numeric(subset, order)) <= 0):
                    raise ValueError("trajectory order must strictly increase within each group; rows are never sorted.")
            if any(index >= len(subset) - 1 for index in arrows):
                raise ValueError("trajectory arrow index exceeds a group's available segments.")
            for index in arrows:
                if subset.iloc[index][x] == subset.iloc[index + 1][x] and subset.iloc[index][y] == subset.iloc[index + 1][y]:
                    raise ValueError("Direction arrow requires a nonzero trajectory segment.")
        metadata.update(order=order or "original within-group row order", arrows=[int(index) for index in arrows],
                        definition="Open parametric path; no inferred loop closure, cycle or hysteresis area.")
    if kind == "contribution":
        definition = spec.get("definition")
        if not isinstance(definition, str) or not definition.strip():
            raise ValueError("contribution requires definition describing the terms and sign convention.")
        for _, subset in groups:
            if subset[x].astype(str).duplicated().any():
                raise ValueError("Repeated contribution term; aggregate explicitly before plotting.")
        metadata.update(definition=definition, baseline=0, normalization="None; supplied signed values, not percentages.")
    spec["metadata"] = metadata
    return spec


def _draw_analysis(axes, frame, kind, x, y, spec, palette, focus, families, draw_colorbar):
    groups = spec["groups"]
    palette_colors = _palette(len(groups), spec["ordered"], palette,
                              next((index for index, (label, _) in enumerate(groups) if label == focus), None))
    labels = {"count": "Weighted count" if spec.get("weight") else "Count",
              "probability": "Probability (-)", "density": "Probability density"}
    if kind == "joint":
        weights = _numeric(frame, spec["weight"]) if spec.get("weight") else None
        counts, xedges, yedges = np.histogram2d(_numeric(frame, x), _numeric(frame, y), bins=spec["edges"], weights=weights)
        values = counts.copy()
        if spec["statistic"] != "count":
            values /= counts.sum()
        if spec["statistic"] == "density":
            values /= np.diff(xedges)[:, None] * np.diff(yedges)[None, :]
        if not np.isfinite(values).all():
            raise ValueError("Joint bin values are non-finite; check weights and bin widths.")
        if spec.get("vmax") is not None and values.max() > spec["vmax"]:
            raise ValueError("joint vmax excludes bin values; expand the scale instead of clipping.")
        image = axes.pcolormesh(xedges, yedges, values.T, cmap="cividis", shading="flat", vmin=0, vmax=spec.get("vmax"))
        spec["metadata"]["color_limits"] = [0, float(image.norm.vmax)]
        axes.grid(False, which="both")
        if draw_colorbar:
            axes.figure.colorbar(image, ax=axes, label=_prepare_label(labels[spec["statistic"]], families), fraction=0.05, pad=0.03)
        return x, y
    if kind == "box":
        parts = axes.boxplot([_numeric(subset, x) for _, subset in groups], patch_artist=True,
                             whis=spec["whis"], showfliers=True,
                             medianprops={"color": "#292929", "linewidth": 1.2},
                             flierprops={"marker": "o", "markersize": 3, "markerfacecolor": "none", "markeredgecolor": "#333333"})
        for patch, color in zip(parts["boxes"], palette_colors):
            patch.set_facecolor(color)
            patch.set_edgecolor("#333333")
        axes.set_xticks(np.arange(1, len(groups) + 1), [_prepare_label(label or "Data", families) for label, _ in groups])
        return "", x
    categories = list(pd.unique(frame[x].astype(str))) if kind == "contribution" else None
    for index, ((label, subset), color) in enumerate(zip(groups, palette_colors)):
        samples = _numeric(subset, x) if kind != "contribution" else None
        weights = _numeric(subset, spec["weight"]) if spec.get("weight") else None
        if kind == "histogram":
            values, edges = np.histogram(samples, bins=spec["edges"], weights=weights)
            values = values.astype(float)
            if spec["statistic"] != "count":
                values /= values.sum()
            if spec["statistic"] == "density":
                values /= np.diff(edges)
            if not np.isfinite(values).all():
                raise ValueError("Histogram values are non-finite; check weights and bin widths.")
            axes.stairs(values, edges, label=label, color=color, linewidth=1.2, linestyle=LINESTYLES[index])
        elif kind == "ecdf":
            order = np.argsort(samples, kind="stable")
            sorted_samples = samples[order]
            mass = np.ones(len(samples)) if weights is None else weights[order]
            cumulative = np.cumsum(mass) / mass.sum()
            ends = np.r_[sorted_samples[1:] != sorted_samples[:-1], True]
            coordinates = sorted_samples[ends]
            axes.step(np.r_[coordinates[0], coordinates], np.r_[0, cumulative[ends]], where="post",
                      label=label, color=color, linewidth=1.2, linestyle=LINESTYLES[index])
        elif kind == "trajectory":
            ordinates = _numeric(subset, y)
            axes.plot(samples, ordinates, label=label, color=color, linewidth=1.2, linestyle=LINESTYLES[index])
            axes.plot(samples[0], ordinates[0], marker="o", markersize=4, color=color, linestyle="none")
            for segment in spec.get("arrows", []):
                axes.annotate("", xy=(samples[segment + 1], ordinates[segment + 1]), xytext=(samples[segment], ordinates[segment]),
                              arrowprops={"arrowstyle": "->", "color": color, "lw": 1.2})
        else:
            positions = [categories.index(str(category)) for category in subset[x]]
            width = 0.8 / len(groups)
            centers = np.asarray(positions) + (index - (len(groups) - 1) / 2) * width
            axes.bar(centers, _numeric(subset, y), width=width, label=label, color=color,
                     edgecolor="#333333", linewidth=0.65, hatch=("", "//", "xx", "..", "\\\\", "++", "oo", "--")[index])
    if kind == "contribution":
        axes.axhline(0, color="#292929", linewidth=0.9)
        axes.set_xticks(np.arange(len(categories)), [_prepare_label(category, families) for category in categories])
    if kind == "ecdf":
        axes.set_ylim(0, 1.02)
    return x, labels[spec["statistic"]] if kind == "histogram" else "Cumulative probability (-)" if kind == "ecdf" else y


@_delivery
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
    style_registry: dict | None = None,
    palette: str = "classic",
    focus: str | None = None,
    encoding: dict | None = None,
    secondary_y: dict | None = None,
    reference_guides: list[dict] | None = None,
    inset: dict | None = None,
    heatmap_scale: dict | None = None,
    analysis: dict | None = None,
    error: dict | None = None,
    error_bars: dict | None = None,
    legend: str = "auto",
    journal: str = "elsevier",
    height_mm: float | None = None,
    host_axes: mpl.axes.Axes | None = None,
    host_error_axes: mpl.axes.Axes | None = None,
    apply_layout: bool = True,
    draw_legend: bool = True,
    draw_colorbar: bool = True,
    report: bool = False,
    bundle: str | Path | None = None,
    include_data: bool = False,
) -> tuple[mpl.figure.Figure, mpl.axes.Axes, list[Path]]:
    """Draw without changing input data; return figure, axes and exported paths."""
    if kind not in KINDS or group_kind not in ("auto", "ordered", "categorical"):
        raise ValueError("Unknown plot kind or group kind.")
    if kind not in ANALYSIS_KINDS and analysis is not None:
        raise ValueError("analysis applies to histogram, ecdf, box, joint, trajectory and contribution only.")
    if kind in ANALYSIS_KINDS and any(option is not None for option in (series_styles, style_registry, encoding, secondary_y,
                                                                       reference_guides, inset, heatmap_scale, error, error_bars)):
        raise ValueError("Analysis plots do not support series styles, registry, encoding, dual axes, guides, insets, heatmap scales or error bars.")
    if kind in ANALYSIS_KINDS and value is not None:
        raise ValueError("Analysis plots use x/y/group mappings, not value.")
    if kind == "joint" and (palette != "classic" or focus is not None):
        raise ValueError("joint uses a quantitative cividis color scale, not categorical palettes.")
    _palette(0, False, palette)
    if (palette == "focus") != (isinstance(focus, str) and bool(focus.strip())) or (palette != "focus" and focus is not None):
        raise ValueError("palette='focus' requires an explicit nonempty focus label; other palettes refuse focus.")
    if kind == "heatmap" and palette != "classic":
        raise ValueError("Categorical palettes do not apply to heatmaps; retain cividis.")
    if encoding is not None and (kind not in (*SERIES_KINDS, "mixed") or group_kind == "ordered"):
        raise ValueError("encoding requires categorical line/point-line/scatter/mixed series.")
    if secondary_y is not None and kind not in SERIES_KINDS:
        raise ValueError("secondary_y supports native line, point-line and scatter only.")
    size = resolve_size(size, journal)
    if xscale not in ("linear", "log") or yscale not in ("linear", "log"):
        raise ValueError("xscale and yscale must be linear or log.")
    if legend not in ("auto", "outside"):
        raise ValueError("legend must be auto or outside.")
    if error is not None and kind not in (*SERIES_KINDS, "mixed"):
        raise ValueError("Error panels require line, point-line, scatter or mixed.")
    if kind not in (*SERIES_KINDS, "mixed") and (xscale != "linear" or yscale != "linear" or series_styles is not None):
        raise ValueError("Axis scales and series_styles apply to line, point-line, scatter and mixed only.")
    guides = _resolve_guides(reference_guides, kind, xscale, yscale)
    inset_spec = _resolve_inset(inset, kind, xscale, yscale)
    heatmap_limits = _heatmap_limits(heatmap_scale)
    if heatmap_scale is not None and kind != "heatmap":
        raise ValueError("heatmap_scale applies to heatmaps only.")
    chosen_formats = resolve_formats(formats)
    dpi_by_format = resolve_dpi(dpi, chosen_formats, journal, kind in ("heatmap", "joint"))
    if line_width is not None and (kind not in ("point-line", "line", "mixed") or isinstance(line_width, bool)
                                   or not np.isfinite(line_width)
                                   or not LINE_WIDTH_MIN_PT <= float(line_width) <= LINE_WIDTH_MAX_PT):
        raise ValueError(f"line_width must be between {LINE_WIDTH_MIN_PT:g} and {LINE_WIDTH_MAX_PT:g} pt "
                         "for point-line, line and mixed.")
    if marker_size is not None and (kind not in ("point-line", "scatter", "mixed") or isinstance(marker_size, bool)
                                    or not np.isfinite(marker_size) or not 0 < float(marker_size) <= 20):
        raise ValueError("marker_size must be a positive finite value up to 20 for point-line, scatter and mixed.")
    face = resolve_font(font)
    families = _font_families(face)
    frame = _frame(data, kind)
    analysis_spec = _analysis_spec(frame, kind, x, y, group, analysis, group_kind) if kind in ANALYSIS_KINDS else None
    if analysis_spec is not None and palette == "focus" and not any(label == focus for label, _ in analysis_spec["groups"]):
        raise ValueError("focus must name a plotted analysis group.")
    if kind in (*SERIES_KINDS, "mixed"):
        _required(frame, x, y)
        for column, scale in ((x, xscale), (y, yscale)):
            numeric = _numeric(frame, column)
            if scale == "log" and (column == x or secondary_y is None) and np.any(numeric <= 0):
                raise ValueError(f"Log axis column {column!r} contains non-positive values; no rows were removed.")
        ordered = False if encoding is not None else _ordered_groups(frame, group, group_kind)
        values = _groups(frame, group, ordered)
        role_styles, encoding_metadata = _encoding_styles(encoding, values, palette, focus)
        if encoding_metadata is not None and secondary_y is None:
            metric_names = {record["metric"] for record in encoding_metadata["observed"]}
            units = {(style["quantity"], style["unit"]) for metric, style in encoding_metadata["metrics"].items()
                     if metric in metric_names and "quantity" in style}
            if len(units) > 1:
                raise ValueError("Different typed metrics cannot share one y axis; use facets or explicit secondary_y.")
        styles = _series_options(values, kind, series_styles, line_width, marker_size, style_registry, palette, focus,
                                 role_styles)
        comparisons, error_metadata = _comparison_errors(values, x, y, error)
    elif style_registry is not None:
        raise ValueError("style_registry applies to line, point-line, scatter and mixed only.")
    if palette == "focus" and encoding is None:
        identity_labels = set((style_registry or {}).keys())
        if kind == "violin" or (kind == "bar" and group is None):
            if x is None:
                identity_labels.add("Data")
            else:
                identity_labels.update(str(item) for item in pd.unique(frame[x]))
        else:
            identity_labels.update(label for label, _ in _groups(frame, group, False))
        if focus not in identity_labels:
            raise ValueError("focus must name a plotted series/category or an entry in style_registry.")
    secondary_spec = _resolve_secondary_y(secondary_y, values if kind in SERIES_KINDS else [], kind=kind,
                                         ylabel=ylabel, yscale=yscale, error=error, inset=inset, guides=guides,
                                         encoding=encoding_metadata if encoding is not None else None)
    error_bar_state = _resolve_error_bars(frame, error_bars, x=x, y=y, kind=kind, xscale=xscale,
                                         yscale="linear" if secondary_spec is not None else yscale)
    if error_bar_state is not None and error_bar_state["display"] == "band":
        if inset is not None:
            raise ValueError("Uncertainty bands with insets are not supported; use separate panels.")
        for label, subset in _groups(frame, group, ordered):
            coordinates = _numeric(subset, x)
            differences = np.diff(coordinates)
            if len(coordinates) < 2 or not (np.all(differences > 0) or np.all(differences < 0)):
                raise ValueError(f"Band series {label!r} requires strictly monotonic x and at least two points; no sorting applied.")
    if secondary_spec is not None:
        for label, subset in _groups(frame, group, ordered):
            axis_spec = secondary_spec if label in secondary_spec["series"] else secondary_spec["primary"]
            scale = secondary_spec["scale"] if label in secondary_spec["series"] else yscale
            coordinates = _numeric(subset, y)
            errors = _axis_errors(subset, "y", error_bar_state) if error_bar_state is not None else None
            lower = coordinates if errors is None else coordinates - errors[0]
            upper = coordinates if errors is None else coordinates + errors[1]
            if scale == "log" and np.any(lower <= 0):
                raise ValueError(f"Log axis series {label!r} has non-positive values or error-bar endpoints.")
            if np.any(lower < axis_spec["limits"][0]) or np.any(upper > axis_spec["limits"][1]):
                raise ValueError(f"Explicit dual-axis limits exclude data or error bars for {label!r}; expand them or use facets.")
    text_sizes = TEXT_SIZES_PT[size]
    with mpl.rc_context(_rc_for_font(face, text_sizes, embed=True)):
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
            "palette": palette, "focus": focus,
            "encoding": encoding_metadata if encoding is not None else None,
            "secondary_y": secondary_spec,
            "xscale": xscale, "yscale": yscale,
            "size": size, "journal": journal,
            "width_mm": width_mm, "height_mm": resolved_height,
            "formats": list(chosen_formats), "dpi_by_format": dpi_by_format,
            "heatmap": kind in ("heatmap", "joint"),
            "analysis": analysis_spec["metadata"] if analysis_spec is not None else None,
            "error": error_metadata if error is not None else None,
            "reference_guides": guides,
            "inset": inset_spec,
            "heatmap_scale": heatmap_limits or None,
            "error_bars": None if error_bar_state is None else {
                "display": error_bar_state["display"],
                "alpha": error_bar_state["alpha"],
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
        axes._scientific_encoding = encoding_metadata if encoding is not None else None
        right_axes = None
        if secondary_spec is not None:
            right_axes = axes.twinx()
            axes.scientific_secondary_axes = right_axes
            right_axes._scientific_primary_axes = axes
            right_axes.set_yscale(secondary_spec["scale"])
            _style_axes(right_axes, kind)
            right_axes.grid(False, which="both", axis="both")
            right_axes.tick_params(axis="y", which="both", left=False, right=True, labelleft=False, labelright=True)
            axes.tick_params(axis="y", which="both", right=False)
            for side in ("left", "top", "bottom"):
                right_axes.spines[side].set_visible(False)
            right_axes.set_ylabel(_prepare_label(secondary_spec["label"], families))
            axes.set_ylim(secondary_spec["primary"]["limits"])
            right_axes.set_ylim(secondary_spec["limits"])
        artists = {}
        error_artists = {}
        error_bar_records = []

        def draw_uncertainty(x_values, y_values, yerr, xerr, color, label, zorder, target_axes=None) -> None:
            if error_bar_state is None or (yerr is None and xerr is None):
                return
            destination = axes if target_axes is None else target_axes
            if error_bar_state["display"] == "band":
                band = destination.fill_between(
                    x_values, y_values - yerr[0], y_values + yerr[1],
                    color=color, alpha=error_bar_state["alpha"], linewidth=0,
                    zorder=1, label="_nolegend_",
                )
                band._scientific_uncertainty_band = True
            else:
                _draw_errorbars(destination, x_values, y_values, yerr=yerr, xerr=xerr, color=color,
                                capsize=error_bar_state["capsize_pt"], elinewidth=error_bar_state["elinewidth_pt"],
                                zorder=zorder)
            record = _errorbar_record(label, x_values, y_values, yerr, xerr)
            if secondary_spec is not None:
                record["axis"] = "right" if target_axes is right_axes else "left"
            error_bar_records.append(record)

        default_xlabel, default_ylabel = x or "", y or value or ""
        if analysis_spec is not None:
            default_xlabel, default_ylabel = _draw_analysis(axes, frame, kind, x, y, analysis_spec, palette, focus, families, draw_colorbar)
        elif kind in ("point-line", "line", "scatter", "bar", "mixed"):
            _required(frame, x, y)
            if kind in (*SERIES_KINDS, "mixed"):
                ordered = False if encoding is not None else _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                limit = len(MARKERS) * len(LINESTYLES) if kind in ("point-line", "mixed") else len(LINESTYLES)
                if len(values) > limit:
                    raise ValueError("Too many series to distinguish in grayscale; divide them into panels.")
                palette_colors = _palette(len(values), ordered, "classic" if encoding is not None else palette,
                                          next((index for index, (label, _) in enumerate(values) if label == focus), None))
                for index, (label, subset) in enumerate(values):
                    x_values, y_values = _numeric(subset, x), _numeric(subset, y)
                    target_axes = right_axes if secondary_spec is not None and label in secondary_spec["series"] else axes
                    artists[label] = _draw_series(target_axes, x_values, y_values, label, styles[label], index, palette_colors[index])
                    if encoding is not None:
                        artists[label]._scientific_roles = encoding["series"][label]
                    if error_bar_state is not None:
                        artist = artists[label]
                        draw_uncertainty(x_values, y_values, _axis_errors(subset, "y", error_bar_state),
                                         _axis_errors(subset, "x", error_bar_state), _artist_color(artist), label,
                                         2.5 if isinstance(artist, PathCollection) else 1.5, target_axes)
                if error_axes is not None:
                    error_axes.set_xscale(xscale)
                    _style_axes(error_axes, kind)
                    for label, coordinates, differences in comparisons:
                        index = next(index for index, (name, _) in enumerate(values) if name == label)
                        error_artists[label] = _draw_series(error_axes, coordinates, differences, label,
                                                           styles[label], index, palette_colors[index])
                    error_axes.set_ylabel(_prepare_label(error.get(
                        "ylabel", {"signed": "Signed error", "absolute": "Absolute error",
                                   "relative": "Relative error (-)"}[error_metadata["definition"]]), families))
            else:
                _numeric(frame, y)
                ordered = _ordered_groups(frame, group, group_kind)
                values = _groups(frame, group, ordered)
                if len(values) > len(CATEGORICAL_COLORS):
                    raise ValueError("Too many bar series to distinguish in grayscale; divide them into panels.")
                if group is None:
                    if frame[x].duplicated().any():
                        raise ValueError("Repeated bar category; aggregate explicitly or specify --group.")
                    bar_colors = (_palette(len(frame), False, palette, list(frame[x].astype(str)).index(focus))
                                  if palette == "focus" else _palette(1, False, palette)[0])
                    bars = axes.bar(frame[x].astype(str), frame[y], color=bar_colors,
                                    edgecolor="#333333", linewidth=0.65)
                    if error_bar_state is not None:
                        centers = [patch.get_x() + patch.get_width() / 2 for patch in bars]
                        heights = [patch.get_height() for patch in bars]
                        draw_uncertainty(centers, heights, _axis_errors(frame, "y", error_bar_state), None,
                                         "#333333", "", 3)
                else:
                    categories = list(pd.unique(frame[x]))
                    width = 0.8 / len(values)
                    palette_colors = _palette(len(values), ordered, palette,
                                              next((index for index, (label, _) in enumerate(values) if label == focus), None))
                    for index, (label, subset) in enumerate(values):
                        if subset[x].duplicated().any():
                            raise ValueError("Repeated group/category; aggregate explicitly before plotting.")
                        positions = np.arange(len(categories)) - 0.4 + width * (index + 0.5)
                        indexed = subset.set_index(x)
                        heights = indexed[y].reindex(categories)
                        bars = axes.bar(positions, heights, width=width, label=label, color=palette_colors[index],
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
            image = axes.imshow(matrix, cmap="cividis", interpolation="nearest", aspect="auto", **heatmap_limits)
            axes.set_xticks(np.arange(frame.shape[1]), [str(item) for item in frame.columns])
            axes.set_yticks(np.arange(frame.shape[0]), [str(item) for item in frame.index])
            axes.tick_params(which="minor", bottom=False, left=False, top=False, right=False)
            if draw_colorbar:
                figure.colorbar(image, ax=axes, label=_prepare_label(value or "Value", families),
                                fraction=0.05, pad=0.03)
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
            palette_colors = _palette(len(categories), False, palette,
                                      next((index for index, category in enumerate(categories) if str(category) == focus), None))
            for index, body in enumerate(parts["bodies"]):
                body.set_facecolor(palette_colors[index])
                body.set_edgecolor("#333333")
                body.set_alpha(1)
            for key in ("cbars", "cmins", "cmaxes"):
                parts[key].set_color("#333333")
            axes.set_xticks(np.arange(1, len(categories) + 1), [str(category) for category in categories])
        label_axes = error_axes if error_axes is not None else axes
        label_axes.set_xlabel(_prepare_label(xlabel if xlabel is not None else default_xlabel, families))
        axes.set_ylabel(_prepare_label(ylabel if ylabel is not None else default_ylabel, families))
        if title:
            axes.set_title(title)
        _draw_guides(axes, guides)
        axes._scientific_inset_spec = inset_spec
        if apply_layout:
            figure.tight_layout(pad=1.0)
            if kind in (*SERIES_KINDS, "mixed"):
                margins = figure.subplotpars
                figure.subplots_adjust(left=max(0.135, margins.left), right=min(0.91, margins.right),
                                       bottom=max(0.13, margins.bottom), top=min(0.95, margins.top))
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        if right_axes is not None:
            _adapt_strokes(right_axes, kind, line_width, marker_size)
        _refresh_inset(axes)
        if draw_legend:
            _place_legend(figure, axes, size, legend)
        figure.canvas.draw()
        for panel_axes in figure.axes:
            _adapt_log_ticks(panel_axes)
        figure.canvas.draw()
        _adapt_strokes(axes, kind, line_width, marker_size)
        if right_axes is not None:
            _adapt_strokes(right_axes, kind, line_width, marker_size)
        for label, artist in error_artists.items():
            _copy_identity(artists[label], artist)
        _sync_legend(axes)
        _refresh_inset(axes)
        if error_bar_state is not None:
            metadata["error_bars"]["series"] = error_bar_records
        if artists:
            metadata["series"] = {
                label: {"kind": styles[label]["kind"],
                        "line_width_pt": None if isinstance(artist, PathCollection) else artist.get_linewidth(),
                        "marker_size_pt": float(np.sqrt(artist.get_sizes()[0])) if isinstance(artist, PathCollection)
                        else artist.get_markersize() if styles[label]["kind"] == "point-line" else None}
                for label, artist in artists.items()}
            if palette != "classic" or encoding is not None or secondary_spec is not None or any("fillstyle" in style for style in styles.values()):
                for label, artist in artists.items():
                    metadata["series"][label].update(color=colors.to_hex(_artist_color(artist)),
                                                      identity=list(artist._scientific_identity),
                                                      style=_config_value(styles[label]))
                    if secondary_spec is not None:
                        metadata["series"][label]["axis"] = "right" if artist.axes is right_axes else "left"
        _refresh_panel_metadata(axes)
        for panel_axes in ((axes, error_axes) if hosted else figure.axes):
            if panel_axes is not None:
                _hide_edge_grids(panel_axes)
        if apply_layout:
            _check_text_layout(figure)
        exported = []
        if not hosted:
            figure.scientific_review = review_figure(figure, journal=journal)
            exported = _export_figure(figure, output, chosen_formats, dpi_by_format, metadata,
                                      error is not None or error_bar_state is not None or bool(guides) or inset_spec is not None
                                      or palette != "classic" or encoding is not None or secondary_spec is not None or analysis_spec is not None
                                      or any("fillstyle" in getattr(artist, "_scientific_style", {}) for artist in artists.values()))
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


def _refresh_panel_metadata(axes) -> None:
    metadata = getattr(axes, "_scientific_panel", getattr(axes.figure, "scientific_metadata", {}))
    for panel in _series_axes(axes):
        for artist in (*panel.lines, *panel.collections):
            if not hasattr(artist, "_scientific_identity"):
                continue
            record = metadata.get("series", {}).get(artist.get_label())
            if record is None:
                continue
            scatter = isinstance(artist, PathCollection)
            record["line_width_pt"] = None if scatter else artist.get_linewidth()
            record["marker_size_pt"] = (float(np.sqrt(artist.get_sizes()[0])) if scatter
                                         else artist.get_markersize() if artist._scientific_identity[0] == "point-line" else None)
    if metadata.get("encoding") is not None:
        metadata["encoding"]["resolved_series"] = {
            label: {key: record[key] for key in ("color", "identity", "axis", "line_width_pt", "marker_size_pt") if key in record}
            for label, record in metadata.get("series", {}).items()}


def _sync_figure_legend(figure: mpl.figure.Figure) -> None:
    if not figure.legends:
        return
    legend = figure.legends[0]
    sources = {}
    for axes in figure.axes:
        for artist, label in zip(*_legend_entries(axes)):
            if label and not str(label).startswith("_") and label not in sources:
                sources[label] = artist
    for target, text in zip(legend.legend_handles, legend.get_texts()):
        source = sources.get(text.get_text())
        if source is None:
            continue
        _copy_identity(source, target)
        if isinstance(source, PathCollection):
            target.set_sizes(source.get_sizes()[:1])


def _panel_layout(panels: list[dict], layout, ncols: int | None, width_mm: float) -> tuple[int, int, list]:
    count = len(panels)
    if layout is None:
        if ncols is None:
            ncols = 2 if width_mm >= 140 and 2 <= count <= 4 else 1
        if isinstance(ncols, bool) or not isinstance(ncols, int) or not 1 <= ncols <= count:
            raise ValueError("ncols must be an integer from 1 through the panel count.")
        return int(np.ceil(count / ncols)), ncols, [
            (index // ncols, index // ncols + 1, index % ncols, index % ncols + 1) for index in range(count)]
    if ncols is not None:
        raise ValueError("layout defines its own columns; omit ncols.")
    if not isinstance(layout, (list, tuple)) or not layout:
        raise ValueError("layout must be a nonempty rectangular matrix of panel IDs and None blanks.")
    if any(not isinstance(row, (list, tuple)) or not row for row in layout):
        raise ValueError("layout must contain nonempty rows.")
    columns = len(layout[0])
    if any(len(row) != columns for row in layout):
        raise ValueError("layout rows must have equal lengths.")
    identifiers = [panel.get("id") for panel in panels]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise ValueError("Every panel needs a nonempty string id when layout is provided.")
    if len(set(identifiers)) != count:
        raise ValueError("Panel IDs must be unique.")
    cells = [cell for row in layout for cell in row if cell is not None]
    if any(not isinstance(cell, str) for cell in cells) or set(cells) != set(identifiers):
        raise ValueError("layout must include every panel ID and no unknown IDs; use None for blanks.")
    spans = []
    for identifier in identifiers:
        positions = [(row, column) for row, entries in enumerate(layout)
                     for column, cell in enumerate(entries) if cell == identifier]
        row_start, column_start = np.min(positions, axis=0).tolist()
        row_end, column_end = (np.max(positions, axis=0) + 1).tolist()
        if any(layout[row][column] != identifier for row in range(row_start, row_end)
               for column in range(column_start, column_end)):
            raise ValueError(f"Panel {identifier!r} must occupy one rectangle in layout.")
        spans.append((row_start, row_end, column_start, column_end))
    return len(layout), columns, spans


def _shared_heatmap_scale(panels: list[dict], shared_colorbar) -> dict | None:
    if shared_colorbar is None:
        return None
    if not isinstance(shared_colorbar, dict) or shared_colorbar.keys() != {"vmin", "vmax", "label"}:
        raise ValueError("shared_colorbar requires vmin, vmax and label.")
    if not isinstance(shared_colorbar["label"], str) or not shared_colorbar["label"].strip():
        raise ValueError("shared_colorbar needs a descriptive label including units.")
    limits = _heatmap_limits({key: shared_colorbar[key] for key in ("vmin", "vmax")})
    heatmaps = [panel for panel in panels if panel["kind"] == "heatmap"]
    if len(heatmaps) < 2:
        raise ValueError("shared_colorbar requires at least two numeric heatmaps.")
    quantities = []
    for panel in heatmaps:
        if any(not isinstance(panel.get(key), str) or not panel[key].strip() for key in ("quantity", "unit")):
            raise ValueError("Shared heatmaps must explicitly name quantity and unit; use '-' for dimensionless.")
        quantities.append((panel["quantity"], panel["unit"]))
        if panel.get("heatmap_scale") is not None and _heatmap_limits(panel["heatmap_scale"]) != limits:
            raise ValueError("Panel heatmap_scale conflicts with the shared colorbar limits.")
    if len(set(quantities)) != 1:
        raise ValueError("Shared heatmaps must have the same explicit quantity and unit.")
    return limits


@_delivery
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
    style_registry: dict | None = None,
    palette: str = "classic",
    focus: str | None = None,
    encoding: dict | None = None,
    layout: list[list[str | None]] | None = None,
    shared_colorbar: dict | None = None,
    report: bool = False,
    bundle: str | Path | None = None,
    include_data: bool = False,
) -> tuple[mpl.figure.Figure, list, list[Path]]:
    """Compose real panels on one journal-width canvas. Titles stay in the caption."""
    if not panels:
        raise ValueError("render_multipanel needs at least one panel.")
    _palette(0, False, palette)
    if legend not in ("shared", "each", "none"):
        raise ValueError("Multipanel legend must be shared, each or none.")
    has_secondary = any(isinstance(panel, dict) and panel.get("secondary_y") is not None for panel in panels)
    has_joint = any(isinstance(panel, dict) and panel.get("kind") == "joint" for panel in panels)
    if has_secondary and sharey:
        raise ValueError("Dual-axis panels cannot use sharey; choose explicit matching primary/secondary limits.")
    if journal not in JOURNALS:
        raise ValueError(f"journal must be one of: {', '.join(JOURNALS)}.")
    if size is None:
        size = {"elsevier": "double", "jfm": "single", "pof": "aip-double"}[journal]
    size = resolve_size(size, journal)
    width_mm = SIZES_MM[size][0]
    count = len(panels)
    for panel in panels:
        if not isinstance(panel, dict) or "data" not in panel or "kind" not in panel:
            raise ValueError("Each panel needs data and kind.")
    nrows, ncols, spans = _panel_layout(panels, layout, ncols, width_mm)
    shared_scale = _shared_heatmap_scale(panels, shared_colorbar)
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
    heatmap = any(panel.get("kind") in ("heatmap", "joint") for panel in panels)
    dpi_by_format = resolve_dpi(dpi, chosen_formats, journal, heatmap)
    face = resolve_font(font)
    text_sizes = TEXT_SIZES_PT[size]
    letters = [f"({chr(ord('a') + index)})" for index in range(count)]
    draw_keys = ("kind", "x", "y", "group", "value", "group_kind", "xlabel", "ylabel", "line_width",
                 "marker_size", "xscale", "yscale", "series_styles", "error", "error_bars", "legend",
                 "reference_guides", "inset", "heatmap_scale", "palette", "focus", "encoding", "secondary_y", "analysis")
    with mpl.rc_context(_rc_for_font(face, text_sizes, embed=False)):
        figure = plt.figure(figsize=(width_mm / 25.4, resolved_height / 25.4), dpi=120)
        figure.scientific_error_axes = None
        figure.scientific_metadata = {
            "palette": palette, "focus": focus,
            "encoding": encoding,
            "multipanel": True, "size": size, "journal": journal,
            "width_mm": width_mm, "height_mm": resolved_height,
            "formats": list(chosen_formats), "dpi_by_format": dpi_by_format,
            "heatmap": heatmap, "legend_mode": legend, "panel_letters": letters,
            "height_clamped": height_clamped, "target_height_mm": target_height,
            "xscale": None, "yscale": None, "error": None, "error_bars": None,
            "layout": layout, "shared_colorbar": shared_colorbar,
        }
        if shared_scale is None:
            grid = figure.add_gridspec(nrows, ncols, hspace=0.55, wspace=0.8 if has_secondary or has_joint else 0.38)
        else:
            outer = figure.add_gridspec(1, 2, width_ratios=[1, 0.035], wspace=0.12)
            grid = outer[0].subgridspec(nrows, ncols, hspace=0.55, wspace=0.38)
            colorbar_axes = figure.add_subplot(outer[1])
        figure.subplots_adjust(left=0.16, right=0.86 if has_secondary or has_joint else 0.88 if shared_scale is not None else 0.97, bottom=0.16, top=0.90)
        created = []
        share_x_anchor = None
        share_y_anchor = None
        shared_quantities = set()
        for index, panel in enumerate(panels):
            row, row_end, column, column_end = spans[index]
            cell = grid[row:row_end, column:column_end]
            share_kwargs = {}
            if sharex and share_x_anchor is not None:
                share_kwargs["sharex"] = share_x_anchor
            if sharey and share_y_anchor is not None:
                share_kwargs["sharey"] = share_y_anchor
            if panel.get("error") is not None:
                sub = cell.subgridspec(2, 1, height_ratios=[2.4, 1], hspace=0.08)
                axes = figure.add_subplot(sub[0], **share_kwargs)
                error_axes = figure.add_subplot(sub[1], sharex=axes)
            else:
                axes = figure.add_subplot(cell, **share_kwargs)
                error_axes = None
            if share_x_anchor is None:
                share_x_anchor = axes
            if share_y_anchor is None:
                share_y_anchor = axes
            kwargs = {key: panel[key] for key in draw_keys if key in panel}
            kwargs.setdefault("palette", palette if panel["kind"] not in ("heatmap", "joint") else "classic")
            kwargs.setdefault("focus", focus if kwargs["palette"] == "focus" else None)
            kwargs.setdefault("encoding", encoding if panel["kind"] in (*SERIES_KINDS, "mixed") else None)
            if shared_scale is not None and panel["kind"] == "heatmap":
                kwargs["heatmap_scale"] = shared_scale
            render_plot(panel["data"], journal=journal, size=size, font=font, host_axes=axes,
                        host_error_axes=error_axes, apply_layout=False,
                        style_registry=style_registry if panel["kind"] in (*SERIES_KINDS, "mixed") else None,
                        draw_colorbar=shared_scale is None,
                        draw_legend=legend == "each", **kwargs)
            if sharey and axes._scientific_panel.get("encoding") is not None:
                encoded = axes._scientific_panel["encoding"]
                observed_metrics = {record["metric"] for record in encoded["observed"]}
                shared_quantities.update((style["quantity"], style["unit"])
                                         for metric, style in encoded["metrics"].items()
                                         if metric in observed_metrics and "quantity" in style)
                if len(shared_quantities) > 1:
                    raise ValueError("sharey cannot link different declared quantities/units; keep metric facets on separate y axes.")
            if sharex and row_end != nrows:
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
        if shared_scale is not None:
            image = next(axes.images[0] for axes, _, panel in created if panel["kind"] == "heatmap")
            figure.colorbar(image, cax=colorbar_axes,
                            label=_prepare_label(shared_colorbar["label"], _font_families(face)))
        figure.scientific_metadata["panels"] = [axes._scientific_panel for axes, _, _ in created]
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
            if getattr(axes, "scientific_secondary_axes", None) is not None:
                _adapt_strokes(axes.scientific_secondary_axes, panel["kind"], panel.get("line_width"), panel.get("marker_size"))
            if error_axes is not None:
                _copy_matching_artists(axes, error_axes)
            _refresh_inset(axes)
            _refresh_panel_metadata(axes)
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


def _replace_cli_value(arguments: list[str], flag: str, value: str) -> None:
    for index in range(len(arguments) - 1, -1, -1):
        if arguments[index] == flag:
            arguments[index + 1] = value
            return
        if arguments[index].startswith(flag + "="):
            arguments[index] = flag + "=" + value
            return
    raise ValueError(f"Missing CLI argument {flag} in reproduction command.")


def _without_bundle_flags(arguments: list[str]) -> list[str]:
    cleaned = []
    iterator = iter(arguments)
    for token in iterator:
        if token == "--bundle":
            next(iterator)
        elif token != "--include-data" and not token.startswith("--bundle="):
            cleaned.append(token)
    return cleaned


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
    if options.uncertainty_display is not None:
        payload["display"] = options.uncertainty_display
    if options.band_alpha is not None:
        payload["alpha"] = options.band_alpha
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
    parser.add_argument("--xlabel",
                        help=r"Axis name. Scripts: t^*, t^+, t_{wall}, \(t^*\), or $t^*$")
    parser.add_argument("--ylabel", help="Axis name. Same superscripts and subscripts as --xlabel")
    parser.add_argument("--title")
    parser.add_argument("--font", choices=FONT_CHOICES, default="Arial",
                        help="Arial, Times New Roman, 思源黑体, or 思源宋体")
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
    parser.add_argument("--style-registry", type=Path, help="Reusable JSON series identities: color, marker, linestyle")
    parser.add_argument("--palette", choices=tuple(PALETTES), default="classic", help="Explicit categorical palette; ordered groups retain classic")
    parser.add_argument("--focus", help="Explicit series/category to emphasize with --palette focus")
    parser.add_argument("--encoding-config", type=Path, help="Explicit JSON category/metric roles and factorized legend")
    parser.add_argument("--secondary-y-config", type=Path, help="Explicit dual-axis roles, quantities, units, limits and scientific reason")
    parser.add_argument("--reference-config", type=Path, help="JSON list of explicit constant or power reference guides")
    parser.add_argument("--inset-config", type=Path, help="JSON xlim, ylim and bounds for an explicit zoom inset")
    parser.add_argument("--analysis-config", type=Path, help="JSON explicit distribution bins/statistic, weights, trajectory or contribution settings")
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
    parser.add_argument("--uncertainty-display", choices=("bars", "band"), help="Render supplied uncertainty as whiskers or a y band")
    parser.add_argument("--band-alpha", type=float, help="Band opacity in (0, 0.35], default 0.18")
    parser.add_argument("--zero-reference", choices=("raise",), default="raise")
    parser.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    parser.add_argument("--index-col", help="Matrix heatmap row-label column")
    parser.add_argument("--output", type=Path, required=True, help="Output basename; suffix does not override --format")
    parser.add_argument("--report", action="store_true", help="Save JSON/Markdown review of the actual exported files")
    parser.add_argument("--bundle", type=Path, help="Write a delivery bundle to an absent or empty directory (implies --report)")
    parser.add_argument("--include-data", action="store_true", help="Explicitly allow used-data snapshots in --bundle")
    parser.add_argument("--no-script", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args(argv)
    if options.include_data and options.bundle is None:
        parser.error("--include-data requires --bundle")
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
    style_registry = json.loads(options.style_registry.read_text(encoding="utf-8")) if options.style_registry else None
    encoding = json.loads(options.encoding_config.read_text(encoding="utf-8")) if options.encoding_config else None
    secondary_y = json.loads(options.secondary_y_config.read_text(encoding="utf-8")) if options.secondary_y_config else None
    reference_guides = json.loads(options.reference_config.read_text(encoding="utf-8")) if options.reference_config else None
    inset = json.loads(options.inset_config.read_text(encoding="utf-8")) if options.inset_config else None
    analysis = json.loads(options.analysis_config.read_text(encoding="utf-8")) if options.analysis_config else None
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
        style_registry=style_registry, palette=options.palette, focus=options.focus, encoding=encoding, secondary_y=secondary_y,
        reference_guides=reference_guides, inset=inset, analysis=analysis,
        error=error, error_bars=_cli_error_bars(options, parser), legend=options.legend,
        journal=options.journal, height_mm=options.height_mm,
        report=options.report, bundle=options.bundle, include_data=options.include_data,
    )
    plt.close(figure)
    if not options.no_script:
        original_args = list(argv if argv is not None else sys.argv[1:])
        original_args = _without_bundle_flags(original_args)
        _replace_cli_value(original_args, "--input", str(source))
        _replace_cli_value(original_args, "--output", str(options.output.resolve()))
        target = paths[0].with_suffix("")
        for flag, payload, suffix in (("--series-config", series_styles, "series"),
                                      ("--style-registry", style_registry, "registry"),
                                      ("--encoding-config", encoding, "encoding"),
                                      ("--secondary-y-config", secondary_y, "secondary_y"),
                                      ("--reference-config", reference_guides, "references"),
                                      ("--inset-config", inset, "inset"),
                                      ("--analysis-config", analysis, "analysis")):
            if getattr(options, flag[2:].replace("-", "_")) is not None:
                config_path = target.with_name(target.stem + f"_{suffix}.json")
                config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                _replace_cli_value(original_args, flag, str(config_path.resolve()))
        _source_script(target, original_args)
    return paths


if __name__ == "__main__":
    for path in run_cli():
        print(path)
