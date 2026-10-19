import importlib.util
from pathlib import Path
import subprocess
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cfd_examples", ROOT / "examples" / "test_cfd_plotting.py")
CFD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CFD)


def test_dns_reader_normalizes_without_collapsing_staggered_grids(tmp_path):
    source = tmp_path / "dns.dat"
    source.write_text("Re_tau = 180\nRe_bulk = 5665\n"
                      "j y+ u_mean uu+ ww+\n1 1.0 1.0 0.2 0.1\n2 90.0 15.0 2.0 1.0\n\n"
                      "j y+ vv+ -uv+\n1 1.0 0.01 0.02\n2 90.0 0.4 0.5\n", encoding="utf-8")
    frame, metadata = CFD.read_dns(source)
    assert metadata["Re_tau"] == 180
    assert metadata["rows"] == 2
    np.testing.assert_array_equal(frame["y+"], [1.0, 90.0])
    np.testing.assert_allclose(frame["y_over_h"], [1 / 180, 0.5])
    np.testing.assert_allclose(frame["u_over_ub"], np.array([1, 15]) / (5665 / 360))
    assert "-uv+" not in frame
    np.testing.assert_array_equal(CFD.read_dns_table(source, "-uv+")["-uv+"], [0.02, 0.5])
    source.write_text(source.read_text().replace("2 90.0 0.4", "2 91.0 0.4"))
    mean, metadata = CFD.read_dns(source)
    assert metadata["staggered_mean_and_shear_grids"]
    np.testing.assert_array_equal(mean["y+"], [1.0, 90.0])
    np.testing.assert_array_equal(CFD.read_dns_table(source, "-uv+")["y+"], [1.0, 91.0])


def test_blasius_boundary_conditions_and_shooting_accuracy():
    eta, velocity, curvature = CFD.blasius_profile()
    assert len(eta) == 1001
    assert eta[0] == velocity[0] == 0
    assert eta[-1] == 10
    assert abs(velocity[-1] - 1) < 1e-10
    assert abs(curvature - 0.3320573362) < 2e-8
    assert (np.diff(velocity) >= -1e-13).all()


@pytest.mark.parametrize("kind", ["line", "point-line", "mixed"])
def test_cfd_renderer_preserves_nonmonotonic_order_and_artist_semantics(tmp_path, kind):
    template = CFD.load_template(ROOT / "scientific-plotting" / "scripts" / "plot_template.py")
    frame = CFD.series_frame(np.array([2, 0, 1]), [("Reference", np.array([3, 1, 2]))])
    overlay = pd.DataFrame({"x": [0.4, 1.4], "y": [1.5, 2.5], "series": "Samples (synth.)"})
    case = {"id": kind, "kind": kind, "frame": frame, "overlay": overlay if kind == "mixed" else None,
            "xlabel": "x (-)", "ylabel": "y (-)", "title": "CFD regression", "group_kind": "categorical", "scale": "linear"}
    audit = CFD.render_case(template, case, tmp_path)
    assert audit["legend_sample_hits"] == 0
    assert audit["image_pixels"] == [int(190 / 25.4 * 300), int(142.5 / 25.4 * 300)]
    assert bool(audit["marker_sizes_pt"]) == (kind == "point-line")


@pytest.mark.parametrize("scale", ["logx", "logy"])
def test_log_axes_use_real_log_minor_ticks_and_preserve_fonts(tmp_path, scale):
    template = CFD.load_template(ROOT / "scientific-plotting" / "scripts" / "plot_template.py")
    frame = CFD.series_frame(np.array([0.01, 0.1, 1, 10]), [("Residual", np.array([1, 0.1, 0.01, 0.001]))])
    case = {"id": scale, "kind": "line", "frame": frame, "overlay": None,
            "xlabel": "x (-)", "ylabel": "y (-)", "title": "Log axes", "group_kind": "categorical", "scale": scale}
    audit = CFD.render_case(template, case, tmp_path)
    assert audit["xscale"] == ("log" if scale == "logx" else "linear")
    assert audit["yscale"] == ("log" if scale == "logy" else "linear")
    assert not any("AutoMinorLocator" in message for message in audit["warnings"])


def test_long_form_heatmap_retains_value_column_and_cli_support(tmp_path):
    source = ROOT / "scientific-plotting" / "scripts" / "plot_template.py"
    template = CFD.load_template(source)
    frame = pd.DataFrame({"station": ["first", "first", "second", "second"],
                          "radius": ["wall", "center", "wall", "center"],
                          "velocity": [0, 2, 0, 2]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        figure, axes, _ = template.render_plot(frame, kind="heatmap", x="station", y="radius", value="velocity")
    np.testing.assert_array_equal(axes.images[0].get_array(), [[0, 0], [2, 2]])
    plt.close(figure)
    input_path = tmp_path / "field.csv"
    frame.to_csv(input_path, index=False)
    subprocess.run([sys.executable, str(source), "--input", str(input_path), "--kind", "heatmap",
                    "--x", "station", "--y", "radius", "--value", "velocity", "--output", str(tmp_path / "field")],
                   check=True, capture_output=True, text=True)
    assert (tmp_path / "field.jpg").exists()
