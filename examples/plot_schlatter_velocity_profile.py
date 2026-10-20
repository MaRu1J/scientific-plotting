"""Plot the public KTH DNS profile without fitting or resampling observations."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))
from plot_template import CATEGORICAL_COLORS, render_plot, review_figure


SOURCE = "https://www.mech.kth.se/~pschlatt/DATA/vel_3970_dns.prof"
RAW = ROOT / "data/schlatter_boundary_layer/raw/vel_3970_dns.prof"
OUTPUT = ROOT / "figures/schlatter_boundary_layer"


def main():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not RAW.exists():
        with urlopen(SOURCE, timeout=60) as response:
            RAW.write_bytes(response.read())
    raw_text = RAW.read_text()
    values = np.loadtxt(RAW, comments="%")
    wall_distance, velocity = values[:, 1], values[:, 2]
    if not np.isfinite(values).all() or not np.all(np.diff(wall_distance) > 0):
        raise ValueError("Expected finite data on a strictly increasing native grid.")
    if wall_distance[0] != 0 or velocity[0] != 0:
        raise ValueError("Expected the documented no-slip wall point.")
    positive = wall_distance > 0
    near_wall = wall_distance <= 6
    reynolds = {
        name: float(re.search(r"% " + re.escape(token) + r"\s*=\s*([\d.]+)", raw_text)[1])
        for name, token in (("Re_theta", r"Re_{\theta}"), ("Re_tau", r"Re_{\tau}"))
    }
    blue, orange, green = CATEGORICAL_COLORS[:3]
    figure, axes, _ = render_plot(
        {"y_plus": wall_distance[positive], "U_plus": velocity[positive]},
        kind="point-line", x="y_plus", y="U_plus", xscale="log",
        size="double", font="Arial", marker_size=2.3, line_width=1.25,
        xlabel=r"Wall distance, $y^+ = y u_\tau/\nu$ (dimensionless)",
        ylabel=r"Mean velocity, $U^+ = \overline{U}/u_\tau$ (dimensionless)",
        draw_legend=False,
    )
    figure.subplots_adjust(left=0.13, right=0.96, bottom=0.13, top=0.95)
    dns = axes.lines[0]
    dns.set(color=blue, marker="o", markerfacecolor=blue,
            markeredgecolor=blue, markeredgewidth=0, label="KTH DNS (native samples)")
    axes.set(xlim=(0.025, 4200), ylim=(0, 29))
    axes.set_yticks(np.arange(0, 30, 5))
    linear_x = np.geomspace(wall_distance[positive].min(), 5, 120)
    axes.plot(linear_x, linear_x, "--", color=orange, linewidth=1.5,
              label=r"Viscous reference: $U^+=y^+$", zorder=4)
    log_x = np.geomspace(30, 350, 180)
    axes.plot(log_x, np.log(log_x) / 0.41 + 5.0, "-.", color=green,
              linewidth=1.5, label=r"Log reference: $U^+=\ln(y^+)/0.41+5.0$", zorder=4)
    axes.axvspan(0.025, 5, color=orange, alpha=0.045, linewidth=0)
    axes.axvspan(30, 350, color=green, alpha=0.045, linewidth=0)
    axes.annotate("Viscous sublayer", xy=(2, 2), xytext=(0.12, 8),
                  fontsize=9, color=orange,
                  arrowprops={"arrowstyle": "->", "color": orange, "lw": 0.9})
    axes.annotate("Log-law comparison", xy=(110, np.log(110) / 0.41 + 5),
                  xytext=(14, 21), fontsize=9, color=green,
                  arrowprops={"arrowstyle": "->", "color": green, "lw": 0.9})
    axes.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="0.8",
                framealpha=0.98, fontsize=8.2, handlelength=2.8, borderpad=0.7)
    inset = axes.inset_axes([0.64, 0.13, 0.31, 0.32])
    inset.plot(wall_distance[near_wall], velocity[near_wall], "-o", color=blue,
               markersize=3.1, markeredgecolor="white", markeredgewidth=0.25, lw=1.1)
    inset.plot([0, 6], [0, 6], "--", color=orange, lw=1.2)
    inset.set(xlim=(-0.15, 6.15), ylim=(-0.15, 6.15), xticks=[0, 2, 4, 6], yticks=[0, 2, 4, 6])
    inset.set_xlabel(r"$y^+$ (dimensionless)", fontsize=8, labelpad=1)
    inset.set_ylabel(r"$U^+$ (dimensionless)", fontsize=8, labelpad=1)
    inset.xaxis.set_minor_locator(AutoMinorLocator(2))
    inset.yaxis.set_minor_locator(AutoMinorLocator(2))
    for panel in (axes, inset):
        panel.set_axisbelow(True)
        panel.tick_params(which="both", direction="in", top=True, right=True)
        panel.grid(which="major", color="#cdd2d8", linestyle="--", linewidth=0.55)
        panel.grid(which="minor", color="#e4e7eb", linestyle="--", linewidth=0.4)
    inset.tick_params(labelsize=7.5)
    stem = OUTPUT / "schlatter_mean_velocity_wall_units"
    review_figure(figure)
    figure.savefig(stem.with_suffix(".svg"), facecolor="white")
    figure.savefig(stem.with_suffix(".png"), dpi=600, facecolor="white")
    np.savetxt(OUTPUT / "velocity_profile_wall_units.csv",
               np.column_stack([wall_distance, velocity]), delimiter=",",
               header="y_plus_dimensionless,U_plus_dimensionless", comments="", fmt="%.7f")
    metadata = {
        "source_url": SOURCE,
        "source_landing_page": "https://www.mech.kth.se/~pschlatt/DATA/",
        "citation": "Schlatter, P. & Orlu, R. (2010), J. Fluid Mech. 659, 116-126.",
        "raw_file": str(RAW.relative_to(ROOT)),
        "sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
        "columns_1_based": {"y_plus": 2, "U_plus": 3},
        "units": "dimensionless wall units",
        "reynolds_numbers_from_file_header": reynolds,
        "original_rows": len(values),
        "main_axes_rows": int(positive.sum()),
        "zero_wall_point": "Shown in the linear near-wall inset; undefined on logarithmic main axis.",
        "data_processing": "No sorting, smoothing, fitting or subsampling; native-order connecting lines.",
        "reference_laws": {"linear_y_plus_range": [float(linear_x[0]), 5],
                           "log_y_plus_range": [30, 350], "kappa": 0.41, "B": 5.0,
                           "note": "Illustrative classical reference, not a fitted or inferred log-region extent."},
        "uncertainty": "No mean-velocity uncertainty supplied; RMS columns are fluctuations, not error bars.",
        "export": {"width_mm": 190, "height_mm": 142.5, "png_dpi": 600},
        "software": {"matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "caption_note": stem.name + "_caption.md",
        "canvas_text": "No main/inset titles, descriptive subtitle or source footer; see the external caption note.",
        "style_overrides": "Existing SVG/PNG export and grid settings retained; only titles, subtitle, footer and reserved margins changed.",
    }
    caption = (
        "# Turbulent boundary-layer mean velocity\n\n"
        f"Zero pressure gradient; Re_theta = {reynolds['Re_theta']}; Re_tau = {reynolds['Re_tau']}.\n\n"
        f"Source: {metadata['citation']} KTH public DNS database.\n\n"
        f"Source URL: {SOURCE}\n\n"
        f"{len(values)} original samples; {int(positive.sum())} positive-wall-distance samples on the logarithmic main axes. "
        "The linear near-wall inset includes the origin.\n\n"
        "Native-order samples, without sorting, smoothing, fitting or subsampling. "
        "The viscous and log-law references are illustrative, not fitted to DNS. "
        "No mean-velocity uncertainty was supplied; RMS fluctuations are not uncertainty bars.\n"
    )
    stem.with_name(stem.name + "_caption.md").write_text(caption, encoding="utf-8")
    stem.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    plt.close(figure)
    print(json.dumps(metadata, indent=2))
    print(stem.with_suffix(".svg"))
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
