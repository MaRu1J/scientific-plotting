import copy
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.collections import LineCollection
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))

from plot_template import CATEGORICAL_COLORS, render_multipanel, render_plot, run_cli


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.fixture
def observations():
    return pd.DataFrame({"x": [3, 1, 2, 3, 1, 2], "y": [3.1, 1.1, 2.1, 3, 1, 2],
                         "method": ["A", "A", "A", "B", "B", "B"], "sd": [0.05] * 6})


def _render(data, **kwargs):
    return render_plot(data, kind=kwargs.pop("kind", "point-line"), x="x", y="y",
                       group="method", **kwargs)


def _identities(axes):
    return {artist.get_label(): artist._scientific_identity
            for artist in (*axes.lines, *axes.collections) if hasattr(artist, "_scientific_identity")}


def test_registry_survives_reordering_subsets_and_overrides(observations):
    registry = {"B": {}, "A": {}, "unused": {"marker": "D"}}
    original = copy.deepcopy(registry)
    _, first, _ = _render(observations, style_registry=registry)
    _, reversed_axes, _ = _render(observations.iloc[::-1], style_registry=registry)
    _, subset, _ = _render(observations[observations.method == "A"], style_registry=registry)
    assert _identities(first) == _identities(reversed_axes)
    assert _identities(first)["A"] == _identities(subset)["A"]
    _, override, _ = _render(observations, style_registry=registry,
                            series_styles={"A": {"color": "#C4453A", "marker": "D"}})
    assert _identities(override)["A"][1:] == ("#c4453a", "--", "D")
    assert registry == original


@pytest.mark.parametrize("kind", ["line", "scatter", "point-line", "mixed"])
def test_registry_preserves_native_semantics(observations, kind):
    options = {"series_styles": {"A": {"kind": "line"}, "B": {"kind": "scatter"}}} if kind == "mixed" else {}
    _, axes, _ = _render(observations, kind=kind, style_registry={"A": {}, "B": {}}, **options)
    if kind == "line":
        assert all(line.get_marker() == "None" for line in axes.lines)
    elif kind == "scatter":
        assert not axes.lines and len(axes.collections) == 2
    elif kind == "mixed":
        assert len(axes.lines) == len(axes.collections) == 1
    else:
        assert all(line.get_marker() != "None" for line in axes.lines)


def test_unregistered_series_warns_and_uses_original_fallback(observations):
    with pytest.warns(UserWarning, match="Unregistered.*B"):
        _, axes, _ = _render(observations, style_registry={"A": {}})
    assert axes.lines[1].get_color() == CATEGORICAL_COLORS[1]
    with pytest.raises(ValueError, match="kinds stay per figure"):
        _render(observations, style_registry={"A": {"kind": "scatter"}})
    with pytest.raises(ValueError, match="explicit kind"):
        _render(observations, kind="mixed", style_registry={"A": {}, "B": {}})


def test_registry_shared_legend_with_reordered_and_partial_panels(observations):
    figure, axes, _ = render_multipanel([
        {"data": observations, "kind": "point-line", "x": "x", "y": "y", "group": "method"},
        {"data": observations.iloc[::-1], "kind": "point-line", "x": "x", "y": "y", "group": "method"},
        {"data": observations[observations.method == "B"], "kind": "point-line", "x": "x", "y": "y", "group": "method"},
    ], ncols=2, style_registry={"A": {}, "B": {}})
    assert len(figure.legends) == 1
    assert _identities(axes[0]) == _identities(axes[1])
    assert _identities(axes[0])["B"] == _identities(axes[2])["B"]


def test_shared_legend_detects_different_explicit_dash_patterns():
    panels = [{"data": {"x": [1, 2], "y": [1, 2], "method": ["A", "A"]},
               "kind": "line", "x": "x", "y": "y", "group": "method",
               "series_styles": {"A": {"linestyle": pattern}}}
              for pattern in ([0, [5, 2]], [0, [2, 1]])]
    with pytest.raises(ValueError, match="different styles"):
        render_multipanel(panels, style_registry={"A": {}})


def test_power_guide_uses_explicit_formula_without_changing_data():
    data = pd.DataFrame({"x": [0.2, 0.05, 0.1], "y": [0.04, 0.0025, 0.01]})
    original = data.copy(deep=True)
    guide = {"kind": "power", "order": 2, "anchor": [0.1, 0.005], "range": [0.05, 0.2], "label": "O(h^2)"}
    figure, axes, _ = render_plot(data, kind="point-line", x="x", y="y", xscale="log", yscale="log",
                                  reference_guides=[guide])
    pd.testing.assert_frame_equal(data, original)
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), original.x)
    reference = axes.lines[1]
    np.testing.assert_allclose(reference.get_ydata(), 0.005 * (reference.get_xdata() / 0.1) ** 2)
    assert reference.get_linewidth() == 0.8
    assert figure.scientific_metadata["reference_guides"] == [guide]


@pytest.mark.parametrize("guides,scales", [
    ([{"kind": "constant", "axis": "y", "value": 0, "label": "zero"}], {"yscale": "log"}),
    ([{"kind": "power", "order": 2, "anchor": [1, 1], "range": [1, 2], "label": "p=2"}], {}),
    ([{"kind": "power", "order": 2, "anchor": [0, 1], "range": [1, 2], "label": "p=2"}], {"xscale": "log", "yscale": "log"}),
    ([{"kind": "constant", "axis": "y", "value": float("nan"), "label": "value"}], {}),
    ([{"kind": "constant", "axis": "y", "value": 1}], {}),
])
def test_invalid_reference_guides_are_rejected(guides, scales):
    with pytest.raises(ValueError):
        render_plot({"x": [1, 2], "y": [2, 3]}, kind="line", x="x", y="y", reference_guides=guides, **scales)


def test_constant_guides_do_not_change_data_semantics(observations):
    guides = [{"kind": "constant", "axis": "y", "value": 2, "label": "Theory"},
              {"kind": "constant", "axis": "x", "value": 1.5, "label": "Explicit event"}]
    _, axes, _ = _render(observations, reference_guides=guides)
    np.testing.assert_array_equal(axes.lines[-2].get_ydata(), [2, 2])
    np.testing.assert_array_equal(axes.lines[-1].get_xdata(), [1.5, 1.5])
    assert len(axes.lines[0].get_xdata()) == 3


@pytest.mark.parametrize("kind", ["line", "point-line", "scatter", "mixed"])
def test_inset_reuses_all_points_styles_errors_and_main_limits(observations, kind):
    options = {"kind": kind, "size": "double", "line_width": 1.2} if kind != "scatter" else {"kind": kind, "size": "double"}
    if kind == "mixed":
        options["series_styles"] = {"A": {"kind": "point-line"}, "B": {"kind": "scatter"}}
    error_bars = {"y": "sd", "definition": "Supplied synthetic SD, n=4"}
    _, baseline, _ = _render(observations, error_bars=error_bars, **options)
    limits = baseline.get_xlim(), baseline.get_ylim()
    _, axes, _ = _render(observations, error_bars=error_bars,
                        inset={"xlim": [1, 2], "ylim": [0.9, 2.3], "bounds": [0.1, 0.57, 0.36, 0.34]}, **options)
    zoom = axes.scientific_inset_axes
    np.testing.assert_allclose(axes.get_xlim(), limits[0])
    np.testing.assert_allclose(axes.get_ylim(), limits[1])
    assert zoom.get_legend() is None
    for source, target in zip(axes.lines, zoom.lines):
        np.testing.assert_array_equal(source.get_xdata(), target.get_xdata())
        np.testing.assert_array_equal(source.get_ydata(), target.get_ydata())
        np.testing.assert_allclose(to_rgba(source.get_color()), to_rgba(target.get_color()))
        assert source.get_marker() == target.get_marker()
        assert source.get_markersize() == target.get_markersize()
        assert source.get_linewidth() == target.get_linewidth()
    assert len(zoom.collections) == len(axes.collections)
    for source, target in zip(axes.collections, zoom.collections):
        if isinstance(source, LineCollection):
            np.testing.assert_allclose(source.get_segments(), target.get_segments())
        else:
            np.testing.assert_array_equal(source.get_offsets(), target.get_offsets())
            np.testing.assert_array_equal(source.get_sizes(), target.get_sizes())
    assert all(label.startswith("_") for label in zoom.get_legend_handles_labels()[1])
    assert len(axes.scientific_inset_connectors) == 3
    assert axes.scientific_inset_connectors[0] in axes.patches
    assert all(connector in zoom.patches for connector in axes.scientific_inset_connectors[1:])


def test_inset_and_reference_error_panel_are_independent(observations):
    figure, axes, _ = _render(observations, error={"reference": "B", "definition": "signed"},
                              inset={"xlim": [1, 2], "ylim": [1, 2.2], "bounds": [0.15, 0.6, 0.3, 0.3]})
    assert figure.scientific_error_axes is not axes.scientific_inset_axes
    assert len(figure.scientific_error_axes.lines) == 1
    assert len(axes.scientific_inset_axes.lines) == 2


@pytest.mark.parametrize("spec", [
    {"xlim": [1, 2], "ylim": [1, 2], "bounds": [0.8, 0.5, 0.4, 0.4]},
    {"xlim": [2, 1], "ylim": [1, 2], "bounds": [0.5, 0.5, 0.4, 0.4]},
    {"xlim": [0, 1], "ylim": [1, 2], "bounds": [0.5, 0.5, 0.4, 0.4]},
])
def test_invalid_inset_specs_are_rejected(spec):
    with pytest.raises(ValueError):
        render_plot({"x": [1, 2], "y": [2, 3]}, kind="line", x="x", y="y", xscale="log", inset=spec)


def _curve_panel(identifier):
    return {"id": identifier, "data": {"x": [1, 2, 3], "y": [1, 2, 1]}, "kind": "line", "x": "x", "y": "y"}


def test_spanning_layout_preserves_panel_order_shared_axes_and_letters():
    panels = [_curve_panel("bottom"), _curve_panel("top")]
    figure, axes, _ = render_multipanel(panels, layout=[["top", "top"], ["bottom", None]], sharex=True)
    assert [text.get_text() for panel in axes for text in panel.texts] == ["(a)", "(b)"]
    assert axes[0].get_position().y0 < axes[1].get_position().y0
    assert axes[1].get_position().width > 1.5 * axes[0].get_position().width
    assert axes[0].get_shared_x_axes().joined(*axes)
    assert figure.scientific_metadata["layout"] == [["top", "top"], ["bottom", None]]


@pytest.mark.parametrize("layout", [
    [["A", "A"], ["A", "B"]],
    [["A", None], [None, "A"], ["B", None]],
    [["A"], ["B", None]],
    [["A", "unknown"]],
    [["A", None]],
    [["A", 1], ["B", None]],
])
def test_invalid_layouts_are_rejected(layout):
    with pytest.raises(ValueError, match="layout|rectangle"):
        render_multipanel([_curve_panel("A"), _curve_panel("B")], layout=layout)


def test_layout_requires_ids_and_rejects_ncols():
    with pytest.raises(ValueError, match="unique"):
        render_multipanel([_curve_panel("A"), _curve_panel("A")], layout=[["A"]])
    with pytest.raises(ValueError, match="omit ncols"):
        render_multipanel([_curve_panel("A")], layout=[["A"]], ncols=1)


def _heatmap_panels():
    return [{"id": "A", "data": np.array([[1., 2.], [3., 4.]]), "kind": "heatmap", "quantity": "pressure", "unit": "Pa"},
            {"id": "B", "data": np.array([[4., 3.], [2., 1.]]), "kind": "heatmap", "quantity": "pressure", "unit": "Pa"}]


def test_heatmap_limits_and_shared_colorbar_preserve_numeric_values():
    panels = _heatmap_panels()
    originals = [panel["data"].copy() for panel in panels]
    figure, axes, _ = render_multipanel(panels, shared_colorbar={"vmin": 0, "vmax": 5, "label": "Pressure (Pa)"})
    assert len(figure.axes) == 3
    assert figure.axes[0].get_ylabel() == "Pressure (Pa)"
    for panel, original, axis in zip(panels, originals, axes):
        np.testing.assert_array_equal(panel["data"], original)
        np.testing.assert_array_equal(axis.images[0].get_array(), original)
        assert axis.images[0].get_clim() == (0, 5)
        assert axis.images[0].get_cmap().name == "cividis"
    _, standalone, _ = render_plot(originals[0], kind="heatmap", heatmap_scale={"vmin": 0, "vmax": 10})
    assert standalone.images[0].get_clim() == (0, 10)


@pytest.mark.parametrize("change", ["quantity", "unit", "missing", "limits"])
def test_shared_colorbar_rejects_semantic_or_scale_conflicts(change):
    panels = _heatmap_panels()
    if change in ("quantity", "unit"):
        panels[1][change] = "different"
    elif change == "missing":
        del panels[1]["unit"]
    else:
        panels[1]["heatmap_scale"] = {"vmin": 0, "vmax": 8}
    with pytest.raises(ValueError, match="quantity|unit|conflicts"):
        render_multipanel(panels, shared_colorbar={"vmin": 0, "vmax": 5, "label": "Pressure (Pa)"})


@pytest.mark.parametrize("scale", [{"vmin": 1, "vmax": 1}, {"vmin": 1}, {"vmin": 0, "vmax": float("inf")}])
def test_invalid_heatmap_limits_are_rejected(scale):
    with pytest.raises(ValueError, match="heatmap_scale"):
        render_plot(np.ones((2, 2)), kind="heatmap", heatmap_scale=scale)


def test_multipanel_inset_matches_final_style_after_layout(observations):
    panels = [{"data": observations, "kind": "point-line", "x": "x", "y": "y", "group": "method",
               "inset": {"xlim": [1, 2], "ylim": [1, 2.2], "bounds": [0.1, 0.55, 0.32, 0.3]}}] * 2
    _, axes, _ = render_multipanel(panels, style_registry={"A": {}, "B": {}})
    for panel in axes:
        for source, target in zip(panel.lines, panel.scientific_inset_axes.lines):
            assert source.get_linewidth() == target.get_linewidth()
            assert source.get_markersize() == target.get_markersize()


def test_log_inset_copies_asymmetric_x_and_y_whiskers(observations):
    errors = {"x_lower": 0.01, "x_upper": 0.02, "y_lower": 0.03, "y_upper": 0.04,
              "definition": "Supplied synthetic bounds in axis units"}
    _, axes, _ = _render(observations, xscale="log", yscale="log", error_bars=errors,
                        inset={"xlim": [1, 2], "ylim": [1, 2.2], "bounds": [0.1, 0.55, 0.3, 0.3]})
    zoom = axes.scientific_inset_axes
    assert zoom.get_xscale() == zoom.get_yscale() == "log"
    assert len(zoom.lines) == len(axes.lines)
    for source, target in zip(axes.collections, zoom.collections):
        np.testing.assert_allclose(source.get_segments(), target.get_segments())
        np.testing.assert_allclose(source.get_linewidths(), target.get_linewidths())


def test_spanning_shared_y_axis_remains_linked():
    _, axes, _ = render_multipanel([_curve_panel("left"), _curve_panel("right")],
                                   layout=[["left", "right"], ["left", "right"]], sharey=True)
    assert axes[0].get_shared_y_axes().joined(*axes)
    assert not any(label.get_visible() for label in axes[1].get_yticklabels())


def test_shared_heatmaps_coexist_with_a_spanning_curve(observations):
    panels = _heatmap_panels() + [dict(_curve_panel("curve"), data=observations)]
    figure, axes, _ = render_multipanel(panels, layout=[["curve", "curve"], ["A", "B"]],
                                       shared_colorbar={"vmin": 0, "vmax": 5, "label": "Pressure (Pa)"})
    assert len(figure.axes) == 4
    assert len(axes[2].lines) == 1
    assert axes[2].get_position().width > axes[0].get_position().width


@pytest.mark.parametrize("format_name", ["png", "svg", "pdf", "eps"])
def test_new_features_do_not_enable_forbidden_formats(tmp_path, observations, format_name):
    with pytest.raises(ValueError, match="Only JPEG and TIFF"):
        _render(observations, style_registry={"A": {}, "B": {}}, output=tmp_path / "figure", formats=[format_name])
    assert not list(tmp_path.iterdir())


def test_tiff_remains_explicit_with_new_features(tmp_path, observations):
    _, _, paths = _render(observations, style_registry={"A": {}, "B": {}}, output=tmp_path / "figure",
                          formats=["tiff"], dpi=120)
    assert paths == [tmp_path / "figure.tiff"]
    assert not (tmp_path / "figure.jpg").exists()


def test_cli_also_pins_explicit_null_configurations(tmp_path, observations):
    source = tmp_path / "input.csv"
    observations.to_csv(source, index=False)
    null_config = tmp_path / "null.json"
    null_config.write_text("null", encoding="utf-8")
    arguments = ["--input", str(source), "--output", str(tmp_path / "null_figure"), "--kind", "line", "--x", "x", "--y", "y"]
    for flag in ("--series-config", "--style-registry", "--reference-config", "--inset-config"):
        arguments.extend([flag, str(null_config)])
    run_cli(arguments)
    for suffix in ("series", "registry", "references", "inset"):
        path = tmp_path / f"null_figure_{suffix}.json"
        assert path.exists() and json.loads(path.read_text(encoding="utf-8")) is None


@pytest.mark.parametrize("equals_arguments", [False, True])
def test_cli_pins_all_new_configs_for_replay(tmp_path, observations, equals_arguments):
    source = tmp_path / "input.csv"
    observations.to_csv(source, index=False)
    configurations = {
        "style-registry": {"A": {}, "B": {}},
        "series-config": {"A": {"line_width": 1.1}},
        "reference-config": [{"kind": "constant", "axis": "y", "value": 2, "label": "Theory"}],
        "inset-config": {"xlim": [1, 2], "ylim": [1, 2.2], "bounds": [0.1, 0.55, 0.3, 0.3]},
    }
    arguments = ["--input", str(source), "--output", str(tmp_path / "figure"), "--kind", "point-line",
                 "--x", "x", "--y", "y", "--group", "method", "--size", "double"]
    for flag, payload in configurations.items():
        path = tmp_path / f"original-{flag}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        arguments.extend([f"--{flag}", str(path)])
    if equals_arguments:
        arguments = [f"{flag}={value}" for flag, value in zip(arguments[::2], arguments[1::2])]
    paths = run_cli(arguments)
    assert paths == [tmp_path / "figure.jpg"]
    assert not list(tmp_path.glob("*.tiff"))
    for flag in configurations:
        (tmp_path / f"original-{flag}.json").unlink()
    for suffix in ("registry", "series", "references", "inset"):
        assert (tmp_path / f"figure_{suffix}.json").exists()
    (tmp_path / "figure.jpg").unlink()
    subprocess.run([sys.executable, str(tmp_path / "figure_reproduce.py")], check=True, capture_output=True)
    assert paths[0].exists()
