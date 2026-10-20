import importlib.util
import json
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
import plot_template as template


@pytest.fixture(autouse=True)
def cleanup():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*not installed; using.*")
        yield
    plt.close("all")


def curve(**kwargs):
    return template.render_plot({"x": [3, 1, 2], "y": [2., 1., 1.5]}, kind="line", x="x", y="y", **kwargs)


@pytest.mark.parametrize("position", ["center", "left", "right", "suptitle", "inset"])
def test_titles_added_after_render_are_reviewed_without_removal(position):
    figure, axes, _ = curve()
    if position == "suptitle":
        title = figure.suptitle("Explicit title")
    elif position == "inset":
        title = axes.inset_axes([.5, .1, .3, .3]).set_title("Explicit title")
    else:
        title = axes.set_title("Explicit title", loc=position)
    before = axes.lines[0].get_xydata().copy()
    findings = template.review_figure(figure)
    finding = next(item for item in findings if item["rule"] == "canvas_title")
    assert finding["severity"] == "warn" and finding["category"] == "style"
    assert "Explicit title" in finding["measured"]
    assert title.get_text() == "Explicit title" and title.get_visible()
    np.testing.assert_array_equal(axes.lines[0].get_xydata(), before)


@pytest.mark.parametrize("prefix", ["Source:", "Sources:", "Data source:", "data sources：", "来源：", "数据来源:", "数据源："])
@pytest.mark.parametrize("location", ["figure", "axes", "inset"])
def test_source_text_is_reviewed_without_losing_attribution(prefix, location):
    figure, axes, _ = curve()
    parent = axes.inset_axes([.5, .1, .3, .3]) if location == "inset" else figure if location == "figure" else axes
    source = parent.text(.1, .1, prefix + " Supplied citation")
    finding = next(item for item in template.review_figure(figure) if item["rule"] == "canvas_source")
    assert finding["category"] == "style" and finding["severity"] == "warn"
    assert source.get_text() in finding["measured"]
    assert source.get_visible()


def test_default_plot_labels_annotations_and_hidden_text_do_not_trigger_reminders():
    figure, axes, _ = curve(xlabel="Data source: axis label", ylabel="Source: axis label")
    axes.lines[0].set_label("Source: method identity")
    axes.legend()
    axes.text(.1, .8, "(a)", transform=axes.transAxes)
    axes.annotate("Source term maximum", xy=(2, 1.5))
    axes.annotate("Viscous sublayer", xy=(1, 1))
    axes.set_title("Hidden title").set_visible(False)
    figure.text(.1, .01, "Source: hidden citation", visible=False)
    assert not any(item["rule"] in ("canvas_title", "canvas_source") for item in template.review_figure(figure))


def test_report_preserves_style_category_and_keeps_explicit_title(tmp_path, monkeypatch):
    export = template._export_figure

    def add_footer(figure, *args, **kwargs):
        figure.text(.1, .01, "Source: Supplied citation")
        return export(figure, *args, **kwargs)

    monkeypatch.setattr(template, "_export_figure", add_footer)
    figure, axes, paths = curve(title="User-requested title", report=True, output=tmp_path / "figure")
    report = json.loads(figure.scientific_report_paths[0].read_text())
    findings = [item for item in report["findings"] if item["rule"] in ("canvas_title", "canvas_source")]
    assert len(findings) == 2 and all(item["category"] == "style" for item in findings)
    assert axes.get_title() == "User-requested title"
    assert paths == [tmp_path / "figure.jpg"] and paths[0].is_file()
    markdown = figure.scientific_report_paths[1].read_text()
    assert "style/canvas_title" in markdown and "style/canvas_source" in markdown


def test_panel_letters_and_shared_legend_are_not_titles():
    data = pd.DataFrame({"x": [1, 2], "y": [2, 3]})
    figure, _, _ = template.render_multipanel([
        {"kind": "line", "data": data, "x": "x", "y": "y"},
        {"kind": "line", "data": data, "x": "x", "y": "y"},
    ])
    assert not any(item["rule"] in ("canvas_title", "canvas_source") for item in template.review_figure(figure))


def test_schlatter_example_moves_titles_and_provenance_outside_canvas(tmp_path, monkeypatch, capsys):
    specification = importlib.util.spec_from_file_location("schlatter_example", ROOT / "examples" / "plot_schlatter_velocity_profile.py")
    example = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(example)
    raw = tmp_path / "data" / "profile.prof"
    raw.parent.mkdir()
    raw.write_text("% Re_{\\theta} = 3969.154\n% Re_{\\tau} = 1244.7742\n"
                   "0 0 0\n0.01 0.5 0.5\n0.1 5 4.5\n0.9 100 15\n", encoding="utf-8")
    monkeypatch.setattr(example, "ROOT", tmp_path)
    monkeypatch.setattr(example, "RAW", raw)
    monkeypatch.setattr(example, "OUTPUT", tmp_path / "figures")
    monkeypatch.setattr(example, "urlopen", lambda *args, **kwargs: pytest.fail("Cached test input must not access network"))
    captured = []

    def review(figure):
        captured.append(figure)
        return template.review_figure(figure)

    monkeypatch.setattr(example, "review_figure", review)
    example.main()
    capsys.readouterr()
    figure = captured[0]
    assert not figure.texts
    assert all(not axes.get_title() for axes in template._all_axes(figure))
    assert not any(item["rule"] in ("canvas_title", "canvas_source") for item in figure.scientific_review)
    np.testing.assert_array_equal(figure.axes[0].lines[0].get_xdata(), [.5, 5, 100])
    np.testing.assert_array_equal(figure.axes[0].child_axes[0].lines[0].get_xdata(), [0, .5, 5])
    stem = example.OUTPUT / "schlatter_mean_velocity_wall_units"
    metadata = json.loads(stem.with_suffix(".json").read_text())
    caption = (example.OUTPUT / metadata["caption_note"]).read_text()
    assert example.SOURCE in caption and metadata["citation"] in caption
    assert "4 original samples" in caption and "3969.154" in caption
    assert "near-wall inset includes the origin" in caption
    assert stem.with_suffix(".png").is_file() and stem.with_suffix(".svg").is_file()
    assert figure.subplotpars.top == .95 and figure.subplotpars.bottom == .13
