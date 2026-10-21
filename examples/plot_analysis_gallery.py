"""Synthetic quantitative-analysis examples; not CFD or experimental evidence."""

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))
from plot_template import render_multipanel, render_plot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "figures" / "analysis_gallery")
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=False)
    random = np.random.default_rng(20261021)
    populations = []
    for label, spread, correlation in (("Case A", 1., .65), ("Case B", .7, .25)):
        velocity = random.normal(0, spread, 1200)
        temperature = correlation * velocity + random.normal(0, .65, len(velocity))
        populations.append(pd.DataFrame({"velocity": velocity, "temperature": temperature,
                                         "volume": random.uniform(.5, 1.5, len(velocity)), "case": label}))
    samples = pd.concat(populations, ignore_index=True)
    velocity_edges = np.linspace(samples.velocity.min(), samples.velocity.max(), 26).tolist()
    temperature_edges = np.linspace(samples.temperature.min(), samples.temperature.max(), 26).tolist()
    weighted = {"weight": "volume", "weight_definition": "Synthetic positive cell-volume weights (arbitrary units)"}
    phase = np.linspace(0, 2 * np.pi, 100)
    trajectories = pd.concat([
        pd.DataFrame({"input": np.sin(phase), "response": np.sin(phase - lag), "time": phase, "case": label})
        for label, lag in (("Case A", .6), ("Case B", .25))], ignore_index=True)
    contributions = pd.DataFrame({"term": ["Source", "Transport", "Sink"] * 2,
                                   "value": [1., -.25, -.7, .8, -.1, -.65],
                                   "case": ["Case A"] * 3 + ["Case B"] * 3})
    panels = [
        {"kind": "histogram", "data": samples, "x": "velocity", "group": "case",
         "analysis": {"bins": velocity_edges, "statistic": "density", **weighted},
         "xlabel": r"$u'/U_b$", "ylabel": "Weighted probability density"},
        {"kind": "ecdf", "data": samples, "x": "velocity", "group": "case", "analysis": weighted,
         "xlabel": r"$u'/U_b$", "ylabel": "Cumulative probability (-)"},
        {"kind": "box", "data": samples, "x": "velocity", "group": "case", "analysis": {"whis": 1.5},
         "xlabel": "Case (unweighted samples)", "ylabel": r"$u'/U_b$"},
        {"kind": "joint", "data": populations[0], "x": "velocity", "y": "temperature",
         "analysis": {"bins": [velocity_edges, temperature_edges], "statistic": "density", **weighted},
         "xlabel": r"$u'/U_b$", "ylabel": r"$T'/T_{ref}$"},
        {"kind": "trajectory", "data": trajectories, "x": "input", "y": "response", "group": "case",
         "analysis": {"order": "time", "arrows": [10, 45, 75]},
         "xlabel": "Input (-)", "ylabel": "Response (-)"},
        {"kind": "contribution", "data": contributions, "x": "term", "y": "value", "group": "case",
         "analysis": {"definition": "Synthetic supplied terms: positive adds, negative removes; not a solved physical budget."},
         "xlabel": "Supplied term", "ylabel": "Signed contribution (-)"},
    ]
    for panel in panels:
        figure, _, paths = render_plot(**panel, output=options.output / panel["kind"], dpi=180, report=True)
        print(paths[0])
        plt.close(figure)
    figure, _, paths = render_multipanel(panels, ncols=2, height_mm=210, legend="shared",
                                         output=options.output / "gallery", dpi=180, report=True)
    print(paths[0])
    plt.close(figure)
    densities = [np.histogram2d(population.velocity, population.temperature, bins=[velocity_edges, temperature_edges],
                                weights=population.volume, density=True)[0] for population in populations]
    shared_maximum = float(max(density.max() for density in densities))
    joint_panels = [{**panels[3], "data": population,
                     "analysis": {**panels[3]["analysis"], "vmax": shared_maximum * 1.001}}
                    for population in populations]
    figure, _, paths = render_multipanel(joint_panels, ncols=2, height_mm=95, legend="none",
                                         output=options.output / "joint_comparison", dpi=180, report=True)
    print(paths[0])
    plt.close(figure)
    samples.to_csv(options.output / "synthetic_samples.csv", index=False)
    trajectories.to_csv(options.output / "synthetic_trajectories.csv", index=False)
    contributions.to_csv(options.output / "synthetic_contributions.csv", index=False)
    (options.output / "caption_notes.txt").write_text(
        "ALL DATA ARE SYNTHETIC. Not a CFD calculation, experiment, validation or physical conclusion.\n"
        "Gallery: (a) volume-weighted histogram; (b) weighted ECDF; (c) unweighted box plot, all fliers;\n"
        "(d) Case A weighted joint density; (e) supplied parametric paths, start circles, explicit direction arrows;\n"
        "(f) supplied signed terms, no percentages or automatic closure claim.\n"
        "Histogram groups share edges and each density integrates to one. Box plots do not use volume weights.\n"
        "Joint comparison: (a) Case A, (b) Case B; identical physical bin edges and color limits;\n"
        "common color maximum is the maximum of both explicitly computed binned densities, expanded by 0.1%.\n"
        "Density units are inverse sample units (joint: inverse product); these example samples are dimensionless.\n"
        "Distribution samples are synthetic independent draws, not a time series; no confidence interval is inferred.\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
