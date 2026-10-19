"""Synthetic plotting demonstrations, not solver validation or measured benchmarks."""

import argparse
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))

from plot_template import render_multipanel, render_plot


REGISTRY = {
    "Baseline": {"color": "#2F6DB5", "marker": "o", "linestyle": "-"},
    "Candidate": {"color": "#D35400", "marker": "s", "linestyle": "--"},
}


def generate(output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = []

    def save(renderer, *args, name: str, **kwargs):
        figure, _, exported = renderer(*args, output=output / name, **kwargs)
        paths.extend(exported)
        plt.close(figure)

    spacing = np.array([0.2, 0.1, 0.05, 0.025])
    convergence = pd.DataFrame({
        "spacing": np.tile(spacing, 2),
        "error": [0.045, 0.0118, 0.0031, 0.00081, 0.028, 0.0072, 0.00185, 0.00047],
        "method": np.repeat(["Baseline", "Candidate"], 4),
        "wall_time": [1.4, 9.2, 65, 490, 1.1, 6.8, 48, 350],
    })
    save(render_plot, convergence, name="synthetic_convergence", kind="point-line", x="spacing", y="error",
         group="method", style_registry=REGISTRY, xscale="log", yscale="log", size="double",
         xlabel="Particle spacing (m)", ylabel="Supplied error (-)",
         reference_guides=[{"kind": "power", "order": 2, "anchor": [0.1, 0.004],
                            "range": [0.025, 0.2], "label": "$h^2$ reference (explicit)"}])
    save(render_plot, convergence.iloc[::-1], name="synthetic_accuracy_cost", kind="point-line",
         x="wall_time", y="error", group="method", style_registry=REGISTRY,
         xscale="log", yscale="log", size="double",
         xlabel="Synthetic wall time (s)", ylabel="Supplied error (-)")

    positions = np.linspace(0, 1, 41)
    profile = 1 + 0.12 * np.sin(np.pi * positions)
    comparison = pd.DataFrame({"x": np.tile(positions, 2),
                               "pressure": np.concatenate([profile, profile + 0.004 * np.sin(6 * positions)]),
                               "method": np.repeat(["Baseline", "Candidate"], len(positions))})
    save(render_plot, comparison, name="synthetic_profile_zoom", kind="point-line", x="x", y="pressure",
         group="method", style_registry=REGISTRY, size="double", xlabel="Position (m)", ylabel="Pressure ratio (-)",
         inset={"xlim": [0.35, 0.65], "ylim": [1.105, 1.125], "bounds": [0.32, 0.12, 0.4, 0.32]})

    method_resolution_registry = {
        "Baseline, h=0.10": {"color": "#2F6DB5", "marker": "o", "linestyle": "-"},
        "Baseline, h=0.05": {"color": "#2F6DB5", "marker": "s", "linestyle": "--"},
        "Candidate, h=0.10": {"color": "#D35400", "marker": "o", "linestyle": "-"},
        "Candidate, h=0.05": {"color": "#D35400", "marker": "s", "linestyle": "--"},
    }
    resolution_profiles = pd.concat([
        pd.DataFrame({"x": positions, "pressure": profile + offset * np.sin(6 * positions), "series": label})
        for label, offset in zip(method_resolution_registry, [0.012, 0.006, 0.008, 0.004])
    ], ignore_index=True)
    save(render_plot, resolution_profiles, name="synthetic_method_resolution", kind="point-line",
         x="x", y="pressure", group="series", style_registry=method_resolution_registry,
         size="double", legend="outside", xlabel="Position (m)", ylabel="Pressure ratio (-)")

    iteration = np.arange(0, 101, 5)
    histories = pd.DataFrame({"iteration": np.tile(iteration, 2),
                              "residual": np.concatenate([np.exp(-0.12 * iteration), np.exp(-0.17 * iteration)]),
                              "method": np.repeat(["Baseline", "Candidate"], len(iteration))})
    save(render_multipanel, [
        {"id": "residual", "data": histories, "kind": "line", "x": "iteration", "y": "residual",
         "group": "method", "yscale": "log", "xlabel": "Iteration (-)", "ylabel": "Supplied residual (-)",
         "reference_guides": [{"kind": "constant", "axis": "y", "value": 1e-6, "label": "Explicit tolerance"}]},
        {"id": "accuracy", "data": convergence, "kind": "line", "x": "spacing", "y": "error",
         "group": "method", "xscale": "log", "yscale": "log", "xlabel": "Spacing (m)", "ylabel": "Supplied error (-)"},
        {"id": "cost", "data": convergence, "kind": "line", "x": "wall_time", "y": "error",
         "group": "method", "xscale": "log", "yscale": "log", "xlabel": "Synthetic time (s)", "ylabel": "Supplied error (-)"},
    ], name="synthetic_validation_panels", layout=[["residual", "residual"], ["accuracy", "cost"]],
         style_registry=REGISTRY, size="double", height_mm=155)

    matrix = np.array([[1., 1.2, 1.5, 1.8], [1.3, 1.6, 1.9, 2.1], [1.5, 1.8, 2.2, 2.5]])
    save(render_multipanel, [
        {"id": "baseline", "data": matrix, "kind": "heatmap", "quantity": "pressure", "unit": "Pa",
         "xlabel": "Column (-)", "ylabel": "Row (-)"},
        {"id": "candidate", "data": matrix + 0.15, "kind": "heatmap", "quantity": "pressure", "unit": "Pa",
         "xlabel": "Column (-)", "ylabel": "Row (-)"},
    ], name="synthetic_shared_colorbar", shared_colorbar={"vmin": 1, "vmax": 3, "label": "Pressure (Pa)"},
         size="double", height_mm=85)
    (output / "synthetic_caption_notes.txt").write_text(
        "All figures use synthetic data for plotting demonstrations only. No solver or paper is reproduced.\n"
        "Convergence: errors are supplied synthetic values; p=2 is explicitly chosen, not fitted.\n"
        "Cost: times are invented, not measured. Hardware and problem size are unspecified; "
        "no benchmark or speedup claim is justified.\n"
        "Profiles: methods and resolutions are illustrative labels, not actual simulation runs.\n"
        "Panels: residuals are synthetic; the tolerance is supplied explicitly.\n"
        "Heatmaps: panels (a)/(b) are synthetic baseline/candidate pressure matrices on one explicit scale.\n",
        encoding="utf-8",
    )
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "figures" / "algorithm_comparisons")
    options = parser.parse_args()
    for path in generate(options.output):
        print(path)
    print("Synthetic examples only; see synthetic_caption_notes.txt for limitations.")
