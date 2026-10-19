"""Reproducible CFD-oriented exercise of the scientific plotting template."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import LogFormatterSciNotation, LogLocator
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://www.rs.tus.ac.jp/~t2lab/db/poi/poi.html"
RAW_NAMES = {
    180: "Poi180_4th_E.dat",
    395: "Poi395_4th_D.dat",
    640: "Poi640_4th_B.dat",
    1020: "Poi1020_4th_A_ver2.dat",
}
SEED = 20261019


def load_template(path: Path):
    spec = importlib.util.spec_from_file_location("cfd_plot_template", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_dns_table(path: Path, required: str) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    for index, line in enumerate(lines):
        tokens = line.split()
        if tokens[:2] != ["j", "y+"] or required not in tokens:
            continue
        rows = []
        for candidate in lines[index + 1:]:
            entries = candidate.split()
            if len(entries) != len(tokens):
                break
            try:
                rows.append([float(entry.replace("D", "E")) for entry in entries])
            except ValueError:
                break
        if not rows:
            raise ValueError(f"Empty DNS table in {path.name}")
        frame = pd.DataFrame(rows, columns=tokens)
        if not np.isfinite(frame.to_numpy(dtype=float)).all() or not (np.diff(frame["y+"]) > 0).all():
            raise ValueError("DNS coordinates must be finite and strictly increasing in source order")
        if frame["j"].duplicated().any():
            raise ValueError("DNS table contains repeated row indices")
        return frame
    raise ValueError(f"Missing DNS table {required} in {path.name}")


def read_dns(path: Path) -> tuple[pd.DataFrame, dict]:
    text = path.read_text(encoding="utf-8", errors="strict")
    frame = read_dns_table(path, "u_mean")
    shear = read_dns_table(path, "-uv+")
    reynolds_tau = re.search(r"^\s*Re_tau\s*=\s*(\d+(?:\.\d+)?)\s*$", text, re.MULTILINE)
    reynolds_bulk = re.search(r"^\s*Re_bulk\s*=\s*(\d+(?:\.\d+)?)\s*$", text, re.MULTILINE)
    if reynolds_tau is None or reynolds_bulk is None:
        raise ValueError("DNS normalization requires numeric Re_tau and Re_bulk")
    metadata = {
        "file": path.name,
        "url": SOURCE_URL.rsplit("/", 1)[0] + "/text/" + path.name,
        "Re_tau": float(reynolds_tau[1]),
        "Re_bulk": float(reynolds_bulk[1]),
        "rows": len(frame),
        "shear_rows": len(shear),
        "staggered_mean_and_shear_grids": not np.array_equal(frame["y+"], shear["y+"]),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    frame["y_over_h"] = frame["y+"] / metadata["Re_tau"]
    frame["u_over_ub"] = frame["u_mean"] / (metadata["Re_bulk"] / (2 * metadata["Re_tau"]))
    return frame, metadata


def blasius_profile(step: float = 0.01, maximum: float = 10.0) -> tuple[np.ndarray, np.ndarray, float]:
    eta = np.linspace(0, maximum, round(maximum / step) + 1)
    step = float(eta[1] - eta[0])

    def integrate(curvature: float) -> np.ndarray:
        solution = np.empty((len(eta), 3))
        solution[0] = (0, 0, curvature)

        def derivative(state: np.ndarray) -> np.ndarray:
            return np.array([state[1], state[2], -0.5 * state[0] * state[2]])

        for index in range(len(eta) - 1):
            current = solution[index]
            stage_one = derivative(current)
            stage_two = derivative(current + step * stage_one / 2)
            stage_three = derivative(current + step * stage_two / 2)
            stage_four = derivative(current + step * stage_three)
            solution[index + 1] = current + step * (stage_one + 2 * stage_two + 2 * stage_three + stage_four) / 6
        return solution

    lower, upper = 0.3, 0.4
    for _ in range(38):
        curvature = (lower + upper) / 2
        solution = integrate(curvature)
        if solution[-1, 1] < 1:
            lower = curvature
        else:
            upper = curvature
    curvature = (lower + upper) / 2
    return eta, integrate(curvature)[:, 1], curvature


def series_frame(coordinates: np.ndarray, values: list[tuple[str | int, np.ndarray]]) -> pd.DataFrame:
    return pd.concat([pd.DataFrame({"x": coordinates, "y": observations, "series": label})
                      for label, observations in values], ignore_index=True)


def build_cases(raw_dir: Path) -> tuple[list[dict], list[dict], dict]:
    random = np.random.default_rng(SEED)
    profiles, provenance = {}, []
    for reynolds, filename in RAW_NAMES.items():
        profiles[reynolds], metadata = read_dns(raw_dir / filename)
        provenance.append(metadata)
    second_order, metadata = read_dns(raw_dir / "Poi180_2nd_A.dat")
    provenance.append(metadata)
    cases = []

    def add(identifier: str, kind: str, frame: pd.DataFrame, title: str, xlabel: str, ylabel: str,
            source: str, meaning: str, parameters: str, *, group_kind: str = "categorical",
            scale: str = "linear", overlay: pd.DataFrame | None = None) -> None:
        cases.append({"id": identifier, "kind": kind, "frame": frame, "title": title,
                      "xlabel": xlabel, "ylabel": ylabel, "source": source, "meaning": meaning,
                      "parameters": parameters, "group_kind": group_kind, "scale": scale,
                      "overlay": overlay})

    iteration = np.arange(0, 2001, dtype=float)
    residual = series_frame(iteration, [
        ("Continuity", 10 ** (-1 - iteration / 300) * (1 + 0.12 * np.sin(iteration / 70))),
        ("x-momentum", 10 ** (-2 - iteration / 285) * (1 + 0.08 * np.sin(iteration / 63))),
        ("y-momentum", 10 ** (-2.4 - iteration / 270) * (1 + 0.10 * np.sin(iteration / 59))),
    ])
    add("A01_line_residual", "line", residual, "Residual convergence [synthetic]", "Iteration",
        "Normalized residual (-)", "人为构造的残差序列，不是求解器输出。",
        "连续性和两个动量方程的归一化残差，测试跨数量级收敛。",
        "迭代 0–2000，步长 1；R=A*10^(-n/tau)*(1+a*sin(n/b))；纵轴 log。", scale="logy")

    inner = pd.concat([pd.DataFrame({"x": profile["y+"], "y": profile["u_mean"], "series": reynolds})
                       for reynolds, profile in profiles.items()], ignore_index=True)
    add("A02_line_dns_inner", "line", inner, "Channel DNS: inner scaling", "Wall distance, y+",
        "Mean velocity, u+", "Kawamura Lab：" + ", ".join(RAW_NAMES.values()),
        "充分发展湍流平面通道流的半通道均值速度内尺度剖面。",
        "Re_tau=180/395/640/1020；原始全部测点；横轴 log，y+>0，无补壁面点。",
        group_kind="ordered", scale="logx")

    radius = np.linspace(0, 1, 201)
    pipe_exact = 2 * (1 - radius ** 2)
    pipe_coarse = pipe_exact * (1 + 0.025 * radius ** 2)
    pipe_fine = pipe_exact * (1 + 0.00625 * radius ** 2)
    pipe_dense = series_frame(radius, [("Exact", pipe_exact), ("Coarse (synth.)", pipe_coarse),
                                       ("Fine (synth.)", pipe_fine)])
    add("A03_line_pipe", "line", pipe_dense, "Pipe profile: theory vs synthetic CFD", "Radius, r/R",
        "Axial velocity, u/Ub", "Hagen–Poiseuille 解析解 + 明确构造的两组数值示意结果。",
        "不可压缩、充分发展层流圆管轴向速度；不是湍流平面通道的解析解。",
        "Re_D=1000；u/Ub=2[1-(r/R)^2]；偏差乘子 1+0.025(r/R)^2 和 1+0.00625(r/R)^2。")

    eta, velocity, curvature = blasius_profile()
    blasius_coarse = velocity - 0.025 * eta * np.exp(-eta / 1.5)
    blasius_fine = velocity - 0.00625 * eta * np.exp(-eta / 1.5)
    boundary_dense = series_frame(eta, [("Blasius", velocity), ("Coarse (synth.)", blasius_coarse),
                                       ("Fine (synth.)", blasius_fine)])
    add("A04_line_blasius", "line", boundary_dense, "Blasius profile vs synthetic CFD", "Similarity coordinate, eta",
        "Velocity, u/U_inf", "Blasius 相似性方程数值求解的理论参考曲线 + 合成数值偏差。",
        "零压梯度层流平板边界层；Blasius 没有在此被冒称为闭式解析公式。",
        f"f'''+0.5*f*f''=0；f(0)=f'(0)=0，f'(10)=1；RK4+二分打靶，deta=0.01；f''(0)={curvature:.10f}。")

    stress_profile = profiles[395]
    shear_profile = read_dns_table(raw_dir / RAW_NAMES[395], "-uv+")
    stresses = pd.concat([
        series_frame(stress_profile["y_over_h"].to_numpy(), [
            ("uu", stress_profile["uu+"].to_numpy()), ("ww", stress_profile["ww+"].to_numpy())]),
        series_frame(shear_profile["y+"].to_numpy() / 395, [
            ("vv", shear_profile["vv+"].to_numpy()), ("-uv", shear_profile["-uv+"].to_numpy())]),
    ], ignore_index=True)
    add("A05_line_dns_stresses", "line", stresses, "Channel DNS: Reynolds stresses", "Wall distance, y/h",
        "Reynolds stress / u_tau^2", "Kawamura Lab：Poi395_4th_D.dat 的均值表与剪切应力表。",
        "三个法向雷诺应力及负雷诺剪切应力；不是速度 RMS。",
        "Re_tau=395；均值/uu/ww 与 vv/-uv 是交错网格，分别保留各表原始 y+；y/h=y+/Re_tau；不插值合并。")

    time = np.linspace(0, 40, 81)
    lift_base = 0.32 * (1 - np.exp(-time / 6)) * np.sin(2 * np.pi * 0.165 * time)
    lift_cfd = 0.312 * (1 - np.exp(-time / 6.3)) * np.sin(2 * np.pi * 0.165 * time + 0.035)
    lift_measurements = lift_base + random.normal(0, 0.007, len(time))
    lift = series_frame(time, [("Reference (synth.)", lift_base), ("CFD (synth.)", lift_cfd),
                              ("Samples (synth.)", lift_measurements)])
    add("B01_pointline_lift", "point-line", lift, "Cylinder lift history [synthetic]", "Dimensionless time, tU/D",
        "Lift coefficient, Cl", "合成圆柱涡脱落式时间信号；包括合成参考和合成测量点，无真实实验。",
        "启动后趋于周期振荡的升力时间历程。所有组均同时画点和连线。",
        "示意 Re_D=100；St=0.165；tU/D=0–40，dt=0.5；噪声标准差 0.007；seed=20261019。")

    schemes = pd.concat([
        pd.DataFrame({"x": second_order["y_over_h"], "y": second_order["u_over_ub"], "series": "2nd-order DNS"}),
        pd.DataFrame({"x": profiles[180]["y_over_h"], "y": profiles[180]["u_over_ub"], "series": "4th-order DNS"}),
    ], ignore_index=True)
    add("B02_pointline_dns_schemes", "point-line", schemes, "Channel DNS: two datasets", "Wall distance, y/h",
        "Mean velocity, u/Ub", "Kawamura Lab：Poi180_2nd_A.dat、Poi180_4th_E.dat，均为真实 DNS。",
        "不同分辨率及离散方法数据的空间剖面对比；不能据此单独归因于离散阶数。",
        "Re_tau=180；Re_bulk=5692/5665；Ub+=Re_bulk/(2*Re_tau)；保留两套原网格，不插值对齐。")

    outer = pd.concat([pd.DataFrame({"x": profile["y_over_h"], "y": profile["u_over_ub"], "series": reynolds})
                       for reynolds, profile in profiles.items()], ignore_index=True)
    add("B03_pointline_dns_reynolds", "point-line", outer, "Channel DNS: Reynolds-number comparison", "Wall distance, y/h",
        "Mean velocity, u/Ub", "Kawamura Lab：四组原始 DNS 均值剖面。",
        "不同摩擦雷诺数下的外尺度均值速度，检验有序配色和密集非均匀网格标记。",
        "Re_tau=180/395/640/1020；y/h=y+/Re_tau；u/Ub=u+/(Re_bulk/(2*Re_tau))；全部原始点。",
        group_kind="ordered")

    pipe_radius = np.linspace(0, 1, 21)
    pipe_theory = 2 * (1 - pipe_radius ** 2)
    pipe_numeric = pipe_theory * (1 + 0.025 * pipe_radius ** 2)
    pipe_samples = pipe_theory + random.normal(0, 0.012, len(pipe_radius)) * (1 - pipe_radius ** 2)
    pipe_points = series_frame(pipe_radius, [("Exact", pipe_theory), ("CFD (synth.)", pipe_numeric),
                                            ("Samples (synth.)", pipe_samples)])
    add("B04_pointline_pipe", "point-line", pipe_points, "Pipe comparison: all series connected", "Radius, r/R",
        "Axial velocity, u/Ub", "Hagen–Poiseuille 解析解 + 合成 CFD 和合成测量点。",
        "同图对比理论、数值示意和测量示意；按 point-line 定义，三组都显示点和连线。",
        "Re_D=1000；21 个 r/R 位置；u/Ub=2[1-(r/R)^2]；噪声为 0.012*(1-r^2)；固定种子。")

    eta_points = np.linspace(0, 8, 25)
    boundary_reference = np.interp(eta_points, eta, velocity)
    boundary_numeric = boundary_reference - 0.025 * eta_points * np.exp(-eta_points / 1.5)
    boundary_samples = boundary_reference + random.normal(0, 0.005, len(eta_points)) * np.minimum(eta_points, 1)
    boundary_points = series_frame(eta_points, [("Blasius", boundary_reference), ("CFD (synth.)", boundary_numeric),
                                              ("Samples (synth.)", boundary_samples)])
    add("B05_pointline_blasius", "point-line", boundary_points, "Boundary-layer comparison: connected points", "Similarity coordinate, eta",
        "Velocity, u/U_inf", "A04 的 Blasius 理论解显式线性插值到 25 个位置 + 合成 CFD 和合成测量点。",
        "边界层速度剖面的三组点线比较；插值仅用于构造理论采样，不修改 DNS。",
        "eta=0–8，共 25 点；数值偏差 -0.025*eta*exp(-eta/1.5)；合成测量噪声标准差上限 0.005。")

    for identifier, dense, points, title, xlabel, ylabel, source, meaning in [
        ("B06_mixed_pipe", pipe_dense.loc[pipe_dense["series"] != "Fine (synth.)"],
         pipe_points.loc[pipe_points["series"] == "Samples (synth.)"], "Pipe: curves plus sample-only markers",
         "Radius, r/R", "Axial velocity, u/Ub", "同 A03/B04；测量点仍为合成数据。", "理论线 + 数值线 + 不连线的合成测量点。"),
        ("B07_mixed_blasius", boundary_dense.loc[boundary_dense["series"] != "Fine (synth.)"],
         boundary_points.loc[boundary_points["series"] == "Samples (synth.)"], "Boundary layer: curves plus sample markers",
         "Similarity coordinate, eta", "Velocity, u/U_inf", "同 A04/B05；测量点仍为合成数据。", "Blasius 理论线 + 数值线 + 不连线的合成测量点。"),
    ]:
        add(identifier, "mixed", dense.copy(), title, xlabel, ylabel, source, meaning,
            "Python API 返回 Axes 后叠加 scatter；不是原生 point-line 模式；复用母板配色、图例和布局检查。",
            overlay=points.copy())

    scatter = pipe_points.loc[pipe_points["series"] == "Samples (synth.)"].copy()
    scatter["x"] = pipe_theory
    scatter["series"] = "Synthetic pairs"
    add("C01_scatter", "scatter", scatter, "Velocity sample pairs [synthetic]", "Exact velocity, u/Ub",
        "Sample velocity, u/Ub", "B04 的理论值与合成观测值逐点配对。", "最简单的一组散点，无连接线。", "21 对数据，无拟合、无回归线。")

    errors = [float(np.sqrt(np.mean((pipe_coarse - pipe_exact) ** 2))),
              float(np.sqrt(np.mean((pipe_fine - pipe_exact) ** 2)))]
    bars = pd.DataFrame({"x": ["Coarse", "Fine"], "y": errors})
    add("C02_bar", "bar", bars, "Synthetic pipe-profile error", "Illustrative grid", "RMSE of u/Ub (-)",
        "显式从 A03 的合成剖面计算 RMSE；并非真实网格收敛研究。", "两个预先计算的误差数值。",
        "RMSE=sqrt(mean((u_synth-u_exact)^2))；201 个 r/R 等距采样点。")

    heatmap_rows = []
    for axial in np.linspace(0, 2, 6):
        for radial in np.linspace(0, 1, 6):
            heatmap_rows.append({"x": f"{axial:.1f}", "y": f"{radial:.1f}", "value": 2 * (1 - radial ** 2)})
    add("C03_heatmap", "heatmap", pd.DataFrame(heatmap_rows), "Fully developed pipe field [analytic]", "Axial coordinate, x/D",
        "Radius, r/R", "Hagen–Poiseuille 解析速度场，规则网格显式求值。", "充分发展时速度沿轴向不变、沿径向抛物分布。",
        "6x6 网格；value=u/Ub=2[1-(r/R)^2]；cividis；原生 imshow 将首行放在图像上方。")

    violin = pd.concat([pd.DataFrame({"x": label, "y": random.normal(0, scale, 80)})
                        for label, scale in [("Coarse", 0.018), ("Fine", 0.006)]], ignore_index=True)
    add("C04_violin", "violin", violin, "Velocity-error distributions [synthetic]", "Illustrative grid", "Signed error in u/Ub (-)",
        "独立构造的高斯误差样本，不是从 DNS 计算的误差，也不是 A03 的误差分布。", "两组原始样本的核密度形状。",
        "每组 80 点；均值 0，标准差 0.018/0.006；固定种子；小提琴轮廓是模板内置 KDE。")
    checks = {"blasius_wall_curvature": curvature, "blasius_farfield_velocity": float(velocity[-1]),
              "pipe_wall_velocity": float(pipe_exact[-1]), "pipe_center_velocity": float(pipe_exact[0]),
              "synthetic_pipe_rmse": errors}
    return cases, provenance, checks


def configure_log_axis(axes, scale: str) -> None:
    for name, active in (("x", scale == "logx"), ("y", scale == "logy")):
        if not active:
            continue
        getattr(axes, f"set_{name}scale")("log")
        axis = getattr(axes, f"{name}axis")
        axis.set_major_locator(LogLocator(base=10))
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
        axis.set_major_formatter(LogFormatterSciNotation(base=10))


def audit_plot(template, case: dict, figure, axes) -> dict:
    frame, kind = case["frame"], case["kind"]
    assertions = []
    if kind in ("line", "point-line", "mixed"):
        expected_groups = list(pd.unique(frame["series"]))
        if case["group_kind"] == "ordered":
            expected_groups.sort()
        assert len(axes.lines) == len(expected_groups)
        for label, line in zip(expected_groups, axes.lines):
            subset = frame.loc[frame["series"] == label]
            np.testing.assert_array_equal(line.get_xdata(), subset["x"].to_numpy())
            np.testing.assert_array_equal(line.get_ydata(), subset["y"].to_numpy())
            assert line.get_linestyle() not in ("", "None", "none", " ")
            marker_present = line.get_marker() not in (None, "", "None", "none", " ")
            assert marker_present == (kind == "point-line")
        assertions.extend(["all source points retained", "within-series row order preserved", "line/marker semantics correct"])
    if kind in ("scatter", "mixed"):
        assert len(axes.collections) == 1
        expected = case["overlay"] if kind == "mixed" else frame
        np.testing.assert_array_equal(np.asarray(axes.collections[0].get_offsets()), expected[["x", "y"]].to_numpy())
        if kind == "scatter":
            assert not axes.lines
        assertions.append("scatter offsets exact; no added connections")
    if kind == "bar":
        np.testing.assert_allclose([patch.get_height() for patch in axes.patches], frame["y"])
        assertions.append("precomputed bar heights preserved")
    if kind == "heatmap":
        matrix = frame.pivot(index="y", columns="x", values="value").reindex(
            index=pd.unique(frame["y"]), columns=pd.unique(frame["x"]))
        np.testing.assert_array_equal(np.asarray(axes.images[0].get_array()), matrix.to_numpy())
        assertions.append("heatmap cells preserved")
    if kind == "violin":
        assert len(axes.collections) == frame["x"].nunique() + 3
        assertions.append("two violin bodies plus extrema artists")
    assert all(spine.get_visible() for spine in axes.spines.values())
    for axis in (axes.xaxis, axes.yaxis):
        for tick in axis.get_major_ticks():
            assert tick._tickdir == "in" and tick.tick1line.get_visible() and tick.tick2line.get_visible()
    template._check_text_layout(figure)
    legend = axes.get_legend()
    hits = 0
    if legend is not None:
        bounds = legend.get_window_extent(figure.canvas.get_renderer())
        assert figure.bbox.contains(*bounds.p0) and figure.bbox.contains(*bounds.p1)
        vertices = template._line_vertices(axes)
        hits = int(np.count_nonzero((vertices[:, 0] >= bounds.x0) & (vertices[:, 0] <= bounds.x1)
                                   & (vertices[:, 1] >= bounds.y0) & (vertices[:, 1] <= bounds.y1)))
        assert hits == 0
        assert all(text.get_fontsize() == template.TEXT_SIZES_PT["double"]["legend"] for text in legend.get_texts())
    np.testing.assert_allclose(figure.get_size_inches() * 25.4, [183, 136])
    assertions.extend(["four inward-ticked sides", "labels/legend inside canvas", "no sampled data covered by legend",
                       "183 x 136 mm; double-column font sizes"])
    return {"checks": assertions, "legend_sample_hits": hits, "line_count": len(axes.lines),
            "marker_sizes_pt": [line.get_markersize() for line in axes.lines] if kind == "point-line" else [],
            "line_widths_pt": [line.get_linewidth() for line in axes.lines], "font": axes.xaxis.label.get_fontfamily(),
            "xscale": axes.get_xscale(), "yscale": axes.get_yscale()}


def render_case(template, case: dict, output_dir: Path) -> dict:
    frame, kind = case["frame"], case["kind"]
    native_kind = "line" if kind == "mixed" else kind
    options = {"kind": native_kind, "x": "x", "y": "y", "xlabel": case["xlabel"],
               "ylabel": case["ylabel"], "title": case["title"], "size": "double"}
    if "series" in frame:
        options.update(group="series", group_kind=case["group_kind"])
    if kind == "heatmap":
        options["value"] = "value"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure, axes, _ = template.render_plot(frame, **options)
        try:
            with mpl.rc_context({"font.family": axes.xaxis.label.get_fontfamily(), "font.size": 9.5}):
                if kind == "mixed":
                    overlay = case["overlay"]
                    axes.scatter(overlay["x"], overlay["y"], label=str(overlay["series"].iloc[0]),
                                 color=template.CATEGORICAL_COLORS[2], marker=template.MARKERS[2],
                                 s=5.5 ** 2, edgecolor="#333333", linewidth=0.55, zorder=3)
                configure_log_axis(axes, case["scale"])
                if case["scale"] != "linear" or kind == "mixed":
                    if axes.get_legend() is not None:
                        axes.get_legend().remove()
                    figure.canvas.draw()
                    template._adapt_strokes(axes, native_kind)
                    template._place_legend(figure, axes, "double")
                    template._hide_edge_grids(axes)
                audit = audit_plot(template, case, figure, axes)
                output = output_dir / (case["id"] + ".png")
                figure.savefig(output, dpi=300, facecolor="white")
                with Image.open(output) as image:
                    expected = tuple(int(length / 25.4 * 300) for length in (183, 136))
                    assert image.size == expected
                    audit["png_pixels"] = list(image.size)
                    audit["png_dpi"] = list(image.info.get("dpi", ()))
        finally:
            plt.close(figure)
    audit["warnings"] = list(dict.fromkeys(str(item.message) for item in caught))
    return audit


def make_contact_sheet(output_dir: Path, filenames: list[str], name: str) -> None:
    thumb_width, thumb_height = 720, 536
    canvas = Image.new("RGB", (thumb_width * 2, (thumb_height + 30) * ((len(filenames) + 1) // 2)), "white")
    drawing = ImageDraw.Draw(canvas)
    for index, filename in enumerate(filenames):
        with Image.open(output_dir / (filename + ".png")) as image:
            image.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            left, top = index % 2 * thumb_width, index // 2 * (thumb_height + 30)
            canvas.paste(image.convert("RGB"), (left, top + 30))
            drawing.text((left + 15, top + 8), filename, fill="#222222")
    canvas.save(output_dir / name)


def write_reports(output_dir: Path, manifest: dict) -> None:
    report = ["# CFD 科研绘图 skill 系统测试", "",
              "## 结论与范围", "",
              "完成 5 张 line、5 张 point-line、2 张混合补充图和 4 张其他图，共 16 张。",
              "所有 line 数据系列均无标记；所有 point-line 数据系列均有标记且连线。混合图不冒充 point-line。",
              "真实 DNS 来源为首选 Kawamura Lab；NASA 备用源未启用。合成 CFD/测量/残差均明确标注，不能用来声称物理模型获得验证。",
              "所有图为双栏 183 × 136 mm、300 dpi、仅 PNG；原始数据未平滑或抽稀。", "",
              "## 数据溯源", "", f"数据库主页：{SOURCE_URL}", "",
              "原始文件保留作者署名、引用要求和使用说明；数据不是本项目原创，也不假定为无条件开放许可。", "",
              "Re_tau=u_tau*h/nu，Re_bulk=Ub*2h/nu；u+=u/u_tau，y+=y*u_tau/nu；h 为半通道高度。", ""]
    for source in manifest["sources"]:
        report.extend([f"- `{source['file']}`：Re_tau={source['Re_tau']:g}，Re_bulk={source['Re_bulk']:g}，"
                       f"{source['rows']} 个原始位置；{source['url']}", f"  SHA256：`{source['sha256']}`"])
    report.extend(["", "引用应按原文件的 References 节选择，尤其注意不同 Reynolds 数与数据版本的出处不同。", "",
                   "## 逐图记录（按执行顺序）", ""])
    for case in manifest["cases"]:
        report.extend([f"### {case['id']} — {case['kind']}", "", f"![{case['id']}]({case['id']}.png)", "",
                       f"- 数据来源：{case['source']}", f"- 物理含义：{case['meaning']}",
                       f"- 关键参数：{case['parameters']}", f"- CSV：`{case['csv']}`；数据行数：{case['rows']}。",
                       "- 自动检查：" + "；".join(case["audit"]["checks"]) + "。", ""])
    report.extend(["## 发现的问题和使用边界", "",
                   "1. 环境未安装 Arial，模板按既定规范警告后回退到 Liberation Sans；没有悄悄换风格。",
                   "2. CLI/API 没有 xscale/yscale 参数。A01 的 log-y 和 A02 的 log-x 通过返回的 Axes 显式设置，"
                   "同时将 AutoMinorLocator 换为 LogLocator，并重算线宽、图例和边界网格；未修改母板。",
                   "3. 原生 kind 是整图级别，不能直接按系列混用 line/scatter。B06/B07 是 Python API 叠图示范，"
                   "理论/数值为纯线，合成测量为纯散点，复用母板的布局检查。B01–B05 则严格所有系列都点+线。",
                   "4. point-line 前 8 组以点形区分，连接线默认同为实线；line 前 8 组使用不同线型。"
                   "因此多 Re 黑白打印主要依赖点形，不能声称每组自动获得不同线型。",
                   "5. 密集 DNS 点线图保留全部点，自动降低到 2.4–3.5 pt 标记；近壁点仍可能拥挤。"
                   "双栏尺寸可读，不能把双栏图直接缩到单栏使用。",
                   "6. 两套 Re_tau=180 DNS 的网格和空间离散同时不同；比较不构成控制变量下的阶数验证。",
                   "7. 热力图原生首行在上方，本例径向标签随之从上到下增大；没有暗中改变坐标方向。",
                   "8. 小提琴图原生使用 KDE，是分布可视化而非无处理的折线；未额外进行数据平滑。",
                   "9. 数据下载时 Re_tau=1020 文件曾出现 TLS EOF，重试后成功；原始文件和校验和已缓存，复现不需要联网。", "",
                   "10. DNS 的均值/uu/ww 表和 vv/-uv 表位于交错网格。不能按相同 j 直接共用 y+；"
                   "A05 分别使用两表自身的坐标，未进行空间插值。", "",
                   "11. 实测发现并修复原生长表热力图缺陷：render_plot 校验线宽/点径时的局部变量 value "
                   "覆盖了热力图的 value 列名。将局部变量改名 override；新增 API 与 CLI 回归测试。"
                   "该修复不改变绘图风格，输出母板快照包含此修复。", "",
                   "12. 全范围理论/合成数值剖面高度重合，是有意设置的小偏差，不是漏画。"
                   "如用于量化方法差异，应另加误差剖面或局部放大；本轮不额外修改既定单图样式。", "",
                   "## 复现与审计", "",
                   "- `manifest.json`：原始 URL/校验和、参数、逐图检查、警告和环境版本。",
                   "- `data/`：每图准确输入 CSV，混合图另存 overlay CSV。",
                   "- `raw/`：下载文件及数据库页面快照；保留来源与作者说明。",
                   "- `plot_template_snapshot.py`：本次绘图母板副本，SHA256 记录于 manifest。",
                   "- `cfd_runner.py` 和 `reproduce.py`：离线重绘，使用同目录母板和 CSV，不依赖仓库原路径。",
                   "- 在本目录运行 `python reproduce.py`；需要 numpy/pandas/matplotlib/Pillow，完整版本见 manifest。",
                   "- 自动审计检查 artist 数据、系列顺序、标记/连线语义、四边朝内刻度、图例与文本边界、"
                   "图例覆盖采样检查及 PNG 像素尺寸。视觉复核不能由这些断言完全替代。", ""])
    (output_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    sections = []
    for heading, prefix in (("A · Line", "A"), ("B · Point-line and mixed supplements", "B"), ("C · Other types", "C")):
        cards = []
        for case in manifest["cases"]:
            if not case["id"].startswith(prefix):
                continue
            identifier = case["id"]
            cards.append(f'<article><h3>{html.escape(identifier)}</h3><a href="{identifier}.png">'
                         f'<img src="{identifier}.png" alt="{identifier}"></a>'
                         f'<p><b>来源：</b>{html.escape(case["source"])}</p>'
                         f'<p><b>含义：</b>{html.escape(case["meaning"])}</p>'
                         f'<p><b>参数：</b>{html.escape(case["parameters"])}</p></article>')
        sections.append(f"<h2>{heading}</h2><section>{''.join(cards)}</section>")
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CFD plotting tests</title>'
                '<style>body{font-family:Arial,sans-serif;max-width:1500px;margin:32px auto;padding:0 24px;color:#24323b}'
                'section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}'
                'article{border:1px solid #d6dfe3;border-radius:8px;padding:16px}img{width:100%}'
                'p{line-height:1.6}h2{margin-top:40px}@media(max-width:900px){section{grid-template-columns:1fr}}</style>'
                '<h1>CFD 科研绘图系统测试</h1><p>5 line + 5 point-line + 2 mixed + 4 simple checks. '
                'DNS 为真实公开数据；synthetic/synth. 均为人为构造，不是真实 CFD/实验。</p>'
                '<p>点击图像查看原始 300 dpi PNG；<a href="REPORT.md">完整报告</a> · '
                '<a href="manifest.json">数据与审计记录</a></p>' + ''.join(sections) + '</html>')
    (output_dir / "index.html").write_text(document, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "cfd_validation" / "raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures" / "cfd_validation")
    parser.add_argument("--template-file", type=Path, default=ROOT / "scientific-plotting" / "scripts" / "plot_template.py")
    parser.add_argument("--replay", type=Path)
    options = parser.parse_args(argv)
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    template = load_template(options.template_file.resolve())
    if options.replay:
        manifest = json.loads(options.replay.read_text(encoding="utf-8"))
        for record in manifest["cases"]:
            case = {**record, "frame": pd.read_csv(options.replay.parent / record["csv"]), "overlay": None}
            if record.get("overlay_csv"):
                case["overlay"] = pd.read_csv(options.replay.parent / record["overlay_csv"])
            render_case(template, case, output_dir)
            print(f"Replayed {case['id']}", flush=True)
        return

    cases, sources, scientific_checks = build_cases(options.raw_dir)
    (output_dir / "data").mkdir(exist_ok=True)
    shutil.copytree(options.raw_dir, output_dir / "raw", dirs_exist_ok=True)
    snapshot = output_dir / "plot_template_snapshot.py"
    shutil.copy2(options.template_file, snapshot)
    shutil.copy2(__file__, output_dir / "cfd_runner.py")
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "source_page": SOURCE_URL,
                "template_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                "environment": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                                "matplotlib": mpl.__version__, "pillow": Image.__version__},
                "sources": sources, "scientific_checks": scientific_checks, "cases": []}
    for case in cases:
        csv_name = "data/" + case["id"] + ".csv"
        case["frame"].to_csv(output_dir / csv_name, index=False)
        overlay_csv = None
        if case["overlay"] is not None:
            overlay_csv = "data/" + case["id"] + "_overlay.csv"
            case["overlay"].to_csv(output_dir / overlay_csv, index=False)
        audit = render_case(template, case, output_dir)
        record = {key: value for key, value in case.items() if key not in ("frame", "overlay")}
        record.update(csv=csv_name, overlay_csv=overlay_csv, rows=len(case["frame"]), audit=audit)
        manifest["cases"].append(record)
        print(f"PASS {case['id']}: {len(case['frame'])} rows; {len(audit['checks'])} checks", flush=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    launcher = ('from pathlib import Path\nimport subprocess\nimport sys\n\n'
                'root = Path(__file__).resolve().parent\n'
                'subprocess.run([sys.executable, str(root / "cfd_runner.py"),\n'
                '    "--replay", str(root / "manifest.json"),\n'
                '    "--template-file", str(root / "plot_template_snapshot.py"),\n'
                '    "--output-dir", str(root)], check=True)\n')
    (output_dir / "reproduce.py").write_text(launcher, encoding="utf-8")
    write_reports(output_dir, manifest)
    for prefix, sheet in (("A", "overview_line.png"), ("B0", "overview_pointline.png"), ("C", "overview_other.png")):
        identifiers = [case["id"] for case in cases if case["id"].startswith(prefix)
                       and (prefix != "B0" or case["kind"] == "point-line")]
        make_contact_sheet(output_dir, identifiers, sheet)
    print(output_dir / "REPORT.md", flush=True)


if __name__ == "__main__":
    main()
