"""Native CFD regression gallery; replay needs only this runner, CSVs and template snapshot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cases():
    baseline = load_module(ROOT / "examples/test_cfd_plotting.py", "baseline_data_readers")
    raw = ROOT / "data/cfd_validation/raw"
    dns, provenance = {}, []
    for reynolds in (180, 395):
        dns[reynolds], metadata = baseline.read_dns(raw / baseline.RAW_NAMES[reynolds])
        provenance.append(metadata)
    sparse, metadata = baseline.read_dns(raw / "Poi180_2nd_A.dat")
    provenance.append(metadata)
    cases = []

    def series(label, coordinates, values):
        return pd.DataFrame({"x": coordinates, "y": values, "series": label})

    def add(identifier, frames, source, parameters, **options):
        cases.append({"id": identifier, "frame": pd.concat(frames, ignore_index=True), "source": source,
                      "parameters": parameters, "options": {"kind": "line", "x": "x", "y": "y", "group": "series",
                                                            "group_kind": "categorical", "size": "double", **options}})

    iteration = np.arange(2001)
    add("01_residual_single", [series(label, iteration, amplitude * 10. ** (-iteration / decay)
                                     * (1 + .08 * np.sin(iteration / 37)))
                               for label, amplitude, decay in (("Continuity (synth.)", 1, 210),
                                                               ("x-mom. (synth.)", .3, 240),
                                                               ("y-mom. (synth.)", .1, 270))],
        "Explicit synthetic residuals, not solver output.",
        "n=0..2000; R=A*10**(-n/tau)*(1+0.08*sin(n/37)); (A,tau)=(1,210),(.3,240),(.1,270).",
        size="single", yscale="log", xlabel="Iteration (-)", ylabel="Normalized residual (-)")

    add("02_dns_mixed_double", [series("DNS 180 (4th)", dns[180]["y+"], dns[180]["u_mean"]),
                                series("DNS 180 (2nd)", sparse["y+"], sparse["u_mean"]),
                                series("Viscous law", np.geomspace(.1, 5, 51), np.geomspace(.1, 5, 51))],
        "Cached Kawamura DNS; 4th/2nd denote source discretizations. Viscous law is a theoretical near-wall reference.",
        "All 240 fourth-order and 33 second-order DNS positions retained; law u+=y+ explicitly limited to 0.1<=y+<=5.",
        kind="mixed", xscale="log", xlabel=r"Wall distance, $y^+$", ylabel=r"Mean velocity, $u^+$",
        series_styles={"DNS 180 (4th)": {"kind": "point-line", "marker": "o"},
                       "DNS 180 (2nd)": {"kind": "scatter", "marker": "s"},
                       "Viscous law": {"kind": "line", "linestyle": "--"}})
    add("03_dns_single", [series("DNS 180", dns[180]["y+"], dns[180]["u_mean"]),
                          series("DNS 395", dns[395]["y+"], dns[395]["u_mean"])],
        "Cached Kawamura DNS, original mean-table coordinates.", "Re_tau=180/395; all positions; native line, no markers.",
        size="single", xscale="log", xlabel=r"Wall distance, $y^+$", ylabel=r"Mean velocity, $u^+$")
    shear = baseline.read_dns_table(raw / baseline.RAW_NAMES[395], "-uv+")
    mean = dns[395]
    add("04_dns_staggered", [series(label, table["y+"], table[column]) for label, table, column in
                             (("uu+ (mean grid)", mean, "uu+"), ("ww+ (mean grid)", mean, "ww+"),
                              ("vv+ (shear grid)", shear, "vv+"), ("-uv+ (shear grid)", shear, "-uv+"))],
        "Cached Kawamura Re_tau=395 DNS; normal and shear tables are read independently.",
        "Mean/uu/ww and vv/-uv keep their original staggered y+; no merging, alignment or interpolation.",
        xscale="log", xlabel=r"Wall distance, $y^+$", ylabel="Reynolds stress (+)")

    radius = np.linspace(0, 1, 201)
    exact = 2 * (1 - radius ** 2)
    sample_radius = np.linspace(0, 1, 21)
    random = np.random.default_rng(20261019)
    fine_radius = np.linspace(0, 1, 41)
    pipe = [series("Theory", radius, exact),
            series("Coarse (synth.)", radius, exact * (1 + .002 * radius ** 2)),
            series("Fine (synth.)", fine_radius, 2 * (1 - fine_radius ** 2) * (1 + .0005 * fine_radius ** 2)),
            series("Samples (synth.)", sample_radius, 2 * (1 - sample_radius ** 2)
                   + random.normal(0, .0004, len(sample_radius)) * (1 - sample_radius ** 2))]
    pipe_styles = {"Theory": {"kind": "line", "linestyle": "-"},
                   "Coarse (synth.)": {"kind": "line", "linestyle": "--"},
                   "Fine (synth.)": {"kind": "point-line", "marker": "D", "linestyle": "-."},
                   "Samples (synth.)": {"kind": "scatter", "marker": "^"}}
    pipe_error = {"reference": "Theory", "definition": "signed", "interpolation": "linear"}
    pipe_source = "Hagen-Poiseuille analytic reference plus explicitly synthetic numerical and measurement illustrations."
    pipe_parameters = ("Re_D=1000; u/Ub=2*(1-r**2); synthetic multipliers 1+0.002*r**2 and 1+0.0005*r**2; "
                       "201 theory/coarse, 41 fine and 21 synthetic sample positions (explicit generated grids, no thinning); noise std=.0004*(1-r**2); "
                       "seed=20261019; mismatch uses explicit linear interpolation in data coordinates.")
    for size in ("double", "single"):
        add("05_pipe_error_double" if size == "double" else "06_pipe_error_single", pipe,
            pipe_source, pipe_parameters, kind="mixed", size=size, series_styles=pipe_styles, error=pipe_error,
            xlabel="Radius, r/R", ylabel="Velocity, u/Ub")

    positive_radius = np.linspace(0, .95, 51)
    positive_exact = 2 * (1 - positive_radius ** 2)
    add("07_relative_error", [series("Theory", positive_radius, positive_exact),
                              series("CFD (synth.)", positive_radius, positive_exact * (1 + .002 * positive_radius ** 2))],
        pipe_source, "Explicit generated domain 0<=r/R<=0.95 (no removed rows); relative=(y-ref)/abs(ref); zero policy raise.",
        kind="point-line", error={"reference": "Theory", "definition": "relative"},
        xlabel="Radius, r/R", ylabel="Velocity, u/Ub")
    add("08_absolute_single", [series("Theory", radius, exact),
                               series("CFD (synth.)", radius, exact - .0016 * radius * (1 - radius))],
        pipe_source, "u_synth=u_exact-0.0016*r*(1-r); absolute=abs(y-ref), including zero wall reference.",
        size="single", error={"reference": "Theory", "definition": "absolute"},
        xlabel="Radius, r/R", ylabel="Velocity, u/Ub")
    add("09_source_order", [series("Path (synth.)", [.2, .8, .5, 1, .1, .6], [.2, .7, 1, .3, .5, .1])],
        "Synthetic path demonstrating nonmonotonic source-row connections.", "Original x order: .2,.8,.5,1,.1,.6; no sorting.",
        kind="point-line", size="single", xlabel="x/L (-)", ylabel="y/L (-)")

    long_names = {"Theory": "Hagen-Poiseuille theoretical reference",
                  "Coarse (synth.)": "Coarse-grid numerical illustration (synthetic)",
                  "Fine (synth.)": "Fine-grid numerical illustration (synthetic)",
                  "Samples (synth.)": "Measurement illustration (synthetic)"}
    add("10_long_legend_times", [frame.replace({"series": long_names}) for frame in pipe], pipe_source,
        pipe_parameters + " Times requested; outside legend; explicit per-series sizes 1.8 pt/4 pt where applicable.",
        kind="mixed", font="Times New Roman", legend="outside",
        series_styles={long_names[label]: {**style, **({"line_width": 1.8} if style["kind"] != "scatter" else {}),
                                          **({"marker_size": 4} if style["kind"] != "line" else {})}
                       for label, style in pipe_styles.items()},
        error={**pipe_error, "reference": long_names["Theory"]}, xlabel="Radius, r/R", ylabel="Velocity, u/Ub")
    for size in ("single", "double"):
        add("11_density_single" if size == "single" else "12_density_double",
            [series(label, coordinates, np.exp(-coordinates)) for label, coordinates in
             (("Sparse (synth.)", np.linspace(0, 1, 5)), ("Dense (synth.)", np.linspace(0, 1, 1001)))],
            "Two synthetic samplings of the same function; sparse markers must not inherit dense sizes.",
            "y=exp(-x); 5 and 1001 points; native point-line; every point retained and marked; outside legend.",
            kind="point-line", size=size, legend="outside", xlabel="x/L (-)", ylabel="Signal (-)")
    logarithmic = np.geomspace(.01, 100, 81)
    add("13_loglog_pointline", [series("Synthetic scaling", logarithmic, logarithmic ** -.5)],
        "Explicit synthetic scaling curve, not a physical fit.", "x=geomspace(.01,100,81); y=x**(-.5).",
        kind="point-line", xscale="log", yscale="log", xlabel="x (-)", ylabel="y (-)")
    return cases, provenance


def audit(template, frame, options, figure, axes):
    template._check_text_layout(figure)
    records = []
    for label, subset in frame.groupby("series", sort=False):
        kind = options.get("series_styles", {}).get(label, {}).get("kind", options["kind"])
        pool = axes.collections if kind == "scatter" else axes.lines
        artist = next(artist for artist in pool if artist.get_label() == label)
        if kind == "scatter":
            np.testing.assert_array_equal(np.asarray(artist.get_offsets()), subset[["x", "y"]].to_numpy())
        else:
            np.testing.assert_array_equal(artist.get_xdata(), subset["x"].to_numpy())
            np.testing.assert_array_equal(artist.get_ydata(), subset["y"].to_numpy())
            assert (artist.get_marker() not in (None, "None", "", " ")) == (kind == "point-line")
            assert artist.get_markevery() is None
        records.append({"series": label, "rows": len(subset), "kind": kind})
    for panel in figure.axes:
        assert all(spine.get_visible() for spine in panel.spines.values())
        for axis in (panel.xaxis, panel.yaxis):
            assert all(tick._tickdir == "in" and tick.tick2line.get_visible() for tick in axis.get_major_ticks())
    legend = axes.get_legend()
    box = legend.get_window_extent(figure.canvas.get_renderer())
    points = template._line_vertices(axes)
    assert not np.any((points[:, 0] >= box.x0) & (points[:, 0] <= box.x1) & (points[:, 1] >= box.y0) & (points[:, 1] <= box.y1))
    np.testing.assert_allclose(figure.get_size_inches() * 25.4, template.SIZES_MM[options["size"]])
    return {"series": records, "resolved_font": axes.yaxis.label.get_fontfamily(),
            "legend_sample_hits": 0, "metadata": figure.scientific_metadata}


def contact_sheet(output, filenames, name, grayscale=False):
    sheet = Image.new("RGB", (1440, 565 * ((len(filenames) + 1) // 2)), "white")
    drawing = ImageDraw.Draw(sheet)
    for index, filename in enumerate(filenames):
        with Image.open(output / filename) as source:
            thumbnail = source.convert("L").convert("RGB") if grayscale else source.convert("RGB")
            thumbnail.thumbnail((720, 535), Image.Resampling.LANCZOS)
            left, top = index % 2 * 720, index // 2 * 565
            sheet.paste(thumbnail, (left, top + 30))
            drawing.text((left + 12, top + 8), filename, fill="#222222")
    sheet.save(output / name)


def render_bundle(source, output):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for filename, key in (("plot_template_snapshot.py", "template_sha256"), ("optimization_runner.py", "runner_sha256")):
        if digest(source / filename) != manifest[key]:
            raise ValueError(f"Snapshot checksum mismatch: {filename}")
    template = load_module(source / "plot_template_snapshot.py", "optimization_template")
    output.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        input_path = source / case["input"]
        if digest(input_path) != case["input_sha256"]:
            raise ValueError(f"Input checksum mismatch: {case['input']}")
        frame = pd.read_csv(input_path, float_precision="round_trip")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            figure, axes, _ = template.render_plot(frame, output=output / case["id"], **case["options"])
            try:
                case["audit"] = audit(template, frame, case["options"], figure, axes)
            finally:
                plt.close(figure)
        case["audit"]["warnings"] = sorted({str(item.message) for item in caught})
        with Image.open(output / (case["id"] + ".png")) as image:
            expected = tuple(int(length / 25.4 * 300) for length in template.SIZES_MM[case["options"]["size"]])
            assert image.size == expected
            case["audit"]["pixels"] = list(image.size)
        case["png_sha256"] = digest(output / (case["id"] + ".png"))
        print(f"Verified {case['id']}", flush=True)
    filenames = [case["id"] + ".png" for case in manifest["cases"]]
    contact_sheet(output, filenames[:4], "overview_dns.png")
    contact_sheet(output, filenames[4:10], "overview_errors.png")
    contact_sheet(output, filenames[10:], "overview_density.png")
    contact_sheet(output, [filenames[1], filenames[4], filenames[9], filenames[11]], "review_grayscale.png", grayscale=True)
    (output / "audit.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def verify_replay(bundle):
    filenames = [case["id"] + ".png" for case in json.loads((bundle / "manifest.json").read_text())["cases"]]
    filenames += [path.name for path in bundle.glob("*_metadata.json")]
    filenames += ["overview_dns.png", "overview_errors.png", "overview_density.png", "review_grayscale.png"]
    with tempfile.TemporaryDirectory(prefix="cfd-offline-replay-") as temporary:
        isolated = Path(temporary)
        relocated = isolated / "relocated"
        relocated.mkdir()
        for name in ("manifest.json", "plot_template_snapshot.py", "optimization_runner.py", "reproduce.py"):
            shutil.copy2(bundle / name, relocated / name)
        shutil.copytree(bundle / "data", relocated / "data")
        guard = isolated / "network_guard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text(
            'import socket\n'
            'def refuse_network(*args, **kwargs):\n'
            '    raise RuntimeError("Network disabled during CFD offline verification")\n'
            'socket.socket.connect = refuse_network\n'
            'socket.socket.connect_ex = refuse_network\n'
            'socket.create_connection = refuse_network\n', encoding="utf-8")
        environment = {**os.environ, "PYTHONPATH": str(guard), "MPLBACKEND": "Agg"}
        completed = subprocess.run([sys.executable, str(relocated / "reproduce.py")], cwd=isolated,
                                   env=environment, check=True, capture_output=True, text=True)
        checks = {name: digest(bundle / name) == digest(relocated / name) for name in filenames}
        if not all(checks.values()):
            raise ValueError(f"Replay mismatch: {[name for name, matches in checks.items() if not matches]}")
    return {"network": "socket connect/connect_ex/create_connection disabled in launcher and child",
            "relocated_outside_repository": True, "raw_dns_copied": False, "png_count": len([name for name in filenames if name.endswith('.png')]),
            "all_files_byte_identical": True, "checks": checks, "replay_stdout": completed.stdout.splitlines()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replay", type=Path, help="Offline bundle directory; no raw DNS or repository imports required")
    parser.add_argument("--verify-replay", type=Path, help="Relocate a bundle, disable network and compare regenerated files")
    options = parser.parse_args(argv)
    if options.verify_replay:
        bundle = options.verify_replay.resolve()
        result = verify_replay(bundle)
        (bundle / "replay_verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Offline replay: {len(result['checks'])} files byte-identical", flush=True)
        return result
    if options.replay:
        return render_bundle(options.replay.resolve(), (options.output or options.replay).resolve())
    output = (options.output or ROOT / "figures/cfd_optimization").resolve()
    if output == (ROOT / "figures/cfd_validation").resolve():
        raise ValueError("Refusing to overwrite the baseline validation directory.")
    cases, provenance = build_cases()
    output.mkdir(parents=True, exist_ok=True)
    (output / "data").mkdir(exist_ok=True)
    for case in cases:
        frame = case.pop("frame")
        case["input"] = "data/" + case["id"] + ".csv"
        frame.to_csv(output / case["input"], index=False)
        case["input_sha256"] = digest(output / case["input"])
        (output / "data" / (case["id"] + "_options.json")).write_text(
            json.dumps(case["options"], indent=2) + "\n", encoding="utf-8")
        if "series_styles" in case["options"]:
            (output / "data" / (case["id"] + "_styles.json")).write_text(
                json.dumps(case["options"]["series_styles"], indent=2) + "\n", encoding="utf-8")
    manifest = {"baseline_commit": "4cc1c1c", "seed": 20261019, "provenance": provenance, "cases": cases,
                "versions": {"python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
                             "numpy": np.__version__, "pandas": pd.__version__},
                "notes": "DNS is real Kawamura data; CFD/measurements/residuals explicitly synthetic. No fitting or uncertainty inferred."}
    shutil.copy2(ROOT / "scientific-plotting/scripts/plot_template.py", output / "plot_template_snapshot.py")
    shutil.copy2(__file__, output / "optimization_runner.py")
    manifest["template_sha256"] = digest(output / "plot_template_snapshot.py")
    manifest["runner_sha256"] = digest(output / "optimization_runner.py")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "reproduce.py").write_text(
        'from pathlib import Path\nimport subprocess\nimport sys\n\n'
        'bundle = Path(__file__).resolve().parent\n'
        'subprocess.run([sys.executable, str(bundle / "optimization_runner.py"), "--replay", str(bundle)], check=True)\n',
        encoding="utf-8")
    result = render_bundle(output, output)
    for entry in provenance:
        assert digest(ROOT / "data/cfd_validation/raw" / entry["file"]) == entry["sha256"]
    return result


if __name__ == "__main__":
    main()
