import copy
import json
import os
from pathlib import Path
import sys

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))

from plot_template import CATEGORICAL_COLORS, PALETTES, _grayscale_findings, render_multipanel, render_plot, replay_bundle, review_figure, run_cli


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.fixture
def observations():
    return pd.DataFrame({"x": [3, 1, 2, 3, 1, 2], "y": [3, 1, 2, 4, 2, 3],
                         "method": ["A"] * 3 + ["B"] * 3})


def render(data, **kwargs):
    return render_plot(data, kind=kwargs.pop("kind", "point-line"), x="x", y="y", group="method", **kwargs)


@pytest.mark.parametrize("palette", ["classic", "jewel", "muted"])
def test_palettes_keep_data_and_explicit_overrides(observations, palette):
    original = observations.copy(deep=True)
    figure, axes, _ = render(observations, palette=palette, series_styles={"B": {"color": "#654321"}})
    assert axes.lines[0].get_color() == PALETTES[palette][0]
    assert axes.lines[1].get_color() == "#654321"
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), [3, 1, 2])
    pd.testing.assert_frame_equal(observations, original)
    assert figure.scientific_metadata["palette"] == palette


def test_default_palette_is_unchanged(observations):
    _, axes, _ = render(observations)
    assert [line.get_color() for line in axes.lines] == list(CATEGORICAL_COLORS[:2])


@pytest.mark.parametrize("palette", ["jewel", "muted", "focus"])
def test_named_palettes_refuse_ordered_groups(observations, palette):
    observations["method"] = [1] * 3 + [2] * 3
    with pytest.raises(ValueError, match="ordered groups"):
        render(observations, palette=palette, **({"focus": "1"} if palette == "focus" else {}))


def test_focus_requires_explicit_existing_identity(observations):
    for options in ({"palette": "focus"}, {"focus": "A"}, {"palette": "focus", "focus": "missing"}):
        with pytest.raises(ValueError, match="focus"):
            render(observations, **options)
    _, axes, _ = render(observations, palette="focus", focus="B")
    assert [line.get_color() for line in axes.lines] == [PALETTES["focus"][1], PALETTES["focus"][0]]


def test_registry_named_palette_survives_missing_categories(observations):
    registry = {"A": {}, "B": {}}
    figure, axes, _ = render_multipanel([
        {"data": observations, "kind": "point-line", "x": "x", "y": "y", "group": "method"},
        {"data": observations[observations.method == "B"], "kind": "point-line", "x": "x", "y": "y", "group": "method"},
    ], palette="jewel", style_registry=registry, size="double")
    assert axes[0].lines[1].get_color() == axes[1].lines[0].get_color() == PALETTES["jewel"][1]
    assert len(figure.legends) == 1


def test_visual_decisions_keep_original_panel_numbers(observations, tmp_path):
    panel = {"data": observations, "kind": "point-line", "x": "x", "y": "y", "group": "method"}
    figure, _, _ = render_multipanel([panel, {**panel, "palette": "jewel"}], legend="each", size="double",
                                    output=tmp_path / "figure", report=True)
    assert figure.scientific_report["visual_decisions"][0]["panel"] == 2


@pytest.mark.parametrize("kind", ["scatter", "bar", "violin"])
def test_named_palettes_reach_other_kinds(observations, kind):
    if kind == "violin":
        _, axes, _ = render_plot(observations, kind=kind, x="method", y="y", palette="muted")
        assert to_hex(axes.collections[0].get_facecolor()[0]) == PALETTES["muted"][0].lower()
    else:
        _, axes, _ = render(observations, kind=kind, palette="jewel")
        artist = axes.collections[0] if kind == "scatter" else axes.patches[0]
        color = artist.get_facecolor()[0] if kind == "scatter" else artist.get_facecolor()
        assert to_hex(color) == PALETTES["jewel"][0].lower()


def test_heatmap_refuses_categorical_palette():
    with pytest.raises(ValueError, match="heatmap"):
        render_plot(np.ones((2, 2)), kind="heatmap", palette="jewel")


def test_palette_capacity_is_not_silently_cycled():
    data = {"x": list(range(9)), "y": list(range(9)), "method": list("ABCDEFGHI")}
    with pytest.raises(ValueError, match="capacity"):
        render(data, palette="jewel")


def test_palette_cli_and_bundle_replay(observations, tmp_path):
    source = tmp_path / "data.csv"
    observations.to_csv(source, index=False)
    run_cli(["--input", str(source), "--kind", "point-line", "--x", "x", "--y", "y", "--group", "method",
             "--palette", "jewel", "--output", str(tmp_path / "figure"),
             "--bundle", str(tmp_path / "bundle"), "--include-data"])
    recipe = json.loads((tmp_path / "bundle" / "recipe.json").read_text())
    assert recipe["options"]["palette"] == "jewel"
    _, axes, _ = replay_bundle(tmp_path / "bundle", ["--output-dir", str(tmp_path / "replayed")])
    assert axes.lines[0].get_color() == PALETTES["jewel"][0]


@pytest.fixture
def semantic_data():
    return pd.DataFrame({"x": [3, 1, 2] * 4, "y": [1.3, 1.1, 1.2, 1.5, 1.2, 1.4, 90, 110, 100, 80, 100, 90],
                         "method": np.repeat(["A height", "B height", "A angle", "B angle"], 3), "sd": [0.01] * 12})


@pytest.fixture
def encoding():
    return {"categories": {"A": {}, "B": {}},
            "metrics": {"Height": {"fillstyle": "full"}, "Angle": {"fillstyle": "none", "linestyle": "--"}},
            "series": {"A height": {"category": "A", "metric": "Height"},
                       "B height": {"category": "B", "metric": "Height"},
                       "A angle": {"category": "A", "metric": "Angle"},
                       "B angle": {"category": "B", "metric": "Angle"}},
            "category_label": "Material", "metric_label": "Quantity", "reason": "Compare material responses"}


def test_semantic_roles_preserve_identity_and_factor_legend(semantic_data, encoding):
    original = copy.deepcopy(encoding)
    figure, axes, _ = render(semantic_data, encoding=encoding, palette="jewel", size="double")
    assert axes.lines[0].get_color() == axes.lines[2].get_color()
    assert axes.lines[0].get_marker() == axes.lines[2].get_marker()
    assert axes.lines[2].get_fillstyle() == "none"
    assert axes.lines[2].get_markeredgecolor() == axes.lines[0].get_color()
    assert len(axes.get_legend().get_texts()) == 4
    assert {text.get_text() for text in axes.get_legend().get_texts()} == {
        "Material: A", "Material: B", "Quantity: Height", "Quantity: Angle"}
    assert figure.scientific_metadata["encoding"]["reason"] == encoding["reason"]
    assert encoding == original


def test_semantic_subset_keeps_category_style_and_no_fake_pairs(semantic_data, encoding):
    subset = semantic_data[semantic_data.method == "B angle"]
    figure, axes, _ = render(subset, encoding=encoding, palette="jewel")
    assert axes.lines[0].get_color() == PALETTES["jewel"][1]
    assert axes.lines[0].get_marker() == "s"
    assert len(axes.lines[0].get_ydata()) == 3
    assert len(figure.scientific_metadata["encoding"]["observed"]) == 1


def test_hollow_markers_survive_inset_density_and_uncertainty(semantic_data, encoding):
    subset = semantic_data[semantic_data.method == "A angle"]
    figure, axes, _ = render(subset, encoding=encoding, palette="jewel", error_bars={"y": "sd", "definition": "Supplied SD"},
                              inset={"xlim": [1, 3], "ylim": [85, 115], "bounds": [0.45, 0.1, 0.4, 0.35]}, size="double")
    source = next(line for line in axes.lines if hasattr(line, "_scientific_identity"))
    target = next(line for line in axes.scientific_inset_axes.lines if not getattr(line, "_scientific_errorbar", False))
    assert source.get_fillstyle() == target.get_fillstyle() == "none"
    assert source.get_markeredgecolor() == target.get_markeredgecolor()
    assert figure.scientific_metadata["error_bars"]["definition"] == "Supplied SD"


def test_hollow_scatter_supports_uncertainty(semantic_data, encoding):
    subset = semantic_data[semantic_data.method == "A angle"]
    _, axes, _ = render(subset, kind="scatter", encoding=encoding,
                       error_bars={"y": "sd", "definition": "Supplied SD"})
    scatter = next(collection for collection in axes.collections if hasattr(collection, "_scientific_identity"))
    assert len(scatter.get_facecolor()) == 0
    assert to_hex(scatter.get_edgecolor()[0]) == CATEGORICAL_COLORS[0].lower()
    assert len(scatter.get_offsets()) == 3


def test_semantic_focus_uses_category_not_combined_label(semantic_data, encoding):
    _, axes, _ = render(semantic_data, encoding=encoding, palette="focus", focus="B", size="double")
    assert axes.lines[1].get_color() == axes.lines[3].get_color() == PALETTES["focus"][0]
    with pytest.raises(ValueError, match="declared category"):
        render(semantic_data, encoding=encoding, palette="focus", focus="B angle")


def test_semantic_conflicting_overrides_refuse_misleading_factorization(semantic_data, encoding):
    with pytest.raises(ValueError, match="cannot be factorized"):
        render(semantic_data, encoding=encoding, series_styles={"A angle": {"color": "black"}})
    encoding["legend"] = "combined"
    _, axes, _ = render(semantic_data, encoding=encoding, series_styles={"A angle": {"color": "black"}})
    assert axes.lines[2].get_color() == "black"


def test_semantic_registry_explicit_fields_override_roles_without_default_leak(semantic_data, encoding):
    registry = {label: {} for label in encoding["series"]}
    registry["A height"] = {"color": "black"}
    registry["A angle"] = {"color": "black"}
    figure, axes, _ = render(semantic_data, encoding=encoding, palette="jewel", style_registry=registry, size="double")
    assert axes.lines[0].get_color() == axes.lines[2].get_color() == "black"
    assert axes.lines[1].get_color() == PALETTES["jewel"][1]
    assert axes.lines[2].get_fillstyle() == "none"
    assert figure.scientific_metadata["encoding"]["resolved_series"]["A height"]["color"] == "#000000"


@pytest.mark.parametrize("mutation", ["unknown_series", "unknown_role", "ordered", "bad_fill", "bad_key"])
def test_invalid_semantic_roles_are_refused(semantic_data, encoding, mutation):
    options = {}
    if mutation == "unknown_series":
        del encoding["series"]["A angle"]
    elif mutation == "unknown_role":
        encoding["series"]["A angle"]["metric"] = "Missing"
    elif mutation == "ordered":
        options["group_kind"] = "ordered"
    elif mutation == "bad_fill":
        encoding["metrics"]["Angle"]["fillstyle"] = "left"
    else:
        encoding["categories"]["A"]["linewidth"] = 2
    with pytest.raises(ValueError):
        render(semantic_data, encoding=encoding, **options)


def test_semantic_shared_legend_and_bundle(semantic_data, encoding, tmp_path):
    panel = {"data": semantic_data, "kind": "point-line", "x": "x", "y": "y", "group": "method"}
    second = {**panel, "data": semantic_data[semantic_data.method == "B angle"]}
    figure, axes, _ = render_multipanel([panel, second], encoding=encoding, palette="jewel", size="double",
                                       output=tmp_path / "figure", bundle=tmp_path / "bundle", include_data=True)
    assert len(figure.legends[0].get_texts()) == 4
    replay, restored, _ = replay_bundle(tmp_path / "bundle", ["--output-dir", str(tmp_path / "replayed")])
    assert restored[1].lines[0].get_fillstyle() == "none"
    assert restored[1].lines[0].get_color() == axes[1].lines[0].get_color()
    assert len(replay.legends[0].get_texts()) == 4


@pytest.fixture
def secondary_y():
    return {"series": ["A angle", "B angle"], "label": "Contact angle (deg)", "quantity": "contact angle", "unit": "deg",
            "limits": [60, 130], "primary": {"quantity": "relative height", "unit": "-", "limits": [0.9, 1.7]},
            "reason": "Compare synchronized responses within a compact panel; limits cover both measurements"}


def test_dual_axes_preserve_series_grids_roles_limits_and_single_grid(semantic_data, encoding, secondary_y):
    source = semantic_data.copy(deep=True)
    source["x"] = source["x"].astype(float)
    source.loc[source.method == "A angle", "x"] = [2.8, 1.2, 2.1]
    figure, axes, _ = render(source, encoding=encoding, secondary_y=secondary_y, ylabel="Relative height (-)",
                              xlabel="Field (kV/cm)", palette="jewel", size="double")
    right = axes.scientific_secondary_axes
    assert len(axes.lines) == len(right.lines) == 2
    np.testing.assert_array_equal(right.lines[0].get_xdata(), [2.8, 1.2, 2.1])
    np.testing.assert_array_equal(right.lines[0].get_ydata(), [90, 110, 100])
    assert axes.get_ylim() == (0.9, 1.7)
    assert right.get_ylim() == (60, 130)
    assert right.get_ylabel() == "Contact angle (deg)"
    assert all(not line.get_visible() for line in right.get_xgridlines() + right.get_ygridlines())
    assert right.lines[0].get_color() == axes.lines[0].get_color()
    assert right.lines[0].get_fillstyle() == "none"
    assert len(right.get_legend().get_texts()) == 4
    assert figure.scientific_metadata["series"]["A angle"]["axis"] == "right"
    assert figure.scientific_metadata["series"]["A height"]["axis"] == "left"
    assert any(item["rule"] == "dual_axis" for item in review_figure(figure))


def test_dual_axis_uncertainty_uses_correct_axis_and_report(semantic_data, encoding, secondary_y, tmp_path):
    figure, axes, _ = render(semantic_data, encoding=encoding, secondary_y=secondary_y, ylabel="Relative height (-)",
                              error_bars={"y": "sd", "definition": "Supplied SD, distinct axis units"}, size="double",
                              output=tmp_path / "figure", report=True)
    records = figure.scientific_metadata["error_bars"]["series"]
    assert [record["axis"] for record in records] == ["left", "left", "right", "right"]
    assert len(axes.containers) == len(axes.scientific_secondary_axes.containers) == 2
    assert figure.scientific_report["visual_decisions"][0]["secondary_y"]["reason"] == secondary_y["reason"]


@pytest.mark.parametrize("mutation", ["missing_reason", "no_units", "unknown_series", "all_series", "duplicate",
                                    "same_quantity", "reversed_limits", "excluded_data", "split_metric", "no_ylabel"])
def test_dual_axis_invalid_semantics_are_refused(semantic_data, encoding, secondary_y, mutation):
    options = {"ylabel": "Relative height (-)"}
    if mutation == "missing_reason":
        del secondary_y["reason"]
    elif mutation == "no_units":
        secondary_y["unit"] = ""
    elif mutation == "unknown_series":
        secondary_y["series"] = ["missing"]
    elif mutation == "all_series":
        secondary_y["series"] = list(encoding["series"])
    elif mutation == "duplicate":
        secondary_y["series"] = ["A angle", "A angle"]
    elif mutation == "same_quantity":
        secondary_y["quantity"] = "relative height"
    elif mutation == "reversed_limits":
        secondary_y["limits"] = [130, 60]
    elif mutation == "excluded_data":
        secondary_y["limits"] = [95, 130]
    elif mutation == "split_metric":
        secondary_y["series"] = ["A angle"]
    else:
        options = {}
    with pytest.raises(ValueError):
        render(semantic_data, encoding=encoding, secondary_y=secondary_y, **options)


@pytest.mark.parametrize("option", ["inset", "reference_guides", "error"])
def test_dual_axis_unsupported_combinations_fail_explicitly(semantic_data, secondary_y, option):
    extras = {"inset": {"xlim": [1, 2], "ylim": [1, 2], "bounds": [0.1, 0.1, 0.3, 0.3]},
              "reference_guides": [{"kind": "constant", "axis": "y", "value": 1.2, "label": "Guide"}],
              "error": {"reference": "A height", "definition": "signed"}}
    with pytest.raises(ValueError, match="cannot yet combine"):
        render(semantic_data, secondary_y=secondary_y, ylabel="Relative height (-)", **{option: extras[option]})


def test_dual_axis_log_endpoint_validation_is_per_axis(semantic_data, secondary_y):
    data = semantic_data.copy(deep=True)
    data.loc[data.method.str.endswith("angle"), "y"] *= -1
    secondary_y["limits"] = [-130, -60]
    _, axes, _ = render(data, secondary_y=secondary_y, yscale="log", ylabel="Relative height (-)", size="double")
    assert axes.get_yscale() == "log"
    assert axes.scientific_secondary_axes.get_yscale() == "linear"
    data.loc[data.method == "A height", "y"] = 0.005
    secondary_y["primary"]["limits"] = [0.001, 1.7]
    with pytest.raises(ValueError, match="non-positive"):
        render(data, secondary_y=secondary_y, yscale="log", ylabel="Relative height (-)",
               error_bars={"y": "sd", "definition": "Supplied SD"})


def test_dual_axis_gray_review_compares_both_axes(semantic_data, secondary_y):
    styles = {label: {"color": "black", "marker": "o", "linestyle": "-"} for label in secondary_y["series"]}
    styles.update({label: {"color": "black", "marker": "o", "linestyle": "-"} for label in ["A height", "B height"]})
    figure, _, _ = render(semantic_data, secondary_y=secondary_y, ylabel="Relative height (-)", series_styles=styles,
                          size="double")
    comparisons = [item["measured"]["series"] for item in _grayscale_findings(figure)]
    assert ["A height", "A angle"] in comparisons


def test_dual_axis_bundle_replay_and_multipanel(semantic_data, encoding, secondary_y, tmp_path):
    panel = {"data": semantic_data, "kind": "point-line", "x": "x", "y": "y", "group": "method",
             "ylabel": "Relative height (-)", "secondary_y": secondary_y}
    figure, axes, _ = render_multipanel([panel, panel], ncols=1, encoding=encoding, palette="jewel", size="double",
                                       height_mm=190, sharex=True, output=tmp_path / "figure",
                                       bundle=tmp_path / "bundle", include_data=True)
    assert len(figure.legends[0].get_texts()) == 4
    replay, restored, _ = replay_bundle(tmp_path / "bundle", ["--output-dir", str(tmp_path / "replayed")])
    assert restored[1].scientific_secondary_axes.lines[0].get_fillstyle() == "none"
    assert replay.scientific_metadata["panels"][0]["secondary_y"]["reason"] == secondary_y["reason"]
    with pytest.raises(ValueError, match="sharey"):
        render_multipanel([panel], sharey=True)


def test_dual_axis_cli_pins_both_configs(semantic_data, encoding, secondary_y, tmp_path):
    data_path = tmp_path / "data.csv"
    semantic_data.to_csv(data_path, index=False)
    encoding_path = tmp_path / "roles.json"
    encoding_path.write_text(json.dumps(encoding))
    secondary_path = tmp_path / "axes.json"
    secondary_path.write_text(json.dumps(secondary_y))
    run_cli(["--input", str(data_path), "--kind", "point-line", "--x", "x", "--y", "y", "--group", "method",
             "--ylabel", "Relative height (-)", "--palette", "jewel", "--size", "double",
             "--encoding-config", str(encoding_path), "--secondary-y-config", str(secondary_path),
             "--output", str(tmp_path / "figure")])
    assert json.loads((tmp_path / "figure_encoding.json").read_text()) == encoding
    assert json.loads((tmp_path / "figure_secondary_y.json").read_text()) == secondary_y


def test_dense_hollow_marker_warning_preserves_observations():
    coordinates = np.linspace(0, 1, 1000)
    figure, axes, _ = render_plot({"x": coordinates, "y": coordinates}, kind="point-line", x="x", y="y",
                                  series_styles={"": {"fillstyle": "none"}})
    assert len(axes.lines[0].get_xdata()) == 1000
    assert any(item["rule"] == "hollow_marker" for item in review_figure(figure))


@pytest.mark.parametrize("kind", ["line", "scatter"])
def test_dual_axis_native_kinds_keep_semantics(semantic_data, secondary_y, kind):
    figure, axes, _ = render(semantic_data, kind=kind, secondary_y=secondary_y, ylabel="Relative height (-)", size="double")
    right = axes.scientific_secondary_axes
    if kind == "line":
        assert all(line.get_marker() == "None" for panel in (axes, right) for line in panel.lines)
    else:
        assert not axes.lines and not right.lines
        assert len(axes.collections) == len(right.collections) == 2


def test_typed_incompatible_metrics_require_facets_or_dual(semantic_data, encoding, secondary_y):
    encoding["metrics"]["Height"].update(quantity="relative height", unit="-")
    encoding["metrics"]["Angle"].update(quantity="contact angle", unit="deg")
    with pytest.raises(ValueError, match="cannot share one y axis"):
        render(semantic_data, encoding=encoding)
    render(semantic_data, encoding=encoding, secondary_y=secondary_y, ylabel="Relative height (-)", size="double")
    encoding["metrics"]["Angle"]["unit"] = "rad"
    with pytest.raises(ValueError, match="disagrees"):
        render(semantic_data, encoding=encoding, secondary_y=secondary_y, ylabel="Relative height (-)")


def test_shared_y_does_not_link_different_declared_metric_units(semantic_data, encoding):
    encoding["metrics"]["Height"].update(quantity="relative height", unit="-")
    encoding["metrics"]["Angle"].update(quantity="contact angle", unit="deg")
    panel = {"kind": "point-line", "x": "x", "y": "y", "group": "method"}
    panels = [{**panel, "data": semantic_data[semantic_data.method.str.endswith(metric)]} for metric in ("height", "angle")]
    with pytest.raises(ValueError, match="sharey cannot link"):
        render_multipanel(panels, encoding=encoding, sharey=True)


@pytest.mark.parametrize("kind", ["point-line", "scatter"])
def test_factorized_legend_requires_distinct_metric_keys(semantic_data, encoding, kind):
    encoding["metrics"]["Angle"] = {"fillstyle": "full"}
    with pytest.raises(ValueError, match="distinct visible encodings"):
        render(semantic_data, kind=kind, encoding=encoding)


def test_partial_metric_units_are_not_invented(semantic_data, encoding):
    encoding["metrics"]["Height"]["unit"] = "-"
    with pytest.raises(ValueError, match="both nonempty"):
        render(semantic_data, encoding=encoding)


def test_explicit_full_marker_is_not_false_grayscale_backup(observations):
    figure, _, _ = render(observations, series_styles={"A": {"color": "black", "marker": "o"},
                                                     "B": {"color": "black", "marker": "o", "fillstyle": "full"}})
    findings = _grayscale_findings(figure)
    assert findings[0]["measured"]["marker_or_dash_backup"] is False


def test_factorized_shared_legend_clears_panel_letters(semantic_data, encoding):
    panel = {"data": semantic_data, "kind": "point-line", "x": "x", "y": "y", "group": "method"}
    figure, axes, _ = render_multipanel([panel, panel, panel, panel], ncols=2, encoding=encoding, size="double", height_mm=180)
    renderer = figure.canvas.get_renderer()
    legend_box = figure.legends[0].get_window_extent(renderer)
    for panel_axes in axes:
        for text in panel_axes.texts:
            if getattr(text, "_scientific_panel_letter", False):
                assert not legend_box.overlaps(text.get_window_extent(renderer))
    for panel_axes, metadata in zip(axes, figure.scientific_metadata["panels"]):
        for line in panel_axes.lines:
            assert metadata["series"][line.get_label()]["marker_size_pt"] == line.get_markersize()


def test_semantic_bundle_omits_raw_data_by_default(semantic_data, encoding, secondary_y, tmp_path):
    data = semantic_data.copy(deep=True)
    data.loc[data.method == "A angle", "y"] = 91.123456789
    data["private_unused"] = "PRIVATE_UNUSED_DATA"
    render(data, encoding=encoding, secondary_y=secondary_y, ylabel="Relative height (-)", size="double",
           output=tmp_path / "figure", bundle=tmp_path / "bundle")
    root = tmp_path / "bundle"
    assert not (root / "inputs").exists()
    for path in root.rglob("*.json"):
        text = path.read_text()
        assert "91.123456789" not in text
        assert "PRIVATE_UNUSED_DATA" not in text


@pytest.mark.parametrize("kind", ["bar", "violin"])
def test_focus_ungrouped_categories(observations, kind):
    data = observations if kind == "violin" else observations.groupby("method", sort=False, as_index=False)["y"].mean()
    _, axes, _ = render_plot(data, kind=kind, x="method", y="y", palette="focus", focus="B")
    if kind == "bar":
        shades = [to_hex(patch.get_facecolor()) for patch in axes.patches]
    else:
        shades = [to_hex(body.get_facecolor()[0]) for body in axes.collections[:2]]
    assert shades == [color.lower() for color in (PALETTES["focus"][1], PALETTES["focus"][0])]


@pytest.mark.parametrize("palette", [None, [], "missing"])
def test_invalid_palettes_raise_clear_errors(observations, palette):
    with pytest.raises(ValueError, match="palette"):
        render(observations, palette=palette)


def test_palette_contrast_and_vision_preview_diagnostics():
    sys.path.insert(0, str(ROOT / "examples"))
    from plot_semantic_gallery import palette_diagnostics, simulate_rgb

    diagnostics = palette_diagnostics()
    for palette in diagnostics["palettes"].values():
        assert palette["minimum_white_contrast"] >= 3.4
    rgb = np.array([[0, 0, 0], [1, 1, 1], [0.2, 0.4, 0.6]])
    for mode in ("grayscale", "protanopia", "deuteranopia", "tritanopia"):
        simulated = simulate_rgb(rgb, mode)
        np.testing.assert_allclose(simulated[:2], rgb[:2], atol=2e-6)
        assert np.isfinite(simulated).all() and np.all((simulated >= 0) & (simulated <= 1))
