import os
from pathlib import Path
import subprocess
import sys
import warnings

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scientific-plotting" / "scripts" / "plot_template.py"
sys.path.insert(0, str(TEMPLATE.parent))

from plot_template import (CATEGORICAL_COLORS, MARKERS, ORDERED_COLORS, SCATTER_DENSE_PT, SCATTER_SPARSE_PT,
                           TEXT_SIZES_PT, _line_vertices, _palette, connected_stroke, format_axis_label,
                           render_multipanel, render_plot, resolve_font)


@pytest.fixture
def observations():
    return pd.DataFrame({
        "distance": [0.02, 0.00, 0.01, 0.02, 0.00, 0.01],
        "measurement": [3.0, 1.0, 2.0, 4.0, 1.5, 2.5],
        "method": ["A", "A", "A", "B", "B", "B"],
    })


@pytest.mark.parametrize("kind", ["point-line", "line", "bar", "scatter", "heatmap", "violin"])
def test_six_kinds_export_jpeg(tmp_path, observations, kind):
    if kind == "heatmap":
        data = np.array([[1.0, 2.0], [3.0, 4.0]])
        mappings = {}
    elif kind == "violin":
        data, mappings = observations, {"x": "method", "y": "measurement"}
    elif kind == "bar":
        data = pd.DataFrame({"distance": ["near", "far"], "measurement": [2, 3]})
        mappings = {"x": "distance", "y": "measurement"}
    else:
        data = observations
        mappings = {"x": "distance", "y": "measurement", "group": "method"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, paths = render_plot(data, kind=kind, output=tmp_path / kind, **mappings)
    assert paths == [tmp_path / f"{kind}.jpg"]
    assert paths[0].stat().st_size > 1000
    assert all(spine.get_visible() for spine in axes.spines.values())
    plt.close(figure)


def test_point_line_preserves_order_per_group_and_scatter_is_unconnected(observations):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(observations, kind="point-line", x="distance", y="measurement", group="method")
    assert [list(line.get_xdata()) for line in axes.lines] == [[0.02, 0.0, 0.01], [0.02, 0.0, 0.01]]
    assert all(line.get_marker() != "None" for line in axes.lines)
    plt.close(figure)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(observations, kind="scatter", x="distance", y="measurement")
    assert not axes.lines
    plt.close(figure)


def test_numeric_group_colors_follow_group_value_not_first_appearance():
    data = {"time": [2, 2, 1, 1], "distance": [0.3, 0.1, 0.2, 0.0], "value": [3, 1, 2, 0]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(data, kind="point-line", x="distance", y="value", group="time")
    assert [line.get_label() for line in axes.lines] == ["1", "2"]
    assert [list(line.get_xdata()) for line in axes.lines] == [[0.2, 0.0], [0.3, 0.1]]
    assert [line.get_color() for line in axes.lines] == [ORDERED_COLORS[0], ORDERED_COLORS[-1]]
    plt.close(figure)


def test_ordered_palette_trends_yellow_to_teal_and_differs_from_methods():
    data = pd.DataFrame({"group": [5, 1, 3, 2, 4], "x": [0, 0, 0, 0, 0],
                         "y": [5, 1, 3, 2, 4]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        ordered_figure, ordered_axes, _ = render_plot(data, kind="point-line", x="x", y="y", group="group")
        method_figure, method_axes, _ = render_plot(data, kind="point-line", x="x", y="y",
                                                    group="group", group_kind="categorical")
    from matplotlib.colors import to_rgb

    ordered_colors = [line.get_color() for line in ordered_axes.lines]
    brightness = [sum(component * weight for component, weight in zip(to_rgb(color), (0.2126, 0.7152, 0.0722)))
                  for color in ordered_colors]
    assert ordered_colors[0] == ORDERED_COLORS[0]
    assert ordered_colors[-1] == ORDERED_COLORS[-1]
    assert all(first > second for first, second in zip(brightness, brightness[1:]))
    assert [line.get_color() for line in method_axes.lines] != ordered_colors
    plt.close(ordered_figure)
    plt.close(method_figure)



def test_palettes_keep_contrast_and_point_line_shapes():
    def naive_luma(color):
        return sum(component * weight for component, weight in zip(colors.to_rgb(color), (0.2126, 0.7152, 0.0722)))

    def relative_luminance(color):
        def linearize(channel):
            return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        red, green, blue = colors.to_rgb(color)
        return 0.2126 * linearize(red) + 0.7152 * linearize(green) + 0.0722 * linearize(blue)

    ordered_luma = [naive_luma(color) for color in ORDERED_COLORS]
    assert all(first - second >= 0.025 for first, second in zip(ordered_luma, ordered_luma[1:]))
    hues = [colors.rgb_to_hsv(colors.to_rgb(color))[0] for color in ORDERED_COLORS]
    assert hues[0] < 0.15 < hues[-1]
    assert all(earlier < later for earlier, later in zip(hues, hues[1:]))
    for color in (*ORDERED_COLORS, *CATEGORICAL_COLORS):
        assert 1.05 / (relative_luminance(color) + 0.05) >= 3.4
    samples = [np.array(colors.to_rgb(color)) for color in CATEGORICAL_COLORS]
    distances = [np.linalg.norm(samples[left] - samples[right])
                 for left in range(len(samples)) for right in range(left + 1, len(samples))]
    assert min(distances) >= 0.22
    assert MARKERS == ("o", "s", "^", "D", "v", "p")
    blended = _palette(4, ordered=True)
    blended_luma = [naive_luma(color) for color in blended]
    assert blended[0] == ORDERED_COLORS[0] and blended[-1] == ORDERED_COLORS[-1]
    assert all(earlier > later for earlier, later in zip(blended_luma, blended_luma[1:]))


def test_inward_ticks_and_two_grid_styles(observations):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(observations, kind="line", x="distance", y="measurement")
    for axis in (axes.xaxis, axes.yaxis):
        assert axis.get_major_ticks()[0].tick2line.get_visible()
        assert axis.get_minor_ticks()[0].tick2line.get_visible()
        assert axis.get_tick_params(which="major")["direction"] == "in"
    assert any(line.get_visible() and line.get_linestyle() == "-" for line in axes.get_xgridlines())
    assert any(tick.gridline.get_visible() and tick.gridline.get_linestyle() == "--"
               for tick in axes.xaxis.get_minor_ticks())
    assert axes.spines["top"].get_linewidth() == 0.95
    assert axes.xaxis.get_major_ticks()[0].gridline.get_color() == "#b1b1b1"
    assert axes.xaxis.get_minor_ticks()[0].gridline.get_color() == "#d1d1d1"
    plt.close(figure)


def test_line_plot_keeps_reference_frame_margins_and_ordered_colors():
    samples = pd.DataFrame({"x": [0, 1, 2] * 5,
                            "y": [level * value for level in (1, 2, 3, 4, 5) for value in (0, 1, 0)],
                            "time": [level for level in range(5) for _ in range(3)]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(samples, kind="point-line", x="x", y="y", group="time")
    position = axes.get_position()
    assert position.x0 >= 0.135 and position.x1 <= 0.91
    assert position.y0 >= 0.13 and position.y1 <= 0.95
    assert [line.get_color() for line in axes.lines] == list(ORDERED_COLORS)
    plt.close(figure)


def test_validation_refuses_implicit_aggregation(tmp_path):
    duplicated = pd.DataFrame({"category": ["A", "A"], "value": [1, 2]})
    with pytest.raises(ValueError, match="aggregate explicitly"):
        render_plot(duplicated, kind="bar", x="category", y="value", output=tmp_path / "bar")
    missing = pd.DataFrame({"x": [0, 1], "y": [1.0, np.nan]})
    with pytest.raises(ValueError, match="missing values"):
        render_plot(missing, kind="point-line", x="x", y="y")


def test_font_fallback_is_reported(monkeypatch):
    from matplotlib import font_manager

    monkeypatch.setattr(font_manager.fontManager, "ttflist", [
        type("FontEntry", (), {"name": "Liberation Sans"})(),
        type("FontEntry", (), {"name": "Liberation Serif"})(),
    ])
    with pytest.warns(UserWarning, match="Arial not installed"):
        assert resolve_font("Arial") == "Liberation Sans"
    with pytest.warns(UserWarning, match="Times New Roman not installed"):
        assert resolve_font("Times New Roman") == "Liberation Serif"
    with pytest.raises(RuntimeError, match="思源黑体"):
        resolve_font("思源黑体")


def test_chinese_fonts_prefer_source_han_and_warn_on_fallback(monkeypatch):
    from matplotlib import font_manager

    monkeypatch.setattr(font_manager.fontManager, "ttflist", [
        type("FontEntry", (), {"name": "Noto Sans CJK SC"})(),
        type("FontEntry", (), {"name": "Noto Serif CJK SC"})(),
        type("FontEntry", (), {"name": "WenQuanYi Micro Hei"})(),
        type("FontEntry", (), {"name": "AR PL UMing CN"})(),
    ])
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        assert resolve_font("思源黑体") == "Noto Sans CJK SC"
        assert resolve_font("Noto Sans CJK SC") == "Noto Sans CJK SC"
        assert resolve_font("Source Han Sans SC") == "Noto Sans CJK SC"
        assert resolve_font("思源宋体") == "Noto Serif CJK SC"
    monkeypatch.setattr(font_manager.fontManager, "ttflist", [
        type("FontEntry", (), {"name": "WenQuanYi Micro Hei"})(),
        type("FontEntry", (), {"name": "AR PL UMing CN"})(),
    ])
    with pytest.warns(UserWarning, match="思源黑体 not installed"):
        assert resolve_font("思源黑体") == "WenQuanYi Micro Hei"
    with pytest.warns(UserWarning, match="思源宋体 not installed"):
        assert resolve_font("思源宋体") == "AR PL UMing CN"
    with pytest.raises(ValueError, match="思源黑体"):
        resolve_font("Comic Sans MS")


@pytest.mark.parametrize(("source", "expected"), [
    ("t^*", r"$t^{*}$"),
    ("t^+", r"$t^{+}$"),
    (r"\( t^* \)", r"$t^*$"),
    (r"\(t^+\)", r"$t^+$"),
    ("无量纲时间 t^*", "无量纲时间 $t^{*}$"),
    (r"无量纲时间 \(t^*\)", "无量纲时间 $t^*$"),
    (r"Wall distance, $y^+$", r"Wall distance, $y^+$"),
    ("t_{wall}", r"$t_{wall}$"),
    ("10^-3", r"$10^{-3}$"),
    ("x^2", r"$x^{2}$"),
    ("Re_b", r"$Re_{b}$"),
    ("t^*_w", r"$t^{*}_{w}$"),
    ("Distance (m)", "Distance (m)"),
    ("Radius, r/R", "Radius, r/R"),
    (r"t\^*", "t^*"),
    ("Velocity, u^+ (m/s)", r"Velocity, $u^{+}$ (m/s)"),
])
def test_axis_label_scripts(source, expected):
    assert format_axis_label(source) == expected


def test_chinese_axis_label_renders_scripts(tmp_path):
    from matplotlib import font_manager

    available = {entry.name for entry in font_manager.fontManager.ttflist}
    if "Noto Sans CJK SC" not in available or "Noto Serif CJK SC" not in available:
        pytest.skip("Noto CJK SC is not installed")
    frame = pd.DataFrame({"x": [-1.0, 0.0, 1.0], "y": [1.0, 2.0, 1.5]})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure, axes, paths = render_plot(
            frame, kind="line", x="x", y="y", font="思源黑体",
            xlabel=r"无量纲时间 \(t^*\)", ylabel="速度 t^+", output=tmp_path / "sans")
        figure.canvas.draw()
        assert axes.get_xlabel() == r"无量纲时间 $t^*$"
        assert axes.get_ylabel() == r"速度 $t^{+}$"
        plt.close(figure)
        figure, axes, _ = render_plot(
            frame, kind="line", x="x", y="y", font="思源宋体",
            xlabel="t^*", ylabel=r"壁面距离 \(y^+\)", output=tmp_path / "serif")
        figure.canvas.draw()
        assert axes.get_xlabel() == r"$t^{*}$"
        assert axes.get_ylabel() == r"壁面距离 $y^+$"
        plt.close(figure)
    assert paths and paths[0].exists()
    assert not any("Glyph" in str(item.message) for item in caught)
    with pytest.warns(UserWarning, match="Arial not installed"):
        with pytest.raises(ValueError, match="思源黑体"):
            render_plot(frame, kind="line", x="x", y="y", xlabel="无量纲时间", ylabel="t^*")


def test_cli_exports_requested_formats_and_reproducible_scripts(tmp_path):
    source = tmp_path / "input.csv"
    pd.DataFrame({"distance": [0.02, 0.0, 0.01], "measurement": [3, 1, 2]}).to_csv(source, index=False)
    target = tmp_path / "curve"
    args = [sys.executable, str(TEMPLATE), "--input", str(source), "--kind", "point-line",
            "--x", "distance", "--y", "measurement", "--output", str(target),
            "--line-width", "1.2", "--marker-size", "6.5"]
    subprocess.run(args, check=True, capture_output=True, text=True)
    assert {entry.name for entry in tmp_path.glob("curve.*")} == {"curve.jpg"}
    assert (tmp_path / "curve_template.py").exists()
    wrapper = tmp_path / "curve_reproduce.py"
    assert wrapper.exists()
    assert "--line-width" in wrapper.read_text()
    assert "--marker-size" in wrapper.read_text()
    target.with_suffix(".jpg").unlink()
    subprocess.run([sys.executable, str(wrapper)], check=True, capture_output=True, text=True)
    assert target.with_suffix(".jpg").exists()
    subprocess.run([*args, "--format", "tiff", "--dpi", "120"], check=True, capture_output=True, text=True)
    assert (tmp_path / "curve.tiff").stat().st_size > 500
    refused = subprocess.run([*args, "--format", "png"], capture_output=True, text=True)
    assert refused.returncode != 0
    assert "JPEG and TIFF" in refused.stderr


def test_only_requested_format_is_written(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, _, paths = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                                       output=tmp_path / "vector", formats=["tiff"], dpi=120)
    assert paths == [tmp_path / "vector.tiff"]
    assert not (tmp_path / "vector.jpg").exists()
    plt.close(figure)


def test_interior_legend_does_not_cover_sampled_curve():
    positions = np.linspace(0, 0.1, 11)
    rows = [{"position": float(position), "value": float((1 - 0.16 * index) * np.sin(np.pi * position / 0.1)),
             "time": time}
            for index, time in enumerate([0, 0.2, 0.5, 0.8, 1]) for position in positions]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(pd.DataFrame(rows), kind="point-line", x="position", y="value",
                                      group="time", size="double")
    box = axes.get_legend().get_window_extent(figure.canvas.get_renderer())
    points = _line_vertices(axes)
    assert not np.any((points[:, 0] >= box.x0) & (points[:, 0] <= box.x1)
                      & (points[:, 1] >= box.y0) & (points[:, 1] <= box.y1))
    assert figure.bbox.contains(*box.p0) and figure.bbox.contains(*box.p1)
    plt.close(figure)


@pytest.mark.parametrize("size", ["single", "medium", "double", "aip-single", "aip-double"])
def test_text_sizes_follow_physical_figure_preset(size):
    samples = pd.DataFrame({"x": [0, 1, 2, 0, 1, 2], "y": [1, 2, 1, 2, 3, 2],
                            "series": ["first"] * 3 + ["second"] * 3})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(samples, kind="point-line", x="x", y="y",
                                      xlabel="Time (s)", ylabel="Signal (a.u.)", title="Measurements",
                                      group="series", size=size)
    sizes = TEXT_SIZES_PT[size]
    assert axes.xaxis.label.get_fontsize() == axes.yaxis.label.get_fontsize() == sizes["label"]
    assert axes.title.get_fontsize() == sizes["title"]
    assert axes.get_xticklabels()[0].get_fontsize() == sizes["tick"]
    assert axes.get_yticklabels()[0].get_fontsize() == sizes["tick"]
    assert all(label.get_fontsize() == sizes["legend"] for label in axes.get_legend().get_texts())
    plt.close(figure)


def test_crowded_single_legend_does_not_shrink_font():
    positions = np.linspace(0, 1, 11)
    samples = pd.DataFrame([{"x": position, "y": height * np.sin(np.pi * position), "series": level}
                            for level, height in enumerate((1, .82, .61, .45, .36))
                            for position in positions])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        with pytest.warns(UserWarning, match="consider --size double"):
            figure, axes, _ = render_plot(samples, kind="point-line", x="x", y="y",
                                          group="series", size="single")
    assert all(label.get_fontsize() == TEXT_SIZES_PT["single"]["legend"]
               for label in axes.get_legend().get_texts())
    legend_box = axes.get_legend().get_window_extent(figure.canvas.get_renderer())
    axes_box = axes.get_window_extent(figure.canvas.get_renderer())
    assert legend_box.y0 >= axes_box.y1 - 1 or legend_box.y1 <= axes_box.y0 + 1
    assert axes_box.x0 < legend_box.x1 and legend_box.x0 < axes_box.x1
    assert axes.get_position().x1 > 0.85
    plt.close(figure)


def test_open_corner_keeps_legend_inside_and_omits_figure_title():
    radius = np.linspace(0, 1, 40)
    exact = 2 * (1 - radius ** 2)
    frame = pd.DataFrame({"x": np.r_[radius, radius], "y": np.r_[exact, exact * 0.98],
                          "series": ["Exact"] * len(radius) + ["CFD"] * len(radius)})
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        figure, axes, _ = render_plot(frame, kind="line", x="x", y="y", group="series", size="double",
                                      xlabel="Radius, r/R", ylabel="Axial velocity, u/Ub")
    assert axes.get_title() == ""
    legend_box = axes.get_legend().get_window_extent(figure.canvas.get_renderer())
    axes_box = axes.get_window_extent(figure.canvas.get_renderer())
    assert axes_box.contains(*legend_box.p0) and axes_box.contains(*legend_box.p1)
    assert axes.get_position().x1 > 0.85
    plt.close(figure)


def test_outside_legend_uses_top_band_without_narrowing_the_axes():
    frame = pd.DataFrame({"x": np.tile(np.linspace(0, 1, 8), 3),
                          "y": np.r_[np.linspace(0, 1, 8), np.linspace(0.2, 0.8, 8), np.linspace(1, 0, 8)],
                          "series": ["Theoretical reference"] * 8 + ["Numerical result (synth.)"] * 8
                          + ["Measurement (synth.)"] * 8})
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        figure, axes, _ = render_plot(frame, kind="line", x="x", y="y", group="series", size="double",
                                      legend="outside", xlabel="Radius, r/R", ylabel="Velocity, u/Ub")
    legend_box = axes.get_legend().get_window_extent(figure.canvas.get_renderer())
    axes_box = axes.get_window_extent(figure.canvas.get_renderer())
    assert legend_box.y0 >= axes_box.y1 - 1
    assert legend_box.x0 >= axes_box.x0 - 1
    assert legend_box.x1 <= axes_box.x1 + 1
    assert axes.get_position().x1 > 0.85
    assert figure.subplotpars.right > 0.85
    plt.close(figure)


def test_outside_legend_stays_within_the_top_spine_and_close_to_it():
    regions = ["Asia", "Africa", "Oceania", "North America", "Europe", "South America", "Sample median"]
    rows = [{"x": 10 ** (2 + index / 3), "y": 40 + index, "region": region} for index, region in enumerate(regions)]
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        figure, axes, _ = render_plot(pd.DataFrame(rows), kind="scatter", x="x", y="y", group="region",
                                      size="double", xscale="log", legend="outside",
                                      xlabel="GDP per capita (2011 international-$)",
                                      ylabel="Life expectancy (years)")
    renderer = figure.canvas.get_renderer()
    legend_box = axes.get_legend().get_window_extent(renderer)
    axes_box = axes.get_window_extent(renderer)
    gap = legend_box.y0 - axes_box.y1
    assert legend_box.x0 >= axes_box.x0 - 1
    assert legend_box.x1 <= axes_box.x1 + 1
    assert 0 <= gap <= 6 * figure.dpi / 72
    assert axes.get_position().x1 > 0.85
    plt.close(figure)


def test_shared_legend_stays_within_outer_spines():
    frame = pd.DataFrame({"x": [0, 1, 0, 1], "y": [1, 2, 2, 3], "series": ["Alpha", "Alpha", "Beta", "Beta"]})
    panel = {"data": frame, "kind": "line", "x": "x", "y": "y", "group": "series",
             "xlabel": "Position (-)", "ylabel": "Signal (-)"}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Arial not installed")
        figure, axes, _ = render_multipanel([panel, panel], ncols=2, size="double", height_mm=140)
    renderer = figure.canvas.get_renderer()
    legend_box = figure.legends[0].get_window_extent(renderer)
    boxes = [panel_axes.get_window_extent(renderer) for panel_axes in axes]
    left, right = min(box.x0 for box in boxes), max(box.x1 for box in boxes)
    top = max(box.y1 for box in boxes)
    assert legend_box.x0 >= left - 1
    assert legend_box.x1 <= right + 1
    assert 0 <= legend_box.y0 - top <= 28 * figure.dpi / 72
    for panel_axes in axes:
        for text in panel_axes.texts:
            if getattr(text, "_scientific_panel_letter", False):
                assert not legend_box.overlaps(text.get_window_extent(renderer))
    plt.close(figure)


def test_excel_and_grouping_preserve_order(tmp_path):
    source = tmp_path / "data.xlsx"
    pd.DataFrame({"time": [0.2, 0.0, 0.1], "signal": [2, 0, 1]}).to_excel(source, index=False)
    subprocess.run([sys.executable, str(TEMPLATE), "--input", str(source), "--kind", "point-line",
                    "--x", "time", "--y", "signal", "--output", str(tmp_path / "excel")],
                   check=True, capture_output=True, text=True)
    assert (tmp_path / "excel.jpg").is_file()


def test_fixed_export_dimensions(tmp_path):
    from PIL import Image

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, _, _ = render_plot({"time": [0, 1], "signal": [1, 2]}, kind="line",
                                   x="time", y="signal", size="single", output=tmp_path / "shape")
    with Image.open(tmp_path / "shape.jpg") as image:
        assert abs(image.width - 90 / 25.4 * 300) < 2
        assert abs(image.height - 67.5 / 25.4 * 300) < 2
        assert abs(image.width / image.height - 4 / 3) < 0.02
    plt.close(figure)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, _, _ = render_plot({"time": [0, 1], "signal": [1, 2]}, kind="line",
                                   x="time", y="signal", size="double", output=tmp_path / "double")
    with Image.open(tmp_path / "double.jpg") as image:
        assert abs(image.width - 190 / 25.4 * 300) < 2
        assert abs(image.height - 142.5 / 25.4 * 300) < 2
        assert abs(image.width / image.height - 4 / 3) < 0.02
    plt.close(figure)


def test_point_line_marks_and_strokes_follow_display_density():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        sparse_figure, sparse_axes, _ = render_plot({"x": [0, 1, 2, 3, 4], "y": [1, 2, 3, 2, 1]},
                                                     kind="point-line", x="x", y="y")
        dense_figure, dense_axes, _ = render_plot({"x": np.linspace(0, 4, 400),
                                                   "y": np.sin(np.linspace(0, 4, 400))},
                                                 kind="point-line", x="x", y="y")
    assert sparse_axes.lines[0].get_linewidth() == 1.5
    assert sparse_axes.lines[0].get_markersize() == 6.2
    assert sparse_axes.lines[0].get_marker() == "o"
    assert colors.to_rgb(sparse_axes.lines[0].get_markerfacecolor()) == colors.to_rgb(sparse_axes.lines[0].get_color())
    assert colors.to_rgb(sparse_axes.lines[0].get_markeredgecolor()) == colors.to_rgb("white")
    assert dense_axes.lines[0].get_linewidth() == 0.7
    assert dense_axes.lines[0].get_markersize() == 2.6
    assert colors.to_rgb(dense_axes.lines[0].get_markerfacecolor()) == colors.to_rgb(dense_axes.lines[0].get_color())
    assert colors.to_rgb(dense_axes.lines[0].get_markeredgecolor()) == colors.to_rgb(dense_axes.lines[0].get_color())
    assert len(dense_axes.lines[0].get_xdata()) == 400
    plt.close(sparse_figure)
    plt.close(dense_figure)


def test_overlapping_series_do_not_shrink_well_spaced_lines():
    shared = pd.DataFrame({"x": [0, 1, 2, 3] * 2, "y": [0, 1, 0, 1] * 2,
                           "series": ["first"] * 4 + ["second"] * 4})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        line_figure, line_axes, _ = render_plot(shared, kind="line", x="x", y="y", group="series")
        scatter_figure, scatter_axes, _ = render_plot(shared, kind="scatter", x="x", y="y")
    assert all(line.get_linewidth() == 1.5 for line in line_axes.lines)
    assert all(line.get_marker() == "None" for line in line_axes.lines)
    assert np.all(scatter_axes.collections[0].get_sizes() == SCATTER_DENSE_PT ** 2)
    plt.close(line_figure)
    plt.close(scatter_figure)


def test_scatter_markers_remain_visible_as_points_get_dense():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        sparse_figure, sparse_axes, _ = render_plot({"x": [0, 1, 2, 3], "y": [0, 1, 0, 1]},
                                                     kind="scatter", x="x", y="y")
        dense_figure, dense_axes, _ = render_plot({"x": np.linspace(0, 3, 400),
                                                   "y": np.sin(np.linspace(0, 3, 400))},
                                                 kind="scatter", x="x", y="y")
    assert np.all(sparse_axes.collections[0].get_sizes() == SCATTER_SPARSE_PT ** 2)
    assert np.all(dense_axes.collections[0].get_sizes() == SCATTER_DENSE_PT ** 2)
    assert len(dense_axes.collections[0].get_offsets()) == 400
    assert dense_axes.collections[0].get_alpha() == 0.85
    plt.close(sparse_figure)
    plt.close(dense_figure)


def test_close_other_series_do_not_shrink_point_line_markers():
    points = pd.DataFrame({"year": [*range(12)] * 2,
                           "value": [*range(12)] * 2,
                           "series": ["Jan"] * 12 + ["Apr"] * 12})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(points, kind="point-line", x="year", y="value",
                                     group="series", size="double")
    assert all(line.get_linewidth() == 1.5 for line in axes.lines)
    assert all(line.get_markersize() == 6.2 for line in axes.lines)
    assert [line.get_marker() for line in axes.lines] == ["o", "s"]
    plt.close(figure)


def test_edge_grid_does_not_overlap_axis_border():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot({"year": [1970, 2020], "life": [70.6, 84.7]},
                                     kind="point-line", x="year", y="life", size="double")
    ticks = {round(tick.get_loc()): tick for tick in axes.yaxis.get_major_ticks()}
    assert not ticks[70].gridline.get_visible()
    assert ticks[72].gridline.get_visible()
    assert ticks[70].tick1line.get_visible()
    plt.close(figure)


def test_explicit_marker_and_stroke_overrides():
    data = {"x": [0, 1, 2], "y": [1, 2, 3]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = render_plot(data, kind="point-line", x="x", y="y",
                                     line_width=1.2, marker_size=6.5)
        scatter_figure, scatter_axes, _ = render_plot(data, kind="scatter", x="x", y="y",
                                                     marker_size=6.5)
    assert axes.lines[0].get_linewidth() == 1.2
    assert axes.lines[0].get_markersize() == 6.5
    assert scatter_axes.collections[0].get_sizes()[0] == 6.5 ** 2
    plt.close(figure)
    plt.close(scatter_figure)
    with pytest.raises(ValueError, match="marker_size"):
        render_plot(data, kind="line", x="x", y="y", marker_size=3)
    with pytest.raises(ValueError, match="line_width"):
        render_plot(data, kind="scatter", x="x", y="y", line_width=2)


def test_rejects_labels_that_would_be_cropped(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with pytest.raises(ValueError, match="label is clipped"):
            render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                        xlabel="Very long axis label " * 30, output=tmp_path / "cropped")
    assert not (tmp_path / "cropped.jpg").exists()
