import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))
import plot_template as template


@pytest.fixture(autouse=True)
def cleanup():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*not installed; using.*")
        yield
    plt.close("all")


@pytest.fixture
def samples():
    return pd.DataFrame({"signal": [3., 0., 1., 1., 0., 3., 2., 2.],
                         "response": [2., 0., 3., 1., 1., 3., 0., 2.],
                         "method": ["A"] * 4 + ["B"] * 4,
                         "volume": [1., 2., 3., 4., 4., 3., 2., 1.],
                         "time": [0., 1., 2., 3.] * 2,
                         "private": ["UNUSED_PRIVATE_VALUE"] * 8})


def render(samples, kind, **options):
    return template.render_plot(samples, kind=kind, x="signal", **options)


@pytest.mark.parametrize("statistic", ["count", "probability", "density"])
@pytest.mark.parametrize("weighted", [False, True])
def test_histogram_common_nonuniform_edges_and_normalization(samples, statistic, weighted):
    original = samples.copy(deep=True)
    config = {"bins": [0, 1, 3], "statistic": statistic}
    if weighted:
        config.update(weight="volume", weight_definition="Cell volume (m^3)")
    figure, axes, _ = render(samples, "histogram", group="method", analysis=config)
    for patch, (_, subset) in zip(axes.patches, samples.groupby("method", sort=False)):
        expected, edges = np.histogram(subset.signal, bins=config["bins"], weights=subset.volume if weighted else None)
        expected = expected.astype(float)
        if statistic != "count":
            expected /= expected.sum()
        if statistic == "density":
            expected /= np.diff(edges)
            assert np.sum(patch.get_data().values * np.diff(edges)) == pytest.approx(1)
        np.testing.assert_allclose(patch.get_data().values, expected)
        np.testing.assert_array_equal(patch.get_data().edges, edges)
    assert figure.scientific_metadata["analysis"]["sample_sizes"] == {"A": 4, "B": 4}
    pd.testing.assert_frame_equal(samples, original)


def test_ecdf_weighted_ties_and_input_order(samples):
    original = samples.copy(deep=True)
    figure, axes, _ = render(samples, "ecdf", group="method", analysis={"weight": "volume", "weight_definition": "Cell volume"})
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), [0, 0, 1, 3])
    np.testing.assert_allclose(axes.lines[0].get_ydata(), [0, .2, .9, 1])
    assert axes.lines[0].get_drawstyle() == "steps-post"
    assert "ties combined" in figure.scientific_metadata["analysis"]["processing"]
    pd.testing.assert_frame_equal(samples, original)


def test_ecdf_singleton_and_constant_samples():
    for values in ([2.], [2., 2., 2.]):
        _, axes, _ = render({"signal": values}, "ecdf")
        np.testing.assert_array_equal(axes.lines[0].get_xdata(), [2, 2])
        np.testing.assert_array_equal(axes.lines[0].get_ydata(), [0, 1])


def test_box_median_and_fliers_are_not_hidden():
    figure, axes, _ = render({"signal": [0., 1., 2., 3., 100.]}, "box", analysis={"whis": 1.5})
    assert any(np.array_equal(line.get_ydata(), [2., 2.]) for line in axes.lines)
    assert any(100 in line.get_ydata() and line.get_marker() == "o" for line in axes.lines)
    assert axes.get_ylabel() == "signal"
    assert figure.scientific_metadata["analysis"]["whis"] == 1.5


@pytest.mark.parametrize("statistic", ["count", "probability", "density"])
@pytest.mark.parametrize("weighted", [False, True])
def test_joint_orientation_and_integral(samples, statistic, weighted):
    config = {"bins": [[0, 1, 3], [0, 1, 2, 3]], "statistic": statistic}
    if weighted:
        config.update(weight="volume", weight_definition="Cell volume")
    figure, axes, _ = render(samples, "joint", y="response", analysis=config)
    expected, xedges, yedges = np.histogram2d(samples.signal, samples.response, bins=config["bins"],
                                             weights=samples.volume if weighted else None)
    if statistic != "count":
        expected /= expected.sum()
    if statistic == "density":
        area = np.diff(xedges)[:, None] * np.diff(yedges)[None, :]
        expected /= area
        assert np.sum(np.asarray(axes.collections[0].get_array()).reshape(3, 2).T * area) == pytest.approx(1)
    np.testing.assert_allclose(np.asarray(axes.collections[0].get_array()).reshape(3, 2), expected.T)
    assert axes.collections[0].get_cmap().name == "cividis"
    assert figure.scientific_metadata["heatmap"] is True


def test_joint_fixed_color_scale(samples):
    _, axes, _ = render(samples, "joint", y="response", analysis={"bins": [2, 3], "statistic": "probability", "vmax": 1})
    assert axes.collections[0].get_clim() == (0, 1)
    with pytest.raises(ValueError, match="excludes"):
        render(samples, "joint", y="response", analysis={"bins": [2, 3], "statistic": "probability", "vmax": .001})


def test_trajectory_preserves_path_and_only_explicit_arrows(samples):
    original = samples.copy(deep=True)
    figure, axes, _ = render(samples, "trajectory", y="response", group="method", analysis={"order": "time", "arrows": [0, 2]})
    paths = [line for line in axes.lines if line.get_label() in ("A", "B")]
    assert len(paths) == 2
    np.testing.assert_array_equal(paths[0].get_xdata(), [3, 0, 1, 1])
    np.testing.assert_array_equal(paths[0].get_ydata(), [2, 0, 3, 1])
    assert len(axes.texts) == 4
    assert figure.scientific_metadata["analysis"]["order"] == "time"
    pd.testing.assert_frame_equal(samples, original)


def test_contribution_signed_values_and_missing_combinations():
    data = {"term": ["Production", "Transport", "Loss", "Loss"], "value": [3., -.5, -2., -1.], "case": ["A", "A", "A", "B"]}
    figure, axes, _ = template.render_plot(data, kind="contribution", x="term", y="value", group="case",
                                          analysis={"definition": "Supplied signed budget terms; positive adds energy."})
    assert [patch.get_height() for patch in axes.patches] == [3, -.5, -2, -1]
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["Production", "Transport", "Loss"]
    assert any(np.array_equal(line.get_ydata(), [0, 0]) for line in axes.lines)
    assert figure.scientific_metadata["analysis"]["baseline"] == 0


@pytest.mark.parametrize("kind,options,match", [
    ("histogram", {}, "explicit bins"),
    ("histogram", {"analysis": {"bins": 2, "statistic": "pdf"}}, "statistic"),
    ("histogram", {"analysis": {"bins": [1, 3], "statistic": "count"}}, "exclude"),
    ("histogram", {"analysis": {"bins": [0, 1, 1, 3], "statistic": "count"}}, "increasing"),
    ("histogram", {"analysis": {"bins": True, "statistic": "count"}}, "edges"),
    ("histogram", {"analysis": {"bins": 0, "statistic": "count"}}, "bins"),
    ("histogram", {"analysis": {"bins": 1001, "statistic": "count"}}, "bins"),
    ("ecdf", {"analysis": {"weight": "volume"}}, "weight_definition"),
    ("ecdf", {"analysis": {"weight_definition": "volume"}}, "requires"),
    ("ecdf", {"analysis": {"smooth": True}}, "accepts only"),
    ("box", {"analysis": {"weight": "volume"}}, "accepts only"),
    ("box", {"analysis": {"whis": 0}}, "whis"),
    ("joint", {"y": "response", "group": "method", "analysis": {"bins": [2, 2], "statistic": "count"}}, "one population"),
    ("joint", {"y": "response", "analysis": {"bins": 2, "statistic": "count"}}, "x_bins"),
    ("joint", {"y": "response", "analysis": {"bins": [1000, 1000], "statistic": "count"}}, "250000"),
    ("joint", {"y": "response", "analysis": {"bins": [2, 2], "statistic": "count"}, "palette": "jewel"}, "cividis"),
    ("trajectory", {"y": "response", "analysis": {"order": "time"}}, "strictly increase"),
    ("trajectory", {"y": "response", "analysis": {"arrows": [9]}}, "exceeds"),
    ("trajectory", {"y": "response", "analysis": {"arrows": [0, 0]}}, "unique"),
    ("trajectory", {"y": "response", "analysis": {"arrows": [-1]}}, "nonnegative"),
    ("contribution", {"y": "response"}, "definition"),
    ("ecdf", {"y": "response"}, "omit y"),
    ("ecdf", {"group": "missing"}, "Missing"),
    ("ecdf", {"series_styles": {}}, "do not support"),
    ("ecdf", {"xscale": "log"}, "Axis scales"),
    ("ecdf", {"value": "volume"}, "not value"),
    ("ecdf", {"palette": "focus", "focus": "absent"}, "focus"),
])
def test_invalid_analysis_requests_fail_explicitly(samples, kind, options, match):
    with pytest.raises(ValueError, match=match):
        render(samples, kind, **options)


@pytest.mark.parametrize("weights", [[-1, 2], [0, 0], [np.nan, 1], [np.inf, 1]])
def test_invalid_weights(weights):
    with pytest.raises(ValueError, match="Weights|weight|missing|finite"):
        render({"signal": [0, 1], "weight": weights}, "ecdf", analysis={"weight": "weight", "weight_definition": "Volume"})


def test_zero_weight_group_fails(samples):
    samples.loc[samples.method == "B", "volume"] = 0
    with pytest.raises(ValueError, match="positive finite"):
        render(samples, "ecdf", group="method", analysis={"weight": "volume", "weight_definition": "Volume"})


def test_missing_nonfinite_and_duplicate_terms_are_not_dropped():
    for invalid in (np.nan, np.inf):
        with pytest.raises(ValueError, match="missing|finite"):
            render({"signal": [0, invalid]}, "ecdf")
    with pytest.raises(ValueError, match="Repeated contribution"):
        template.render_plot({"term": ["A", "A"], "value": [1, 2]}, kind="contribution", x="term", y="value",
                             analysis={"definition": "Signed supplied terms"})
    with pytest.raises(ValueError, match="nonzero"):
        render({"signal": [1, 1], "response": [2, 2]}, "trajectory", y="response", analysis={"arrows": [0]})
    with pytest.raises(ValueError, match="analysis applies"):
        render({"signal": [1], "response": [2]}, "line", y="response", analysis={})


def options_for(kind):
    if kind == "histogram":
        return {"analysis": {"bins": 5, "statistic": "density", "weight": "volume", "weight_definition": "Cell volume"}}
    if kind == "joint":
        return {"y": "response", "analysis": {"bins": [4, 5], "statistic": "density", "weight": "volume", "weight_definition": "Cell volume"}}
    if kind == "trajectory":
        return {"y": "response", "group": "method", "analysis": {"order": "time", "arrows": [1]}}
    if kind == "contribution":
        return {"y": "response", "analysis": {"definition": "Supplied signed terms"}}
    return {"group": "method"}


@pytest.mark.parametrize("kind", template.ANALYSIS_KINDS)
def test_export_report_bundle_and_replay(tmp_path, samples, kind):
    options = options_for(kind)
    if kind == "contribution":
        samples = samples.copy()
        samples["signal"] = [f"term {index}" for index in range(len(samples))]
    bundle = tmp_path / "bundle"
    figure, _, paths = render(samples, kind, output=tmp_path / kind, dpi=100, report=True, bundle=bundle, include_data=True, **options)
    assert paths[0].is_file()
    assert figure.scientific_report["quantitative_analysis"][0]["analysis"]["kind"] == kind
    assert json.loads((tmp_path / f"{kind}_metadata.json").read_text())["analysis"]["kind"] == kind
    manifest = json.loads((bundle / "manifest.json").read_text())
    columns = [column for entry in manifest["inputs"] for column in entry["columns"]]
    assert "private" not in columns
    if kind in ("histogram", "joint"):
        assert "volume" in columns
    if kind == "trajectory":
        assert "time" in columns
    assert "UNUSED_PRIVATE_VALUE" not in "".join(path.read_text() for path in bundle.rglob("*.json"))
    result = subprocess.run([sys.executable, str(bundle / "reproduce.py")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((bundle / "replayed" / "figure_metadata.json").read_text())
    assert metadata["analysis"] == figure.scientific_metadata["analysis"]


def test_analysis_bundle_without_data_does_not_copy_samples(tmp_path, samples):
    render(samples, "ecdf", group="method", output=tmp_path / "ecdf", dpi=100, bundle=tmp_path / "bundle")
    assert not (tmp_path / "bundle" / "inputs").exists()
    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text())
    assert all(entry["file"] is None for entry in manifest["inputs"])


def test_multipanel_analysis_and_bundle(tmp_path, samples):
    panels = [{"data": samples, "kind": kind, "x": "signal", **options_for(kind)}
              for kind in ("histogram", "ecdf", "box", "joint", "trajectory")]
    figure, axes, _ = template.render_multipanel(panels, ncols=2, output=tmp_path / "gallery", dpi=100,
                                                bundle=tmp_path / "bundle", include_data=True, legend="each")
    assert len(axes) == 5
    assert [panel["analysis"]["kind"] for panel in figure.scientific_metadata["panels"]] == [panel["kind"] for panel in panels]
    result = subprocess.run([sys.executable, str(tmp_path / "bundle" / "reproduce.py")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_joint_comparison_colorbar_label_does_not_overlap_next_axis(samples):
    panels = [{"data": samples, "kind": "joint", "x": "signal", "y": "response",
               "analysis": {"bins": [4, 5], "statistic": "density", "vmax": 2},
               "ylabel": "Temperature fluctuation (K)"} for _ in range(2)]
    figure, axes, _ = template.render_multipanel(panels, ncols=2, height_mm=95, legend="none")
    renderer = figure.canvas.get_renderer()
    left_colorbar = axes[0].collections[0].colorbar.ax
    first_label = left_colorbar.yaxis.label.get_window_extent(renderer)
    second_label = axes[1].yaxis.label.get_window_extent(renderer)
    assert first_label.x1 < second_label.x0


def test_cli_analysis_configuration_is_copied_and_reproducible(tmp_path, samples):
    source = tmp_path / "samples.csv"
    samples.to_csv(source, index=False)
    config = tmp_path / "settings.json"
    config.write_text(json.dumps(options_for("histogram")["analysis"]))
    template.run_cli(["--input", str(source), "--kind", "histogram", "--x", "signal", "--group", "method",
                      "--analysis-config", str(config), "--output", str(tmp_path / "hist"), "--dpi", "100"])
    assert (tmp_path / "hist_analysis.json").is_file()
    config.unlink()
    result = subprocess.run([sys.executable, str(tmp_path / "hist_reproduce.py")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
