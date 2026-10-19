import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import warnings

import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scientific-plotting/scripts/plot_template.py"
sys.path.insert(0, str(TEMPLATE.parent))
from plot_template import connected_stroke, render_plot


@pytest.fixture(autouse=True)
def clean_figures():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*not installed; using.*")
        yield
    plt.close("all")


def mixed_data():
    return pd.DataFrame({"x": [1, 3, 2] * 3, "y": [1, 3, 2, 1.01, 3.02, 2.03, .99, 3.01, 2.02],
                         "series": ["Theory"] * 3 + ["CFD (synth.)"] * 3 + ["Samples (synth.)"] * 3})


def mixed_styles():
    return {"Theory": {"kind": "line", "linestyle": "--", "color": "#126b80", "line_width": 2},
            "CFD (synth.)": {"kind": "point-line", "marker": "s", "linestyle": "-.",
                              "line_width": 1.7, "marker_size": 4},
            "Samples (synth.)": {"kind": "scatter", "marker": "^", "marker_size": 6}}


@pytest.mark.parametrize("xscale,yscale", [("log", "linear"), ("linear", "log"), ("log", "log")])
def test_native_log_axes_have_real_minor_ticks(xscale, yscale):
    coordinates = np.geomspace(.01, 100, 80)
    figure, axes, _ = render_plot({"x": coordinates, "y": coordinates ** -.5}, kind="point-line",
                                  x="x", y="y", xscale=xscale, yscale=yscale)
    for axis, scale in ((axes.xaxis, xscale), (axes.yaxis, yscale)):
        if scale == "log":
            assert isinstance(axis.get_major_locator(), LogLocator)
            assert isinstance(axis.get_minor_locator(), LogLocator)
            assert any(tick.gridline.get_visible() and tick.gridline.get_linestyle() == "--"
                       for tick in axis.get_minor_ticks())
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), coordinates)
    assert all(spine.get_visible() for spine in axes.spines.values())


@pytest.mark.parametrize("column", ["x", "y"])
@pytest.mark.parametrize("bad", [0, -1])
def test_log_nonpositive_refused_before_export(tmp_path, column, bad):
    data = {"x": [1, 2], "y": [1, 2]}
    data[column][1] = bad
    with pytest.raises(ValueError, match="non-positive"):
        render_plot(data, kind="line", x="x", y="y", output=tmp_path / "bad", **{column + "scale": "log"})
    assert not list(tmp_path.iterdir())


def test_mixed_explicit_styles_preserve_data_and_semantics():
    frame = mixed_data()
    figure, axes, _ = render_plot(frame, kind="mixed", x="x", y="y", group="series",
                                  size="double", series_styles=mixed_styles())
    assert len(axes.lines) == 2 and len(axes.collections) == 1
    assert axes.lines[0].get_marker() == "None"
    assert axes.lines[0].get_linestyle() == "--"
    assert axes.lines[0].get_color() == "#126b80"
    assert axes.lines[1].get_marker() == "s"
    assert axes.lines[1].get_linestyle() == "-."
    assert axes.lines[0].get_linewidth() == 2
    assert axes.lines[1].get_markersize() == 4
    np.testing.assert_array_equal(axes.collections[0].get_sizes(), [36] * 3)
    for line in axes.lines:
        np.testing.assert_array_equal(line.get_xdata(), [1, 3, 2])
    np.testing.assert_array_equal(axes.collections[0].get_offsets(), frame.iloc[6:][["x", "y"]])


@pytest.mark.parametrize("kind", ["line", "point-line"])
def test_native_kind_cannot_be_changed_by_series_style(kind):
    with pytest.raises(ValueError, match="mixed"):
        render_plot(mixed_data(), kind=kind, x="x", y="y", group="series", series_styles=mixed_styles())


@pytest.mark.parametrize("styles", [{}, {"Theory": {"color": "red"}}, {"not present": {"kind": "line"}}])
def test_mixed_requires_complete_explicit_configuration(styles):
    with pytest.raises(ValueError):
        render_plot(mixed_data(), kind="mixed", x="x", y="y", group="series", series_styles=styles)


def test_cli_log_mixed_reproducer_pins_style_config(tmp_path):
    data_path, style_path = tmp_path / "input.csv", tmp_path / "styles.json"
    mixed_data().to_csv(data_path, index=False)
    style_path.write_text(json.dumps(mixed_styles()), encoding="utf-8")
    result = subprocess.run([sys.executable, str(TEMPLATE), "--input", str(data_path), "--kind", "mixed",
                             "--x", "x", "--y", "y", "--group", "series", "--size", "double",
                             "--xscale", "log", "--series-config", str(style_path),
                             "--output", str(tmp_path / "mixed")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    original = (tmp_path / "mixed.png").read_bytes()
    style_path.unlink()
    subprocess.run([sys.executable, str(tmp_path / "mixed_reproduce.py")], check=True, capture_output=True)
    assert (tmp_path / "mixed.png").read_bytes() == original
    assert {path.suffix for path in tmp_path.glob("mixed.*")} == {".png"}


@pytest.mark.parametrize("definition", ["signed", "absolute", "relative"])
def test_error_values_and_identity_are_explicit(definition):
    frame = mixed_data()
    figure, axes, _ = render_plot(frame, kind="mixed", x="x", y="y", group="series", size="double",
                                  series_styles=mixed_styles(),
                                  error={"reference": "Theory", "definition": definition})
    error_axes = figure.scientific_error_axes
    expected = frame.iloc[3:6]["y"].to_numpy() - frame.iloc[:3]["y"].to_numpy()
    if definition == "absolute":
        expected = np.abs(expected)
    elif definition == "relative":
        expected /= np.abs(frame.iloc[:3]["y"].to_numpy())
    np.testing.assert_allclose(error_axes.lines[0].get_ydata(), expected)
    np.testing.assert_array_equal(error_axes.lines[0].get_xdata(), [1, 3, 2])
    main_line, error_line = axes.lines[1], error_axes.lines[0]
    for attribute in ("color", "linestyle", "linewidth", "marker", "markersize", "markerfacecolor", "markeredgewidth"):
        assert getattr(main_line, "get_" + attribute)() == getattr(error_line, "get_" + attribute)()
    for attribute in ("sizes", "facecolors", "edgecolors"):
        np.testing.assert_array_equal(getattr(axes.collections[0], "get_" + attribute)(),
                                      getattr(error_axes.collections[0], "get_" + attribute)())
    assert axes.collections[0].get_alpha() == error_axes.collections[0].get_alpha()
    assert error_axes.get_yscale() == "linear"
    assert len(error_axes.lines) == len(error_axes.collections) == 1
    assert figure.scientific_metadata["error"]["comparisons"][0]["method"] == "exact"


def test_relative_error_zero_policy_is_raise(tmp_path):
    frame = mixed_data()
    frame.loc[0, "y"] = 0
    for config, message in [({"zero_reference": "raise"}, "zero reference"),
                             ({"zero_reference": "drop"}, "only zero_reference")]:
        with pytest.raises(ValueError, match=message):
            render_plot(frame, kind="line", x="x", y="y", group="series", output=tmp_path / "bad",
                        error={"reference": "Theory", "definition": "relative", **config})
    assert not list(tmp_path.iterdir())


def test_error_coordinate_mismatch_refused_and_linear_interpolation_recorded():
    frame = pd.DataFrame({"x": [0, 1, 2, 1.5, .5], "y": [0, 2, 4, 3.01, .98],
                          "series": ["Theory"] * 3 + ["CFD (synth.)"] * 2})
    with pytest.raises(ValueError, match="Coordinate mismatch"):
        render_plot(frame, kind="point-line", x="x", y="y", group="series",
                    error={"reference": "Theory", "definition": "signed"})
    figure, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", group="series", size="double",
                                  error={"reference": "Theory", "definition": "signed", "interpolation": "linear"})
    np.testing.assert_allclose(figure.axes[1].lines[0].get_ydata(), [.01, -.02])
    np.testing.assert_array_equal(figure.axes[1].lines[0].get_xdata(), [1.5, .5])
    assert figure.scientific_metadata["error"]["comparisons"][0]["method"].startswith("linear")


@pytest.mark.parametrize("ref_x,comparison_x,message", [([0, 2, 1], [.5], "strictly increasing"),
                                                        ([0, 1, 1], [.5], "strictly increasing"),
                                                        ([0, 1, 2], [3], "extrapolate"),
                                                        ([0], [0.5], "strictly increasing")])
def test_interpolation_does_not_sort_or_extrapolate(ref_x, comparison_x, message):
    frame = pd.DataFrame({"x": ref_x + comparison_x, "y": [1] * (len(ref_x) + len(comparison_x)),
                          "series": ["ref"] * len(ref_x) + ["synth"] * len(comparison_x)})
    with pytest.raises(ValueError, match=message):
        render_plot(frame, kind="line", x="x", y="y", group="series",
                    error={"reference": "ref", "definition": "signed", "interpolation": "linear"})


def test_same_length_reordered_coordinates_are_not_subtracted_by_row():
    frame = pd.DataFrame({"x": [1, 2, 3, 3, 2, 1], "y": [1, 2, 3, 3, 2, 1], "series": ["ref"] * 3 + ["synth"] * 3})
    with pytest.raises(ValueError, match="Coordinate mismatch"):
        render_plot(frame, kind="line", x="x", y="y", group="series", error={"reference": "ref", "definition": "signed"})


@pytest.mark.parametrize("scale", ["linear", "log"])
def test_density_uses_each_series_final_transform(scale):
    sparse = np.linspace(1, 100, 5) if scale == "linear" else np.geomspace(1, 100, 5)
    dense = np.linspace(1, 100, 1001) if scale == "linear" else np.geomspace(1, 100, 1001)
    frame = pd.DataFrame({"x": np.r_[sparse, dense], "y": np.ones(len(sparse) + len(dense)),
                          "series": ["sparse"] * len(sparse) + ["dense"] * len(dense)})
    figure, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", group="series",
                                  xscale=scale, size="double", legend="outside")
    assert axes.lines[0].get_markersize() == 6.2
    assert axes.lines[1].get_markersize() == 2.6
    for line in axes.lines:
        vertices = axes.transData.transform(np.c_[line.get_xdata(), line.get_ydata()])
        spacing = np.median(np.linalg.norm(np.diff(vertices, axis=0), axis=1))
        expected = 1.2 if spacing < 4 else 1.35 if spacing < 12 else 1.8 if spacing >= 26 else 1.45
        assert line.get_linewidth() == expected
    assert len(axes.lines[1].get_xdata()) == 1001
    assert axes.lines[1].get_markevery() is None
    handles = axes.get_legend().legend_handles
    assert [handle.get_markersize() for handle in handles] == [6.2, 2.6]


def test_density_layout_change_recomputed_after_outside_legend():
    frame = pd.DataFrame({"x": np.linspace(0, 1, 27), "y": np.ones(27), "series": "synth"})
    _, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", group="series", size="double", legend="outside")
    vertices = axes.transData.transform(np.c_[axes.lines[0].get_xdata(), axes.lines[0].get_ydata()])
    spacing = np.median(np.linalg.norm(np.diff(vertices, axis=0), axis=1))
    assert spacing < 26
    assert axes.lines[0].get_markersize() == connected_stroke(spacing * 120 / axes.figure.dpi)[1]


def test_explicit_sizes_override_auto_per_series_then_global():
    frame = pd.DataFrame({"x": np.tile(np.linspace(0, 1, 1001), 2), "y": np.ones(2002),
                          "series": ["A"] * 1001 + ["B"] * 1001})
    _, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", group="series", size="double",
                             line_width=2.2, marker_size=6, series_styles={"A": {"line_width": 1.8, "marker_size": 4}})
    assert [line.get_linewidth() for line in axes.lines] == [1.8, 2.2]
    assert [line.get_markersize() for line in axes.lines] == [4, 6]


@pytest.mark.parametrize("size", ["single", "double"])
def test_error_log_and_long_outside_legend_are_not_clipped(size):
    from plot_template import TEXT_SIZES_PT, _check_text_layout

    frame = mixed_data().replace({"Theory": "Theoretical reference", "CFD (synth.)": "Numerical result (synth.)",
                                  "Samples (synth.)": "Measurement (synth.)"})
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Legend moved outside")
        figure, axes, _ = render_plot(frame, kind="point-line", x="x", y="y", group="series", size=size,
                                      xscale="log", legend="outside", xlabel="Position (-)", ylabel="Velocity (-)",
                                      error={"reference": "Theoretical reference", "definition": "signed"})
    _check_text_layout(figure)
    assert figure.axes[1].get_xscale() == "log"
    assert all(text.get_fontsize() == TEXT_SIZES_PT[size]["legend"] for text in axes.get_legend().get_texts())


def test_log_residual_minors_survive_ten_decades():
    _, axes, _ = render_plot({"x": np.arange(101), "y": np.geomspace(1, 1e-10, 101)},
                             kind="line", x="x", y="y", yscale="log", size="single")
    locations = [tick.get_loc() for tick in axes.yaxis.get_minor_ticks() if tick.gridline.get_visible()]
    assert any(np.isclose(location, 2e-6, rtol=1e-8, atol=0) for location in locations)
    assert any(np.isclose(location, 5e-9, rtol=1e-8, atol=0) for location in locations)
    assert not any(np.isclose(location, 3e-9, rtol=1e-8, atol=0) for location in locations)


def test_ylog_density_is_measured_in_log_display_space():
    _, axes, _ = render_plot({"x": np.ones(5), "y": np.geomspace(1e-10, 1, 5)},
                             kind="point-line", x="x", y="y", yscale="log", size="double")
    assert axes.lines[0].get_markersize() == 6.2
    assert axes.lines[0].get_linewidth() == 1.8


def test_sparse_scatter_size_is_independent_of_overlapping_dense_series():
    sparse = np.linspace(0, 1, 5)
    dense = np.linspace(0, 1, 1001)
    frame = pd.DataFrame({"x": np.r_[sparse, dense], "y": np.ones(1006),
                          "series": ["sparse"] * 5 + ["dense"] * 1001})
    _, axes, _ = render_plot(frame, kind="scatter", x="x", y="y", group="series", size="double")
    np.testing.assert_array_equal(axes.collections[0].get_sizes(), [6.2 ** 2] * 5)
    np.testing.assert_array_equal(axes.collections[1].get_sizes(), [5.0 ** 2] * 1001)
    assert axes.collections[0].get_alpha() == 1
    assert axes.collections[1].get_alpha() == .85


def test_custom_dash_identity_survives_error_and_legend():
    styles = mixed_styles()
    styles["CFD (synth.)"]["linestyle"] = [0, [7, 2, 1, 2]]
    figure, axes, _ = render_plot(mixed_data(), kind="mixed", x="x", y="y", group="series",
                                  size="double", series_styles=styles,
                                  error={"reference": "Theory", "definition": "signed"})
    assert axes.lines[1]._dash_pattern == figure.axes[1].lines[0]._dash_pattern
    assert axes.lines[1]._dash_pattern == axes.get_legend().legend_handles[1]._dash_pattern


@pytest.mark.parametrize("kind,style", [("line", {"marker": "o"}),
                                       ("point-line", {"marker": "None"}),
                                       ("point-line", {"linestyle": ""}),
                                       ("scatter", {"linestyle": "--"}),
                                       ("line", {"line_width": 0}),
                                       ("point-line", {"marker_size": 21}),
                                       ("line", {"unknown": 2})])
def test_invalid_style_cannot_silently_change_semantics(kind, style):
    with pytest.raises(ValueError):
        render_plot({"x": [1, 2], "y": [1, 2]}, kind=kind, x="x", y="y", series_styles={"": style})


def test_cli_error_panel_records_formula_and_interpolation(tmp_path):
    data_path = tmp_path / "input.csv"
    mixed_data().to_csv(data_path, index=False)
    result = subprocess.run([sys.executable, str(TEMPLATE), "--input", str(data_path), "--kind", "line",
                             "--x", "x", "--y", "y", "--group", "series", "--size", "double",
                             "--error-reference", "Theory", "--error-definition", "signed",
                             "--error-ylabel", "Signed error in y (m/s)",
                             "--output", str(tmp_path / "errors")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((tmp_path / "errors_metadata.json").read_text())
    assert metadata["error"]["formula"] == "y - reference"
    assert metadata["error"]["interpolation"] == "none"
    assert all(record["method"] == "exact" for record in metadata["error"]["comparisons"])


def test_error_ylabel_and_dpi_do_not_change_sizes(tmp_path):
    options = {"kind": "point-line", "x": "x", "y": "y", "group": "series", "size": "double",
               "error": {"reference": "Theory", "definition": "signed", "ylabel": "Error (m/s)"}}
    first, axes, _ = render_plot(mixed_data(), **options, dpi=150, output=tmp_path / "low")
    second, other_axes, _ = render_plot(mixed_data(), **options, dpi=600, output=tmp_path / "high")
    assert first.scientific_error_axes.get_ylabel() == "Error (m/s)"
    assert [line.get_markersize() for line in axes.lines] == [line.get_markersize() for line in other_axes.lines]
    assert [line.get_linewidth() for line in axes.lines] == [line.get_linewidth() for line in other_axes.lines]


def test_dns_optimization_inputs_preserve_both_original_grids():
    module_spec = importlib.util.spec_from_file_location("optimization_cases", ROOT / "examples/validate_cfd_optimization.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    cases, provenance = module.build_cases()
    staggered = next(case["frame"] for case in cases if case["id"] == "04_dns_staggered")
    reference = module.load_module(ROOT / "examples/test_cfd_plotting.py", "raw_reader")
    raw = ROOT / "data/cfd_validation/raw/Poi395_4th_D.dat"
    mean = reference.read_dns_table(raw, "u_mean")
    shear = reference.read_dns_table(raw, "-uv+")
    assert not np.array_equal(mean["y+"], shear["y+"])
    for label, table, column in (("uu+ (mean grid)", mean, "uu+"), ("ww+ (mean grid)", mean, "ww+"),
                                 ("vv+ (shear grid)", shear, "vv+"), ("-uv+ (shear grid)", shear, "-uv+")):
        subset = staggered.loc[staggered["series"] == label]
        np.testing.assert_array_equal(subset["x"], table["y+"])
        np.testing.assert_array_equal(subset["y"], table[column])
    assert all(entry["sha256"] == module.digest(ROOT / "data/cfd_validation/raw" / entry["file"]) for entry in provenance)


def test_delivered_bundle_replays_without_network_or_raw_dns():
    module_spec = importlib.util.spec_from_file_location("optimization_replay", ROOT / "examples/validate_cfd_optimization.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    result = module.verify_replay(ROOT / "figures/cfd_optimization")
    assert result["all_files_byte_identical"]
    assert result["png_count"] == 17
    assert not result["raw_dns_copied"]
