import os
from pathlib import Path
import sys
import warnings

os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))

from plot_template import SIZES_MM, connected_stroke, render_multipanel, render_plot


@pytest.fixture(autouse=True)
def ignore_font_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*not installed; using.*")
        yield
    plt.close("all")


def test_stroke_bands_and_manual_limits():
    assert connected_stroke(30) == (1.5, 6.2)
    assert connected_stroke(20) == (1.2, 5.0)
    assert connected_stroke(8) == (1.0, 3.8)
    assert connected_stroke(2) == (0.7, 2.6)
    data = {"x": [0, 1, 2], "y": [1, 2, 3]}
    for width in (0.4, 1.6):
        with pytest.raises(ValueError, match="line_width"):
            render_plot(data, kind="line", x="x", y="y", line_width=width)


def test_minor_grid_stays_on(observations=None):
    figure, axes, _ = render_plot({"x": [0, 1, 2], "y": [1, 2, 1]}, kind="line", x="x", y="y")
    minor = axes.xaxis.get_minor_ticks()[0].gridline
    assert minor.get_linestyle() == "--"
    assert minor.get_linewidth() == 0.45
    assert minor.get_visible()


@pytest.mark.parametrize("size,width,height", [
    ("single", 90, 67.5), ("medium", 140, 105), ("double", 190, 142.5),
    ("aip-single", 85, 63.75), ("aip-double", 170, 127.5),
])
def test_named_sizes_match_journal_widths(tmp_path, size, width, height):
    from PIL import Image

    figure, _, paths = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                                   size=size, output=tmp_path / size)
    assert paths == [tmp_path / f"{size}.jpg"]
    assert figure.scientific_metadata["width_mm"] == width
    assert figure.scientific_metadata["height_mm"] == height
    with Image.open(paths[0]) as image:
        assert abs(image.width - width / 25.4 * 300) < 2
        assert abs(image.height - height / 25.4 * 300) < 2
    assert SIZES_MM[size] == (width, height)


@pytest.mark.parametrize("fmt", ["png", "svg", "pdf", "eps"])
def test_removed_formats_are_refused(fmt):
    with pytest.raises(ValueError, match="JPEG and TIFF"):
        render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y", formats=[fmt])


def test_old_multipanel_size_points_at_the_new_entry():
    with pytest.raises(ValueError, match="render_multipanel"):
        render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y", size="multipanel")


def test_tiff_dpi_follows_the_journal_unless_set():
    figure, _, _ = render_plot({"x": [1, 10], "y": [1, 2]}, kind="line", x="x", y="y",
                               formats=["tiff"], journal="elsevier")
    assert figure.scientific_metadata["dpi_by_format"]["tiff"] == 1000
    heatmap, _, _ = render_plot(np.array([[1.0, 2.0], [3.0, 4.0]]), kind="heatmap", formats=["tiff"], journal="elsevier")
    assert heatmap.scientific_metadata["dpi_by_format"]["tiff"] == 500
    jfm, _, _ = render_plot({"x": [1, 10], "y": [1, 2]}, kind="line", x="x", y="y",
                            formats=["tiff"], journal="jfm")
    assert jfm.scientific_metadata["dpi_by_format"]["tiff"] == 1200
    pof, _, _ = render_plot({"x": [1, 10], "y": [1, 2]}, kind="line", x="x", y="y",
                            formats=["tiff"], journal="pof")
    assert pof.scientific_metadata["dpi_by_format"]["tiff"] == 600
    explicit, _, _ = render_plot({"x": [1, 10], "y": [1, 2]}, kind="line", x="x", y="y",
                                 formats=["tiff"], journal="elsevier", dpi=120)
    assert explicit.scientific_metadata["dpi_by_format"]["tiff"] == 120
    assert any(item["rule"] == "dpi" and item["severity"] == "warn" for item in explicit.scientific_review)


def _messages(findings):
    return " ".join(item["message"] for item in findings)


def test_review_reports_differences_without_a_compliance_claim():
    wide, _, _ = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                             size="double", journal="pof")
    assert any(item["rule"] == "width" and item["severity"] == "warn" and "190" in item["message"]
               for item in wide.scientific_review)
    elsevier, _, _ = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                                 size="single", journal="elsevier")
    assert not any(item["rule"] == "width" and item["severity"] == "warn" for item in elsevier.scientific_review)
    jfm, _, _ = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y", journal="jfm")
    text = _messages(jfm.scientific_review)
    assert "EPS" in text and "TIFF" in text
    assert "CMYK" in text and "RGB" in text
    assert "90 mm" in text
    blob = text.lower()
    for word in ("compliant", "符合", "通过"):
        assert word not in blob
    assert "pass" not in blob


def test_pof_default_uses_aip_width_without_replacing_an_explicit_elsevier_width():
    figure, _, _ = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y", journal="pof")
    assert figure.scientific_metadata["size"] == "aip-single"
    assert figure.scientific_metadata["width_mm"] == 85
    kept, _, _ = render_plot({"x": [0, 1], "y": [1, 2]}, kind="line", x="x", y="y",
                             size="single", journal="pof")
    assert kept.scientific_metadata["width_mm"] == 90
    assert any(item["severity"] == "warn" and item["rule"] == "width" for item in kept.scientific_review)


def test_multipanel_letters_shared_legend_conflict_and_height_cap():
    frame = pd.DataFrame({"x": [0, 1, 2, 0, 1, 2], "y": [1, 2, 1.2, 2, 1, 1.4],
                          "series": ["CFD", "CFD", "CFD", "DNS", "DNS", "DNS"]})
    figure, axes, _ = render_multipanel([
        {"data": frame, "kind": "line", "x": "x", "y": "y", "group": "series"},
        {"data": frame, "kind": "line", "x": "x", "y": "y", "group": "series"},
    ], size="double")
    letters = [text.get_text() for panel in axes for text in panel.texts]
    assert letters == ["(a)", "(b)"]
    assert len(figure.legends) == 1
    assert all(panel.get_legend() is None for panel in figure.axes)
    assert figure.scientific_metadata["width_mm"] == 190
    assert abs(figure.get_size_inches()[0] * 25.4 - 190) < 0.1
    one = pd.DataFrame({"x": [0, 1], "y": [1, 2], "series": ["A", "A"]})
    other = pd.DataFrame({"x": [0, 1], "y": [2, 3], "series": ["A", "A"]})
    with pytest.raises(ValueError, match="different styles"):
        render_multipanel([
            {"data": one, "kind": "line", "x": "x", "y": "y", "group": "series",
             "series_styles": {"A": {"color": "#112233"}}},
            {"data": other, "kind": "line", "x": "x", "y": "y", "group": "series",
             "series_styles": {"A": {"color": "#445566"}}},
        ])
    panels = [{"data": {"x": [0, 1], "y": [1, 2]}, "kind": "line", "x": "x", "y": "y",
               "xlabel": "x", "ylabel": f"p{index}"} for index in range(8)]
    tall, _, _ = render_multipanel(panels, size="single", ncols=1)
    assert tall.scientific_metadata["height_mm"] == 210
    assert any("210" in item["message"] for item in tall.scientific_review)
