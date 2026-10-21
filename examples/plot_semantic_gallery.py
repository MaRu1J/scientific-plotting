"""Synthetic demonstrations only; no measurements are recovered from the reference image."""

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))

from plot_template import PALETTES, _srgb_to_oklab, render_multipanel, render_plot


CVD_SOURCE = "https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html"
CVD_MATRICES = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                           [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                             [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                           [0.004733, 0.691367, 0.303900]]),
}


def simulate_rgb(rgb, mode):
    channels = np.asarray(rgb, dtype=float)
    linear = np.where(channels <= 0.04045, channels / 12.92, ((channels + 0.055) / 1.055) ** 2.4)
    if mode == "grayscale":
        luminance = linear @ np.array([0.2126, 0.7152, 0.0722])
        simulated = np.repeat(luminance[..., None], 3, axis=-1)
    elif mode in CVD_MATRICES:
        simulated = linear @ CVD_MATRICES[mode].T
    else:
        raise ValueError("Unknown vision-preview mode.")
    clipped = np.clip(simulated, 0, 1)
    return np.where(clipped <= 0.0031308, clipped * 12.92, 1.055 * clipped ** (1 / 2.4) - 0.055)


def palette_diagnostics():
    diagnostics = {}
    for name, shades in PALETTES.items():
        channels = np.array([to_rgb(shade) for shade in shades])
        linear = np.where(channels <= 0.04045, channels / 12.92, ((channels + 0.055) / 1.055) ** 2.4)
        contrast = 1.05 / (linear @ np.array([0.2126, 0.7152, 0.0722]) + 0.05)
        lab = np.array([_srgb_to_oklab(shade) for shade in shades])
        distances = np.linalg.norm(lab[:, None] - lab[None, :], axis=-1)
        np.fill_diagonal(distances, np.inf)
        diagnostics[name] = {"colors": list(shades), "minimum_white_contrast": float(contrast.min()),
                             "minimum_oklab_distance": float(distances.min())}
    return {"scope": "Heuristic screen, not a color-vision or journal certification; focus background colors intentionally repeat.",
            "cvd_model": "Machado, Oliveira and Fernandes (2009), severity 1.0 matrices applied to linear sRGB; out-of-gamut values clipped.",
            "source": CVD_SOURCE, "palettes": diagnostics}


def synthetic_data():
    records = []
    materials = ["A", "B", "C", "D"]
    for condition in range(3):
        for index, material in enumerate(materials):
            coordinates = np.linspace(0, 10, 11)
            height = 1 + (0.006 + 0.004 * index) * coordinates + (0.004 + 0.002 * condition) * np.maximum(coordinates - 7, 0) ** 2
            angle = 72 + 16 * index - (0.35 + 0.22 * condition + 0.15 * index) * coordinates - 1.0 * np.maximum(coordinates - 7, 0) ** 2
            for metric, values, uncertainty in (("Height", height, 0.012), ("Angle", angle, 1.1)):
                for coordinate, measurement in zip(coordinates, values):
                    records.append({"field": coordinate, "value": measurement, "condition": condition + 1,
                                    "material": material, "metric": metric, "series": f"{material} {metric}", "sd": uncertainty})
    encoding = {"categories": {material: {} for material in materials},
                "metrics": {"Height": {"fillstyle": "full", "quantity": "relative height", "unit": "-"},
                            "Angle": {"fillstyle": "none", "linestyle": "--", "quantity": "contact angle", "unit": "deg"}},
                "series": {f"{material} {metric}": {"category": material, "metric": metric}
                           for material in materials for metric in ("Height", "Angle")},
                "category_label": "Material", "metric_label": "Metric",
                "reason": "Synthetic demonstration: material identity is stable across metrics and conditions; not experimental evidence."}
    return pd.DataFrame(records), encoding


def make_gallery(output: Path):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh/empty gallery output directory; existing bundles and figures are not overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    frame, encoding = synthetic_data()
    base = {"kind": "point-line", "x": "field", "y": "value", "group": "series", "xlabel": "E (kV/cm)"}
    height_data = frame[(frame.condition == 1) & (frame.metric == "Height")]
    registry = {f"{material} Height": {} for material in encoding["categories"]}
    palette_panels = [{**base, "data": height_data, "palette": palette, "ylabel": "h/h_0 (-)",
                       **({"focus": "B Height"} if palette == "focus" else {})} for palette in PALETTES]
    figure, _, _ = render_multipanel(palette_panels, size="double", ncols=2, height_mm=165, legend="each",
                                      style_registry=registry, output=output / "palette_comparison", report=True)
    plt.close(figure)
    panels = []
    for metric, ylabel in (("Height", "h/h_0 (-)"), ("Angle", "CA (deg)")):
        for condition in (1, 2, 3):
            panels.append({**base, "data": frame[(frame.condition == condition) & (frame.metric == metric)],
                           "ylabel": ylabel})
    figure, _, _ = render_multipanel(panels, ncols=3, size="double", height_mm=175, sharex=True,
                                      encoding=encoding, palette="jewel", output=output / "multivariable_facets", report=True)
    plt.close(figure)
    dual = {"series": [f"{material} Angle" for material in encoding["categories"]],
            "label": "CA (deg)", "quantity": "contact angle", "unit": "deg", "limits": [45, 130],
            "primary": {"quantity": "relative height", "unit": "-", "limits": [0.95, 1.4]},
            "reason": "Synthetic compact-layout comparison only; fixed limits cover all conditions and supplied SD. Independent scales do not establish correlation."}
    selected = frame[frame.condition == 1]
    figure, _, _ = render_plot(selected, **base, ylabel="h/h_0 (-)", secondary_y=dual, encoding=encoding,
                                palette="jewel", size="medium", output=output / "dual_axis",
                                error_bars={"y": "sd", "definition": "Synthetic supplied SD, each metric's axis units; not measured uncertainty"},
                                report=True, bundle=output / "dual_axis_bundle", include_data=True)
    plt.close(figure)
    dual_panels = [{**base, "data": frame[frame.condition == condition], "ylabel": "h/h_0 (-)", "secondary_y": dual}
                   for condition in (1, 2, 3)]
    figure, _, _ = render_multipanel(dual_panels, ncols=1, size="double", height_mm=210, sharex=True,
                                      encoding=encoding, palette="jewel", output=output / "dual_axis_conditions", report=True)
    plt.close(figure)
    with Image.open(output / "palette_comparison.jpg") as image:
        rgb = np.array(image.convert("RGB"), dtype=float) / 255
    for mode in ("grayscale", *CVD_MATRICES):
        pixels = np.rint(simulate_rgb(rgb, mode) * 255).astype(np.uint8)
        Image.fromarray(pixels).save(output / f"palette_comparison_{mode}.jpg", quality=95, dpi=(300, 300))
    (output / "palette_diagnostics.json").write_text(json.dumps(palette_diagnostics(), indent=2) + "\n", encoding="utf-8")
    (output / "synthetic_caption_notes.txt").write_text(
        "全部曲线及 SD 均为公式构造的合成示例，不是附件数字化、论文复现或真实实验。\n"
        "palette_comparison: (a) classic; (b) jewel; (c) muted; (d) focus, B is explicitly emphasized.\n"
        "multivariable_facets: (a–c) height at conditions 1–3; (d–f) angle at conditions 1–3. "
        "Materials retain their colors and markers; filled=height, hollow/dashed=angle. "
        "Each row uses separate metric units; autoscaled y ranges are visible, not asserted identical.\n"
        "dual_axis: condition 1; left=relative height (-), right=contact angle (deg). "
        "Both axes have deliberately fixed limits covering every condition; intersections are not equality or correlation.\n"
        "dual_axis_conditions: (a–c) conditions 1–3; one primary grid per panel, same explicit limits across conditions.\n"
        "*_grayscale/protanopia/deuteranopia/tritanopia.jpg are derived vision previews only, not new observations. "
        "CVD previews use the Machado et al. (2009) severity 1.0 model; clipping is part of the preview, not an accessibility certification.\n",
        encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "figures" / "semantic_gallery")
    arguments = parser.parse_args()
    print(make_gallery(arguments.output))
