import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

os.environ["MPLBACKEND"] = "Agg"

from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scientific-plotting" / "scripts" / "plot_template.py"
sys.path.insert(0, str(TEMPLATE.parent))

from plot_template import ERRORBAR_CAPSIZE_PT, ERRORBAR_ELINEWIDTH_PT, render_plot


def vertical_spans(axes):
    spans = []
    for collection in axes.collections:
        if not getattr(collection, "_scientific_errorbar", False) or not isinstance(collection, LineCollection):
            continue
        for segment in collection.get_segments():
            segment = np.asarray(segment, dtype=float)
            if len(segment) >= 2 and np.allclose(segment[:, 0], segment[0, 0]):
                spans.append((float(segment[0, 0]), float(segment[:, 1].min()), float(segment[:, 1].max())))
    return spans


def data_lines(axes):
    return [line for line in axes.lines if not getattr(line, "_scientific_errorbar", False)]


def rgb(color):
    return to_rgba(color)[:3]


@pytest.fixture(autouse=True)
def ignore_font_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        yield


def test_error_bars_are_off_unless_requested(tmp_path):
    frame = pd.DataFrame({"x": [0.0, 1.0], "y": [1.0, 2.0]})
    figure, axes, paths = render_plot(frame, kind="point-line", x="x", y="y", output=tmp_path / "plain")
    assert figure.scientific_metadata["error_bars"] is None
    assert not any(getattr(artist, "_scientific_errorbar", False) for artist in (*axes.lines, *axes.collections))
    assert paths == [tmp_path / "plain.jpg"]
    assert not (tmp_path / "plain_metadata.json").exists()
    plt.close(figure)


def test_symmetric_error_bars_keep_row_order_color_caps_and_limits():
    frame = pd.DataFrame({"x": [2.0, 0.0, 1.0], "y": [3.0, 1.0, 2.0], "dy": [0.5, 0.5, 0.5]})
    original = frame.copy(deep=True)
    figure, axes, _ = render_plot(frame, kind="point-line", x="x", y="y",
                                  error_bars={"y": "dy", "capsize": 3, "definition": "  sample standard deviation  "})
    pd.testing.assert_frame_equal(frame, original)
    assert [list(line.get_xdata()) for line in data_lines(axes)] == [[2.0, 0.0, 1.0]]
    assert data_lines(axes)[0].get_marker() not in (None, "None")
    spans = vertical_spans(axes)
    assert [item[0] for item in spans] == pytest.approx([2, 0, 1])
    assert [(item[1], item[2]) for item in spans] == pytest.approx([(2.5, 3.5), (0.5, 1.5), (1.5, 2.5)])
    assert axes.get_ylim()[0] < 0.5 and axes.get_ylim()[1] > 3.5
    caps = [line for line in axes.lines if getattr(line, "_scientific_errorbar", False)]
    assert caps
    assert all(line.get_markersize() == pytest.approx(6) for line in caps)
    assert all(line.get_markeredgewidth() == pytest.approx(ERRORBAR_ELINEWIDTH_PT) for line in caps)
    assert all(np.allclose(rgb(line.get_markeredgecolor()), rgb(data_lines(axes)[0].get_color())) for line in caps)
    assert figure.scientific_metadata["error_bars"]["definition"] == "sample standard deviation"
    assert figure.scientific_metadata["error_bars"]["capsize_pt"] == 3
    assert figure.scientific_metadata["error_bars"]["y"] == {"mode": "symmetric", "source": "dy"}
    assert axes.get_legend() is None
    plt.close(figure)


def test_line_error_bars_do_not_add_markers_to_the_series():
    figure, axes, _ = render_plot({"x": [0.0, 1.0, 2.0], "y": [1.0, 2.0, 1.5], "dy": [0.1, 0.1, 0.1]},
                                  kind="line", x="x", y="y",
                                  error_bars={"y": "dy", "definition": "synthetic standard deviation"})
    assert all(line.get_marker() in (None, "None") for line in data_lines(axes))
    assert any(line.get_marker() == "_" for line in axes.lines)
    assert figure.scientific_metadata["error_bars"]["capsize_pt"] == ERRORBAR_CAPSIZE_PT
    plt.close(figure)


def test_asymmetric_scatter_and_constant_x_errors_use_series_color():
    frame = pd.DataFrame({"x": [0.0, 1.0, 2.0], "y": [1.0, 2.0, 4.0], "series": ["S", "S", "S"]})
    figure, axes, _ = render_plot(
        frame, kind="scatter", x="x", y="y", group="series",
        error_bars={"y_lower": [0.1, 0.2, 0.4], "y_upper": [0.3, 0.0, 0.5], "x": 0.25,
                    "definition": "asymmetric instrument bounds"})
    spans = vertical_spans(axes)
    assert [(item[1], item[2]) for item in spans] == pytest.approx([(0.9, 1.3), (1.8, 2.0), (3.6, 4.5)])
    horizontal = []
    for collection in axes.collections:
        if not getattr(collection, "_scientific_errorbar", False):
            continue
        for segment in collection.get_segments():
            segment = np.asarray(segment, dtype=float)
            if np.allclose(segment[:, 1], segment[0, 1]):
                horizontal.append((float(segment[:, 0].min()), float(segment[:, 0].max()), float(segment[0, 1])))
    assert horizontal == pytest.approx([(-0.25, 0.25, 1), (0.75, 1.25, 2), (1.75, 2.25, 4)])
    points = next(collection for collection in axes.collections if not getattr(collection, "_scientific_errorbar", False))
    stems = [collection for collection in axes.collections if getattr(collection, "_scientific_errorbar", False)]
    assert all(np.allclose(rgb(collection.get_colors()[0]), rgb(points.get_facecolor()[0])) for collection in stems)
    recorded = figure.scientific_metadata["error_bars"]
    assert recorded["x"]["source"] == "constant"
    assert recorded["y"]["mode"] == "asymmetric"
    assert [text.get_text() for text in axes.get_legend().get_texts()] == ["S"]
    plt.close(figure)


def test_grouped_bar_error_bars_follow_bar_centers():
    frame = pd.DataFrame({"x": ["near", "far", "near", "far"], "y": [2.0, 3.0, 2.4, 2.8],
                          "sd": [0.2, 0.1, 0.3, 0.2], "method": ["A", "A", "B", "B"]})
    figure, axes, _ = render_plot(frame, kind="bar", x="x", y="y", group="method",
                                  error_bars={"y": "sd", "definition": "sample standard deviation, n=4"})
    spans = vertical_spans(axes)
    assert len(spans) == len(axes.patches) == 4
    magnitudes = [0.2, 0.1, 0.3, 0.2]
    for patch, magnitude, span in zip(axes.patches, magnitudes, spans):
        center = patch.get_x() + patch.get_width() / 2
        assert span[0] == pytest.approx(center)
        assert span[1] == pytest.approx(patch.get_height() - magnitude)
        assert span[2] == pytest.approx(patch.get_height() + magnitude)
        assert patch.get_zorder() < axes.collections[0].get_zorder()
    assert all(np.allclose(rgb(collection.get_colors()[0]), rgb("#333333"))
               for collection in axes.collections if getattr(collection, "_scientific_errorbar", False))
    assert [text.get_text() for text in axes.get_legend().get_texts()] == ["A", "B"]
    assert axes.get_ylim()[1] > 3.1
    plt.close(figure)
    incomplete = frame.drop(index=1)
    with pytest.raises(ValueError, match="Missing group/category"):
        render_plot(incomplete, kind="bar", x="x", y="y", group="method",
                    error_bars={"y": "sd", "definition": "sample standard deviation, n=4"})


def test_zero_magnitude_is_drawn_and_caller_series_is_not_reordered():
    frame = pd.DataFrame({"x": [0.0, 1.0], "y": [2.0, 2.0], "dy": [0.0, 0.0]})
    figure, axes, _ = render_plot(frame, kind="scatter", x="x", y="y",
                                  error_bars={"y": "dy", "definition": "exact values, zero uncertainty"})
    spans = vertical_spans(axes)
    assert [(item[1], item[2]) for item in spans] == pytest.approx([(2, 2), (2, 2)])
    plt.close(figure)


@pytest.mark.parametrize("kind", ["heatmap", "violin"])
def test_unsupported_kinds_refuse_error_bars(kind):
    data = np.array([[1.0, 2.0], [3.0, 4.0]]) if kind == "heatmap" else {"y": [1.0, 2.0, 3.0]}
    with pytest.raises(ValueError, match="Error bars apply"):
        render_plot(data, kind=kind, error_bars={"y": 0.1, "definition": "synthetic standard deviation"})


@pytest.mark.parametrize(("payload", "message"), [
    ({"y": [-0.1, 0.2], "definition": "sd"}, "negative magnitude"),
    ({"y": [0.1, np.nan], "definition": "sd"}, "non-finite"),
    ({"y": "missing", "definition": "sd"}, "missing"),
    ({"y": [0.1], "definition": "sd"}, "one magnitude per row"),
    ({"y": 0.1, "y_lower": 0.1, "y_upper": 0.1, "definition": "sd"}, "not both"),
    ({"y_lower": 0.1, "definition": "sd"}, "both lower and upper"),
    ({"y": 0.1}, "requires definition"),
    ({"definition": "sd"}, "needs an x or y"),
    ({"y": 0.1, "definition": "sd", "shade": True}, "Unknown error_bars"),
    ({"capsize": 0, "y": 0.1, "definition": "sd"}, "capsize"),
])
def test_error_bar_spec_is_explicit(payload, message):
    frame = pd.DataFrame({"x": [0.0, 1.0], "y": [1.0, 2.0]})
    with pytest.raises(ValueError, match=message):
        render_plot(frame, kind="point-line", x="x", y="y", error_bars=payload)


def test_misaligned_series_is_not_reindexed():
    frame = pd.DataFrame({"x": [0.0, 1.0], "y": [1.0, 2.0]})
    shifted = pd.Series([0.1, 0.2], index=[1, 0])
    with pytest.raises(ValueError, match="same row index"):
        render_plot(frame, kind="line", x="x", y="y", error_bars={"y": shifted, "definition": "sd"})


def test_bar_refuses_categorical_x_errors():
    frame = pd.DataFrame({"x": ["near", "far"], "y": [1.0, 2.0], "dx": [0.1, 0.1]})
    with pytest.raises(ValueError, match="y error bars only"):
        render_plot(frame, kind="bar", x="x", y="y", error_bars={"x": "dx", "definition": "not a position error"})


def test_log_axis_refuses_nonpositive_whiskers_without_clipping():
    frame = pd.DataFrame({"x": [1.0, 10.0, 100.0], "y": [1.0, 2.0, 4.0], "dy": [0.2, 2.0, 0.1]})
    with pytest.raises(ValueError, match="non-positive"):
        render_plot(frame, kind="point-line", x="x", y="y", yscale="log",
                    error_bars={"y": "dy", "definition": "synthetic standard deviation"})
    figure, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", yscale="log",
                                  error_bars={"y": [0.2, 0.5, 1.0], "definition": "synthetic standard deviation"})
    assert axes.get_yscale() == "log"
    assert vertical_spans(axes)[1][1] == pytest.approx(1.5)
    plt.close(figure)


def test_error_bars_stay_on_the_main_panel_when_a_reference_error_is_drawn():
    frame = pd.DataFrame({
        "x": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
        "y": [0.0, 1.0, 2.0, 0.1, 1.2, 1.9],
        "dy": [0.01, 0.02, 0.01, 0.05, 0.04, 0.03],
        "series": ["Theory", "Theory", "Theory", "Sample", "Sample", "Sample"],
    })
    figure, axes, _ = render_plot(frame, kind="line", x="x", y="y", group="series",
                                  error={"reference": "Theory", "definition": "signed"},
                                  error_bars={"y": "dy", "definition": "synthetic standard deviation"})
    np.testing.assert_allclose(figure.scientific_error_axes.lines[0].get_ydata(), [0.1, 0.2, -0.1])
    assert not any(getattr(line, "_scientific_errorbar", False) for line in figure.scientific_error_axes.lines)
    assert any(getattr(line, "_scientific_errorbar", False) for line in axes.lines)
    assert figure.scientific_metadata["error"]["formula"] == "y - reference"
    assert figure.scientific_metadata["error_bars"]["series"][1]["y_lower"] == [0.05, 0.04, 0.03]
    plt.close(figure)


def test_cli_error_bars_record_definition_and_reject_a_missing_one(tmp_path):
    source = tmp_path / "repeats.csv"
    pd.DataFrame({"radius": [0.0, 1.0], "velocity": [1.0, 0.5], "sd": [0.1, 0.05]}).to_csv(source, index=False)
    target = tmp_path / "uncertainty"
    result = subprocess.run([sys.executable, str(TEMPLATE), "--input", str(source), "--kind", "point-line",
                             "--x", "radius", "--y", "velocity", "--yerr", "sd",
                             "--errorbar-definition", "sample standard deviation, n=4",
                             "--output", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((tmp_path / "uncertainty_metadata.json").read_text())
    assert metadata["error_bars"]["definition"] == "sample standard deviation, n=4"
    assert metadata["error_bars"]["y"] == {"mode": "symmetric", "source": "sd"}
    assert metadata["error"] is None
    assert target.with_suffix(".jpg").stat().st_size > 1000
    missing = subprocess.run([sys.executable, str(TEMPLATE), "--input", str(source), "--kind", "point-line",
                              "--x", "radius", "--y", "velocity", "--yerr", "sd",
                              "--output", str(tmp_path / "missing")], capture_output=True, text=True)
    assert missing.returncode != 0
    assert "errorbar-definition" in missing.stderr
    conflict = subprocess.run([sys.executable, str(TEMPLATE), "--input", str(source), "--kind", "point-line",
                               "--x", "radius", "--y", "velocity", "--yerr", "sd", "--yerr-lower", "sd",
                               "--errorbar-definition", "sd", "--output", str(tmp_path / "conflict")],
                              capture_output=True, text=True)
    assert conflict.returncode != 0
    assert "not both" in conflict.stderr
