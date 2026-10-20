import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import warnings

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
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
def data():
    return pd.DataFrame({"x": [3., 1., 2., 3., 1., 2.], "y": [2., 1., 3., 2.1, 1.1, 3.1],
                         "method": ["A", "A", "A", "B", "B", "B"], "sd": [0.03] * 6,
                         "unused": ["PRIVATE_UNUSED_WORKSHEET_VALUE"] * 6})


def render(data, root, **kwargs):
    return template.render_plot(data, kind="point-line", x="x", y="y", group="method",
                                output=root / "figure", **kwargs)


def run_bundle(root, *arguments, **kwargs):
    return subprocess.run([sys.executable, str(root / "reproduce.py"), *map(str, arguments)],
                          capture_output=True, text=True, timeout=60, **kwargs)


def test_default_behavior_has_no_new_sidecars(tmp_path, data):
    figure, _, paths = render(data, tmp_path)
    assert paths == [tmp_path / "figure.jpg"]
    assert {path.name for path in tmp_path.iterdir()} == {"figure.jpg"}
    assert not hasattr(figure, "scientific_report_paths")
    assert not hasattr(figure, "scientific_bundle_path")


@pytest.mark.parametrize("options", [{"report": True}, {"bundle": "delivery"}, {"include_data": True}])
def test_delivery_requires_explicit_paths_and_permission(options):
    with pytest.raises(ValueError, match="requires|require"):
        template.render_plot({"x": [1, 2], "y": [2, 3]}, kind="line", x="x", y="y", **options)


def test_report_verifies_actual_files_and_preserves_return_value(tmp_path, data):
    figure, _, paths = render(data, tmp_path, report=True, formats=["jpeg", "tiff"], dpi=120)
    assert paths == [tmp_path / "figure.jpg", tmp_path / "figure.tiff"]
    assert figure.scientific_report_paths == [tmp_path / "figure_review.json", tmp_path / "figure_review.md"]
    report = json.loads(figure.scientific_report_paths[0].read_text())
    assert report["schema_version"] == 1
    assert report["snapshot_date"] == template.SNAPSHOT_DATE
    assert len(report["exports"]) == 2
    assert not any(finding["severity"] == "error" for finding in report["findings"])
    for record in report["exports"]:
        assert record["sha256"] == template._sha256(tmp_path / record["file"])
        assert record["dpi"] == [120, 120]
        assert len(record["physical_mm"]) == 2
    tiff = report["exports"][1]
    assert tiff["mode"] == "RGBA" and tiff["opaque_alpha"] is True
    assert report["fonts"]["requested"] == "Arial"
    assert report["fonts"]["resolved"][0]["sha256"]
    text = figure.scientific_report_paths[1].read_text()
    assert "Manual checks" in text and "not certification" in text
    assert "PRIVATE_UNUSED_WORKSHEET_VALUE" not in text
    assert not any(face.get("path") for face in report["fonts"]["resolved"])


def test_runtime_notices_are_reported_and_still_emitted(tmp_path, data):
    with pytest.warns(UserWarning, match="Unregistered"):
        figure, _, _ = render(data, tmp_path, report=True, style_registry={"A": {}})
    assert any("Unregistered" in finding["message"] for finding in figure.scientific_report["findings"])


def test_gray_backup_changes_severity_without_restyling(tmp_path, data):
    for distinct_marker in (False, True):
        registry = {"A": {"color": "#333333", "marker": "o", "linestyle": "-"},
                    "B": {"color": "#333333", "marker": "s" if distinct_marker else "o", "linestyle": "-"}}
        _, before, _ = render(data, tmp_path, style_registry=registry)
        figure, after, _ = render(data, tmp_path, report=True, style_registry=registry)
        findings = [finding for finding in figure.scientific_report["findings"] if finding["rule"] == "grayscale"]
        assert findings[0]["severity"] == ("info" if distinct_marker else "warn")
        for first, second in zip(before.lines, after.lines):
            assert first.get_color() == second.get_color()
            assert first.get_marker() == second.get_marker()
            assert first.get_linewidth() == second.get_linewidth()
            np.testing.assert_array_equal(first.get_ydata(), second.get_ydata())


@pytest.mark.parametrize("failure", ["decode", "format", "dpi", "pixels"])
def test_bad_actual_export_writes_reports_before_raising(tmp_path, data, monkeypatch, failure):
    export = template._export_figure

    def altered(*args, **kwargs):
        paths = export(*args, **kwargs)
        path = paths[0]
        if failure == "decode":
            path.write_bytes(b"not an image")
        else:
            with Image.open(path) as source:
                image = source.copy()
            if failure == "pixels":
                image = image.resize((image.width + 20, image.height))
            image.save(path, format="TIFF" if failure == "format" else "JPEG", dpi=(72, 72) if failure == "dpi" else (300, 300))
        return paths

    monkeypatch.setattr(template, "_export_figure", altered)
    with pytest.raises(ValueError, match="Export verification failed"):
        render(data, tmp_path, report=True)
    assert (tmp_path / "figure.jpg").exists()
    report = json.loads((tmp_path / "figure_review.json").read_text())
    assert any(finding["severity"] == "error" and finding["rule"] == f"file_{failure}" for finding in report["findings"])
    assert (tmp_path / "figure_review.md").exists()


def test_one_pixel_rounding_is_accepted(tmp_path, data, monkeypatch):
    export = template._export_figure

    def altered(*args, **kwargs):
        paths = export(*args, **kwargs)
        with Image.open(paths[0]) as source:
            image = source.resize((source.width + 1, source.height))
        image.save(paths[0], dpi=(300, 300))
        return paths

    monkeypatch.setattr(template, "_export_figure", altered)
    figure, _, _ = render(data, tmp_path, report=True)
    assert not any(finding["severity"] == "error" for finding in figure.scientific_report["findings"])


def test_inset_typography_is_reviewed(tmp_path, data, monkeypatch):
    refresh = template._refresh_inset

    def tiny_ticks(axes):
        refresh(axes)
        if hasattr(axes, "scientific_inset_axes"):
            axes.scientific_inset_axes.tick_params(labelsize=4)

    monkeypatch.setattr(template, "_refresh_inset", tiny_ticks)
    figure, _, _ = render(data, tmp_path, report=True,
                          inset={"xlim": [1, 2], "ylim": [1, 3], "bounds": [.15, .6, .3, .3]})
    assert any(finding["rule"] == "type" and finding["measured"] == 4 for finding in figure.scientific_report["findings"])


def test_no_data_bundle_contains_no_raw_arrays_or_indexes(tmp_path, data):
    data = data.copy()
    data["y"] = [9273.41234567, 9301.7654321, 9289.2345678] * 2
    data.index = pd.Index([f"PRIVATE_INDEX_{index}" for index in range(6)])
    bundle = tmp_path / "delivery"
    magnitudes = np.array([57.12345678, 57.23456789, 57.34567891] * 2)
    figure, _, _ = render(data, tmp_path, bundle=bundle,
                          error_bars={"y": magnitudes, "definition": "Supplied synthetic magnitudes"})
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["include_data"] is False and manifest["self_contained"] is False
    assert all(entry["file"] is None for entry in manifest["inputs"])
    assert not (bundle / "inputs").exists()
    assert not list((bundle / "artifacts").glob("*_metadata.json"))
    for path in bundle.rglob("*"):
        if path.suffix in (".json", ".txt", ".md"):
            text = path.read_text()
            for forbidden in ("9273.41234567", "57.12345678", "PRIVATE_INDEX_", "PRIVATE_UNUSED_WORKSHEET_VALUE", str(tmp_path)):
                assert forbidden not in text
    process = run_bundle(bundle)
    assert process.returncode != 0 and "Missing inputs" in process.stderr
    assert not (bundle / "replayed").exists()
    assert figure.scientific_bundle_path == bundle


def test_no_data_replay_accepts_explicit_table_and_auxiliary_inputs(tmp_path, data):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, error_bars={"y": [.01] * 6, "definition": "Supplied bounds"})
    table = tmp_path / "replacement.csv"
    data.to_csv(table, index=False)
    errors = tmp_path / "errors.csv"
    pd.DataFrame({"magnitude": [.01] * 6}).to_csv(errors, index=False)
    process = run_bundle(bundle, "--input", f"main={table}", "--input", f"main_yerr={errors}")
    assert process.returncode == 0, process.stderr
    assert (bundle / "replayed" / "figure.jpg").exists()


def test_authorized_snapshots_preserve_data_without_unused_columns(tmp_path, data):
    original = data.copy(deep=True)
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, include_data=True, error_bars={"y": "sd", "definition": "Supplied SD, n=4"})
    restored = template._snapshot_frame(json.loads((bundle / "inputs" / "main.json").read_text()))
    pd.testing.assert_frame_equal(restored, original[["x", "y", "method", "sd"]], check_exact=True)
    pd.testing.assert_frame_equal(data, original, check_exact=True)
    assert "PRIVATE_UNUSED_WORKSHEET_VALUE" not in (bundle / "inputs" / "main.json").read_text()


@pytest.mark.parametrize("kind", ["category", "datetime", "nullable", "multiindex", "float32", "object", "string"])
def test_typed_snapshot_roundtrip(kind):
    if kind == "category":
        frame = pd.DataFrame({"group": pd.Categorical(["B", "A", "B"], categories=["B", "A", "unused"], ordered=True)})
    elif kind == "datetime":
        frame = pd.DataFrame({"time": pd.date_range("2026-01-01", periods=3, tz="Asia/Shanghai")},
                             index=pd.date_range("2026-01-01", periods=3, freq="h"))
    elif kind == "nullable":
        frame = pd.DataFrame({"int": pd.array([1, None, 2], dtype="Int64"), "float": pd.array([1., None, 2.], dtype="Float64")})
    elif kind == "multiindex":
        frame = pd.DataFrame({"x": [1., 2., 3.]}, index=pd.MultiIndex.from_tuples([("A", 1), ("A", 2), ("B", 1)], names=["method", "row"]))
    elif kind == "float32":
        frame = pd.DataFrame({"x": np.array([.1, .2, .3], dtype="float32")})
    elif kind == "string":
        frame = pd.DataFrame({"name": pd.Series(["A", None, "B"], dtype="string")})
    else:
        frame = pd.DataFrame({"mixed": pd.Series([1, "A", None], dtype="object")})
    payload = template._snapshot_payload(frame)
    restored = template._snapshot_frame(json.loads(json.dumps(payload, allow_nan=False)))
    pd.testing.assert_frame_equal(frame, restored, check_exact=True)


def test_unsupported_snapshot_fails_without_partial_bundle(tmp_path):
    data = pd.DataFrame({"x": [1, 2], "y": [2, 3]}, index=[object(), object()])
    bundle = tmp_path / "delivery"
    with pytest.raises(ValueError, match="losslessly"):
        template.render_plot(data, kind="line", x="x", y="y", output=tmp_path / "figure", bundle=bundle, include_data=True)
    assert not bundle.exists()
    assert not list(tmp_path.glob(".plot-bundle-*"))


def test_relocated_replay_has_no_network_or_original_paths(tmp_path, data):
    source = tmp_path / "original"
    source.mkdir()
    bundle = source / "delivery"
    errors = pd.Series([.01, .02, .03] * 2, index=data.index)
    _, before, _ = render(data, source, bundle=bundle, include_data=True, size="double",
                          style_registry={"A": {}, "B": {}}, error_bars={"y": errors, "definition": "Supplied bounds"},
                          reference_guides=[{"kind": "constant", "axis": "y", "value": 1.5, "label": "Explicit reference"}],
                          inset={"xlim": [1, 2], "ylim": [1, 3.2], "bounds": [.12, .57, .3, .3]})
    relocated = tmp_path / "relocated"
    shutil.move(bundle, relocated)
    shutil.rmtree(source)
    guard = tmp_path / "offline"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import socket\ndef deny(*args, **kwargs):\n    raise RuntimeError('Network access forbidden')\n"
        "socket.create_connection = deny\nsocket.socket.connect = deny\n", encoding="utf-8")
    process = run_bundle(relocated, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(guard)})
    assert process.returncode == 0, process.stderr
    replayed = json.loads((relocated / "replayed" / "figure_review.json").read_text())
    assert not any(finding["severity"] == "error" for finding in replayed["findings"])
    figure, after, _ = template.replay_bundle(relocated, ["--output-dir", str(tmp_path / "second_replay")])
    for first, second in zip(before.lines, after.lines):
        np.testing.assert_array_equal(first.get_xdata(), second.get_xdata())
        np.testing.assert_array_equal(first.get_ydata(), second.get_ydata())
        assert first.get_color() == second.get_color()
        assert first.get_markersize() == second.get_markersize()
    assert figure.scientific_report["exports"][0]["pixels"] == replayed["exports"][0]["pixels"]


def test_multipanel_bundle_preserves_layout_heatmaps_and_error_panel(tmp_path, data):
    panels = [
        {"id": "profile", "data": data, "kind": "point-line", "x": "x", "y": "y", "group": "method",
         "error": {"reference": "B", "definition": "signed"}},
        {"id": "first", "data": np.array([[1., 2.], [3., 4.]]), "kind": "heatmap", "quantity": "pressure", "unit": "Pa"},
        {"id": "second", "data": np.array([[2., 3.], [4., 5.]]), "kind": "heatmap", "quantity": "pressure", "unit": "Pa"},
    ]
    bundle = tmp_path / "delivery"
    figure, axes, _ = template.render_multipanel(
        panels, output=tmp_path / "multi", bundle=bundle, include_data=True, height_mm=180,
        layout=[["profile", "profile"], ["first", "second"]], style_registry={"A": {}, "B": {}},
        shared_colorbar={"vmin": 0, "vmax": 6, "label": "Pressure (Pa)"})
    replay, replay_axes, _ = template.replay_bundle(bundle, [])
    assert replay.scientific_metadata["layout"] == figure.scientific_metadata["layout"]
    assert len(replay.axes) == len(figure.axes)
    assert replay.scientific_metadata["shared_colorbar"] == figure.scientific_metadata["shared_colorbar"]
    for first, second in zip(axes[0].lines, replay_axes[0].lines):
        np.testing.assert_array_equal(first.get_xdata(), second.get_xdata())
        np.testing.assert_array_equal(first.get_ydata(), second.get_ydata())
    for first, second in zip(axes[1:], replay_axes[1:]):
        np.testing.assert_array_equal(first.images[0].get_array(), second.images[0].get_array())
    assert len(replay.legends) == 1


@pytest.mark.parametrize("entry", ["recipe.json", "plot_template.py", "inputs/main.json", "reproduce.py"])
def test_checksum_changes_stop_replay_before_template_execution(tmp_path, data, entry):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, include_data=True)
    with (bundle / entry).open("a") as target:
        target.write("\n# changed\n")
    if entry == "reproduce.py":
        with pytest.raises(ValueError, match="checksum"):
            template.replay_bundle(bundle, [])
    else:
        process = run_bundle(bundle)
        assert process.returncode != 0 and "Checksum mismatch" in process.stderr
    assert not (bundle / "replayed").exists()


def test_versions_and_font_drift_are_disclosed(tmp_path, data):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, include_data=True)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["environment"]["python"] = "0.0.0"
    manifest["fonts"]["requested"] = "An explicitly different font"
    manifest_path.write_text(json.dumps(manifest))
    process = run_bundle(bundle)
    assert process.returncode == 0, process.stderr
    assert "Runtime versions differ" in process.stderr and "Resolved fonts differ" in process.stderr


def test_missing_runtime_dependency_has_actionable_message(tmp_path, data):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, include_data=True)
    guard = tmp_path / "missing_dependency"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import sys\nclass Block:\n    def find_spec(self, fullname, *args):\n"
        "        if fullname == 'matplotlib':\n            raise ModuleNotFoundError('matplotlib unavailable')\n"
        "sys.meta_path.insert(0, Block())\n", encoding="utf-8")
    process = run_bundle(bundle, env={**os.environ, "PYTHONPATH": str(guard)})
    assert process.returncode != 0 and "Missing runtime dependency" in process.stderr
    assert "Install dependencies manually" in process.stderr


def test_existing_destination_and_replay_outputs_are_not_overwritten(tmp_path, data):
    bundle = tmp_path / "delivery"
    bundle.mkdir()
    marker = bundle / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="empty directory"):
        render(data, tmp_path, bundle=bundle)
    assert not (tmp_path / "figure.jpg").exists()
    assert marker.read_text() == "keep"
    marker.unlink()
    render(data, tmp_path, bundle=bundle, include_data=True)
    with pytest.raises(ValueError, match="fresh/empty"):
        template.replay_bundle(bundle, ["--output-dir", str(bundle)])
    template.replay_bundle(bundle, [])
    with pytest.raises(ValueError, match="fresh/empty"):
        template.replay_bundle(bundle, [])


def test_cli_excel_snapshot_excludes_other_sheets_and_columns(tmp_path, data):
    source = tmp_path / "workbook.xlsx"
    with pd.ExcelWriter(source) as writer:
        pd.DataFrame({"private": ["PRIVATE_OTHER_SHEET"]}).to_excel(writer, sheet_name="private", index=False)
        data.to_excel(writer, sheet_name="used", index=False)
    bundle = tmp_path / "delivery"
    arguments = ["--input", str(source), "--sheet", "used", "--kind", "line", "--x", "x", "--y", "y",
                 "--group", "method", "--output", str(tmp_path / "excel"), "--bundle", str(bundle), "--include-data"]
    template.run_cli(arguments)
    assert not list(bundle.rglob("*.xlsx"))
    snapshot = (bundle / "inputs" / "main.json").read_text()
    assert "PRIVATE_OTHER_SHEET" not in snapshot and "PRIVATE_UNUSED_WORKSHEET_VALUE" not in snapshot
    assert "--bundle" not in (tmp_path / "excel_reproduce.py").read_text()
    source.unlink()
    process = run_bundle(bundle)
    assert process.returncode == 0, process.stderr


def test_failure_during_staging_leaves_no_complete_or_partial_bundle(tmp_path, data, monkeypatch):
    bundle = tmp_path / "delivery"
    original = template._json_write

    def fail_manifest(path, payload):
        if path.name == "manifest.json":
            raise OSError("simulated finalization failure")
        return original(path, payload)

    monkeypatch.setattr(template, "_json_write", fail_manifest)
    with pytest.raises(OSError, match="finalization"):
        render(data, tmp_path, bundle=bundle, include_data=True)
    assert not bundle.exists()
    assert not list(tmp_path.glob(".plot-bundle-*"))


def test_unsafe_manifest_paths_are_rejected(tmp_path, data):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, include_data=True)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"]["../outside.txt"] = "invalid"
    path.write_text(json.dumps(manifest))
    process = run_bundle(bundle)
    assert process.returncode != 0 and "unsafe managed path" in process.stderr


def test_no_data_matrix_replay_requires_explicit_typed_labels(tmp_path):
    matrix = pd.DataFrame([[1.25, 2.5], [3.75, 5]], index=["north", "south"], columns=["left", "right"])
    bundle = tmp_path / "matrix_delivery"
    template.render_plot(matrix, kind="heatmap", output=tmp_path / "matrix", bundle=bundle)
    source = tmp_path / "matrix.csv"
    matrix.to_csv(source)
    figure, axes, paths = template.replay_bundle(bundle, ["--input", f"main={source}"])
    np.testing.assert_array_equal(axes.images[0].get_array(), matrix.to_numpy())
    assert [text.get_text() for text in axes.get_yticklabels()] == ["north", "south"]
    assert paths == [bundle / "replayed" / "figure.jpg"]
    assert not any(item["severity"] == "error" for item in figure.scientific_report["findings"])


@pytest.mark.parametrize("source", [{"x": [3, 1, 2], "y": [1.5, 2.5, 3.5]}, np.array([[1., 2.], [3., 4.]])])
def test_python_dictionary_and_array_delivery(tmp_path, source):
    bundle = tmp_path / "delivery"
    options = {"kind": "line", "x": "x", "y": "y"} if isinstance(source, dict) else {"kind": "heatmap"}
    figure, before, _ = template.render_plot(source, output=tmp_path / "figure", bundle=bundle,
                                             include_data=True, **options)
    replay, after, _ = template.replay_bundle(bundle, [])
    if isinstance(source, dict):
        np.testing.assert_array_equal(before.lines[0].get_xdata(), after.lines[0].get_xdata())
        np.testing.assert_array_equal(before.lines[0].get_ydata(), after.lines[0].get_ydata())
    else:
        np.testing.assert_array_equal(before.images[0].get_array(), after.images[0].get_array())
    assert figure.scientific_report["exports"][0]["pixels"] == replay.scientific_report["exports"][0]["pixels"]


def test_missing_auxiliary_input_stops_before_render(tmp_path, data):
    bundle = tmp_path / "delivery"
    render(data, tmp_path, bundle=bundle, error_bars={"y": [.01] * len(data), "definition": "Synthetic"})
    table = tmp_path / "external.csv"
    data.to_csv(table, index=False)
    process = run_bundle(bundle, "--input", f"main={table}")
    assert process.returncode != 0 and "main_yerr" in process.stderr
    assert not (bundle / "replayed").exists()


def test_report_without_bundle_includes_shared_colorbar_text(tmp_path, monkeypatch):
    review = template.review_figure

    def tiny_colorbar(figure, **kwargs):
        for axes in figure.axes:
            if axes.get_ylabel() == "Synthetic value (-)":
                axes.yaxis.label.set_fontsize(3)
        return review(figure, **kwargs)

    monkeypatch.setattr(template, "review_figure", tiny_colorbar)
    figure, _, paths = template.render_multipanel(
        [{"kind": "heatmap", "data": np.ones((2, 2)) * value, "quantity": "synthetic", "unit": "-"}
         for value in (1, 2)], report=True, output=tmp_path / "panels", formats=["jpeg", "tiff"], dpi=100,
        shared_colorbar={"vmin": 0, "vmax": 2, "label": "Synthetic value (-)"})
    assert len(paths) == 2
    assert any(finding["rule"] == "type" and finding["measured"] == 3
               for finding in figure.scientific_report["findings"])
    assert not hasattr(figure, "scientific_bundle_path")


def test_bundle_destination_file_is_preserved(tmp_path, data):
    destination = tmp_path / "delivery"
    destination.write_text("keep")
    with pytest.raises(ValueError, match="empty directory"):
        render(data, tmp_path, bundle=destination)
    assert destination.read_text() == "keep"
    assert not (tmp_path / "figure.jpg").exists()


def test_export_size_checked_against_request_not_modified_canvas(tmp_path, data, monkeypatch):
    export = template._export_figure

    def resized(figure, *args, **kwargs):
        figure.set_size_inches(figure.get_figwidth() + .25, figure.get_figheight())
        return export(figure, *args, **kwargs)

    monkeypatch.setattr(template, "_export_figure", resized)
    with pytest.raises(ValueError, match="Export verification failed"):
        render(data, tmp_path, report=True)
    report = json.loads((tmp_path / "figure_review.json").read_text())
    assert any(finding["rule"] == "file_pixels" for finding in report["findings"])


def test_extended_numpy_scalar_does_not_recurse_forever():
    value = np.longdouble("1.123456789123456789")
    if isinstance(value.item(), np.generic):
        with pytest.raises(ValueError, match="losslessly snapshot scalar dtype"):
            template._encode_scalar(value)


@pytest.mark.parametrize("resolution", [None, 300, (float("nan"), 300), (float("inf"), 300), (300,)])
def test_malformed_dpi_metadata_still_saves_both_reports(tmp_path, data, monkeypatch, resolution):
    open_image = template.Image.open

    def malformed(*args, **kwargs):
        image = open_image(*args, **kwargs)
        image.info["dpi"] = resolution
        return image

    monkeypatch.setattr(template.Image, "open", malformed)
    with pytest.raises(ValueError, match="Export verification failed"):
        render(data, tmp_path, report=True)
    report = json.loads((tmp_path / "figure_review.json").read_text())
    assert any(item["rule"] == "file_dpi" and item["severity"] == "error" for item in report["findings"])
    assert (tmp_path / "figure_review.md").is_file()
