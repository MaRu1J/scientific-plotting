import importlib.util
import json
from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reactor_figures", ROOT / "examples/plot_reactor_thermal_hydraulics.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_iapws_official_table_36():
    np.testing.assert_allclose(RUNNER.saturation_temperature([.1, 1, 10]),
                               [372.755919, 453.035632, 584.149488], atol=1e-6, rtol=0)


@pytest.mark.parametrize("pressure", [0, -1, 23, np.nan])
def test_iapws_rejects_invalid_pressure(pressure):
    with pytest.raises(ValueError):
        RUNNER.saturation_temperature(pressure)


def test_sampling_preserves_extrema_and_order():
    frame = pd.DataFrame({"TIME": np.arange(100) * 10, "value": np.arange(100, dtype=float)})
    frame.loc[37, "value"] = 200
    frame.loc[61, "value"] = -100
    selected = RUNNER.sampled_indices(frame, ["value"])
    assert 37 in selected and 61 in selected
    assert selected[0] == 0 and selected[-1] == 99
    assert np.all(np.diff(selected) > 0)


def test_hwat_parser_keeps_source_sensor_order_and_duplicates():
    record = RUNNER.load_hwat(RUNNER.BUNDLE / "raw/ID_20230809_Run_10.xml")
    assert len(record["axial"]) == 23 and len(record["radial"]) == 12
    assert record["axial"].z_m.iloc[:4].tolist() == [3.79] * 4
    assert record["axial"].wall_c.iloc[0] == 320.0056
    assert record["radial"].r_normalized.iloc[0] == 1
    assert record["radial"].r_normalized.is_monotonic_decreasing


def test_bundle_uses_real_sources_and_required_plot_ratio():
    manifest = json.loads((RUNNER.BUNDLE / "manifest.json").read_text())
    assert len(manifest) == 14
    assert sum(record["kind"] in ("line", "point-line") for record in manifest) / len(manifest) >= .7
    for kind in ("scatter", "bar", "heatmap", "violin"):
        assert sum(record["kind"] == kind for record in manifest) == 1
    assert all(all(record["checks"].values()) for record in manifest)
    assert all(record["sources"] for record in manifest)


def test_source_cache_hashes_and_publisher_checksums():
    assert RUNNER.prepare_sources(RUNNER.BUNDLE) == RUNNER.BUNDLE / "raw"


def test_pressure_reference_sampling_records_exact_source_rows():
    raw = pd.read_csv(RUNNER.BUNDLE / "raw/LOCA_10.csv")
    plotted = pd.read_csv(RUNNER.BUNDLE / "data/05_loca_reference_pointline.csv")
    plotted = plotted.loc[plotted.series == "计算 / Calc. LOCA 10"]
    chosen = raw.iloc[plotted.source_row]
    np.testing.assert_array_equal(plotted.x, chosen.TIME)
    np.testing.assert_allclose(plotted.y, chosen.P * .1, rtol=1e-14)


def test_bar_is_full_timeseries_maximum():
    plotted = pd.read_csv(RUNNER.BUNDLE / "data/12_loca_peak_clad_bar.csv")
    expected = [pd.read_csv(RUNNER.BUNDLE / f"raw/LOCA_{severity}.csv").TPCT.max() for severity in (1, 10, 50)]
    np.testing.assert_array_equal(plotted.y, expected)


@pytest.mark.xfail(raises=AttributeError, reason="Original skill syncs BarContainer as if it were Line2D", strict=True)
def test_original_skill_grouped_bar_legend_known_failure():
    template, _ = RUNNER.load_template(RUNNER.BUNDLE)
    frame = pd.DataFrame({"x": ["1 cm²", "10 cm²"], "y": [550, 560], "series": "Calculation"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        try:
            template.render_plot(frame, kind="bar", x="x", y="y", group="series")
        finally:
            plt.close("all")
