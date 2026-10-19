"""CFD-focused exercise of the scientific-plotting template.

Kawamura channel profiles are read from the cached database files and are not
smoothed or resampled. Hagen–Poiseuille, Blasius, cylinder histories, residuals
and measurement-like samples are constructed references and are labeled synthetic.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "cfd_validation" / "raw"
OUTPUT_DIR = ROOT / "figures" / "cfd_skill_test"
SOURCE_PAGE = "https://www.rs.tus.ac.jp/~t2lab/db/poi/poi.html"
RAW_NAMES = {
    180: "Poi180_4th_E.dat",
    395: "Poi395_4th_D.dat",
    640: "Poi640_4th_B.dat",
    1020: "Poi1020_4th_A_ver2.dat",
}
SECOND_ORDER_NAME = "Poi180_2nd_A.dat"
SEED = 20261019


def load_template():
    path = ROOT / "scientific-plotting" / "scripts" / "plot_template.py"
    spec = importlib.util.spec_from_file_location("scientific_plot_template", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_table(path: Path, required: str) -> pd.DataFrame:
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
            raise ValueError(f"Empty table {required} in {path.name}")
        frame = pd.DataFrame(rows, columns=tokens)
        values = frame.to_numpy(dtype=float)
        if not np.isfinite(values).all() or not (np.diff(frame["y+"].to_numpy()) > 0).all():
            raise ValueError(f"Non-finite or non-increasing y+ in {path.name}:{required}")
        return frame
    raise ValueError(f"Missing table {required} in {path.name}")


def read_case(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="strict")
    reynolds_tau = re.search(r"^\s*Re_tau\s*=\s*(\d+(?:\.\d+)?)\s*$", text, re.MULTILINE)
    reynolds_bulk = re.search(r"^\s*Re_bulk\s*=\s*(\d+(?:\.\d+)?)\s*$", text, re.MULTILINE)
    if reynolds_tau is None or reynolds_bulk is None:
        raise ValueError(f"Missing Reynolds numbers in {path.name}")
    mean = read_table(path, "u_mean")
    shear = read_table(path, "-uv+")
    re_tau = float(reynolds_tau[1])
    re_bulk = float(reynolds_bulk[1])
    mean = mean.copy()
    shear = shear.copy()
    mean["y_over_h"] = mean["y+"] / re_tau
    mean["u_over_ub"] = mean["u_mean"] / (re_bulk / (2 * re_tau))
    shear["y_over_h"] = shear["y+"] / re_tau
    return {
        "file": path.name,
        "url": SOURCE_PAGE.rsplit("/", 1)[0] + "/text/" + path.name,
        "Re_tau": re_tau,
        "Re_bulk": re_bulk,
        "mean_rows": len(mean),
        "shear_rows": len(shear),
        "staggered": not np.array_equal(mean["y+"].to_numpy(), shear["y+"].to_numpy()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "y_plus_mean": (float(mean["y+"].iloc[0]), float(mean["y+"].iloc[-1])),
        "centerline_u_plus": float(mean["u_mean"].iloc[-1]),
        "mean": mean,
        "shear": shear,
    }


def stack(parts: list[tuple[str, np.ndarray, np.ndarray]]) -> pd.DataFrame:
    frames = [pd.DataFrame({"x": x_values, "y": y_values, "series": label}) for label, x_values, y_values in parts]
    return pd.concat(frames, ignore_index=True)


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
    for _ in range(40):
        curvature = (lower + upper) / 2
        if integrate(curvature)[-1, 1] < 1:
            lower = curvature
        else:
            upper = curvature
    curvature = (lower + upper) / 2
    velocity = integrate(curvature)[:, 1]
    if abs(velocity[-1] - 1) > 1e-8 or velocity[0] != 0:
        raise RuntimeError("Blasius shooting did not meet the boundary conditions")
    return eta, velocity, curvature


def build_catalog(cases: dict[int, dict], second: dict, curvature: float,
                  eta: np.ndarray, blasius: np.ndarray) -> list[dict]:
    random = np.random.default_rng(SEED)
    ordered = load_template()._palette(4, True)
    reynolds_styles = {
        f"Re_tau = {re_tau:g}": {"color": color, "linestyle": linestyle}
        for re_tau, color, linestyle in zip(
            (180, 395, 640, 1020), ordered, ("-", "--", "-.", ":"), strict=True)
    }
    catalog = []

    def add(case: dict) -> None:
        catalog.append(case)

    iteration = np.arange(0, 2001, 5, dtype=float)
    residual = stack([
        ("Continuity", iteration, 1.0 * 10 ** (-iteration / 280) * (1 + 0.06 * np.sin(iteration / 37))),
        ("x-momentum", iteration, 0.8 * 10 ** (-iteration / 340) * (1 + 0.05 * np.sin(iteration / 29))),
        ("y-momentum", iteration, 0.9 * 10 ** (-iteration / 310) * (1 + 0.05 * np.cos(iteration / 41))),
    ])
    add({
        "id": "A01_line_residual", "kind": "line", "frame": residual, "group_kind": "categorical",
        "xscale": "linear", "yscale": "log", "size": "double",
        "xlabel": "Iteration (-)", "ylabel": "Normalized residual (-)",
        "title": "Synthetic residual history",
        "source": "人为构造的正残差序列，不是任何求解器的输出。",
        "meaning": "连续性方程和两个动量方程的归一化残差随迭代下降，用来检查对数纵轴折线。",
        "parameters": "迭代 0–2000，步长 5；R=A·10^(-n/τ)·(1+a·sin或cos)；三个残差均严格大于 0。seed 未使用。",
    })

    law_y = np.geomspace(0.3, 12, 40)
    log_y = np.geomspace(30, 300, 80)
    kappa, intercept = 0.41, 5.2
    inner_parts = [
        (f"Re_tau = {re_tau:g}", cases[re_tau]["mean"]["y+"].to_numpy(), cases[re_tau]["mean"]["u_mean"].to_numpy())
        for re_tau in (180, 395, 640, 1020)
    ]
    inner_parts.extend([
        ("u+ = y+", law_y, law_y),
        ("Log law", log_y, np.log(log_y) / kappa + intercept),
    ])
    inner_styles = dict(reynolds_styles)
    inner_styles["u+ = y+"] = {"color": "#3A3F46", "linestyle": (0, (5, 2)), "line_width": 1.6}
    inner_styles["Log law"] = {"color": "#5C4E9A", "linestyle": (0, (7, 1.8)), "line_width": 1.6}
    add({
        "id": "A02_line_dns_inner", "kind": "line", "frame": stack(inner_parts),
        "group_kind": "categorical", "series_styles": inner_styles,
        "xscale": "log", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y+", "ylabel": "Mean velocity, u+",
        "title": "Channel DNS: inner scaling",
        "source": "Kawamura Lab 四个第四阶充分发展 Poiseuille 案例的均值表；黏性底层和对数律是经典参考式，不是对 DNS 的拟合。",
        "meaning": "半通道内尺度速度剖面 u+(y+)。u_mean 列在近壁处约等于 y+，按数据库约定视为 u/u_tau。",
        "parameters": "Re_tau=180/395/640/1020；保留各文件全部 y+>0 的原始点，不补 y+=0。对数律 κ=0.41，B=5.2，只画 y+=30–300。",
    })

    radius = np.linspace(0, 1, 401)
    exact_pipe = 2 * (1 - radius ** 2)
    pipe = stack([
        ("Exact", radius, exact_pipe),
        ("Fine CFD (synth.)", radius, exact_pipe * (1 + 0.006 * radius ** 2)),
        ("Coarse CFD (synth.)", radius, exact_pipe * (1 + 0.025 * radius ** 2)),
    ])
    add({
        "id": "A03_line_pipe", "kind": "line", "frame": pipe, "group_kind": "categorical",
        "series_styles": {
            "Exact": {"color": "#0A5270", "linestyle": "-", "line_width": 1.8},
            "Fine CFD (synth.)": {"color": "#D35400", "linestyle": "--", "line_width": 1.5},
            "Coarse CFD (synth.)": {"color": "#2F6DB5", "linestyle": "-.", "line_width": 1.5},
        },
        "error": {"reference": "Exact", "definition": "signed", "interpolation": "none",
                  "ylabel": "Signed error in u/Ub"},
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Radius, r/R", "ylabel": "Axial velocity, u/Ub",
        "title": "Laminar pipe profile",
        "source": "Hagen–Poiseuille 解析解，加上两组按半径放大的合成数值剖面。不是求解器结果。",
        "meaning": "不可压缩充分发展层流圆管轴向速度，以及相对解析解的有符号偏差。",
        "parameters": "示意 Re_D=1000；u/Ub=2[1-(r/R)^2]；细网格乘子 1+0.006(r/R)^2，粗网格 1+0.025(r/R)^2；401 个相同半径，误差为 y-解析解，不插值。图例能放进坐标框就放进去，否则放到图顶。",
    })

    eta_plot = eta[eta <= 8]
    blasius_plot = blasius[eta <= 8]
    boundary = stack([
        ("Blasius", eta_plot, blasius_plot),
        ("CFD (synth.)", eta_plot, blasius_plot - 0.018 * eta_plot * np.exp(-eta_plot / 1.6)),
    ])
    add({
        "id": "A04_line_blasius", "kind": "line", "frame": boundary, "group_kind": "categorical",
        "series_styles": {
            "Blasius": {"color": "#0A5270", "linestyle": "-", "line_width": 1.8},
            "CFD (synth.)": {"color": "#D35400", "linestyle": "--", "line_width": 1.5},
        },
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Similarity coordinate, eta", "ylabel": "Velocity, u/Uinf",
        "title": "Blasius profile",
        "source": "Blasius 方程的打靶数值解作为理论曲线；第二条是人为下移的合成数值剖面。",
        "meaning": "零压力梯度层流平板边界层的相似速度剖面。Blasius 解不是闭式代数公式。",
        "parameters": f"f'''+0.5·f·f''=0；f(0)=f'(0)=0，f'(10)=1；RK4 步长 0.01；f''(0)={curvature:.10f}。图中 eta 只取到 8，偏差为 -0.018·eta·exp(-eta/1.6)。",
    })

    stress_mean = cases[395]["mean"]
    stress_shear = cases[395]["shear"]
    stresses = stack([
        ("uu+", stress_mean["y_over_h"].to_numpy(), stress_mean["uu+"].to_numpy()),
        ("ww+", stress_mean["y_over_h"].to_numpy(), stress_mean["ww+"].to_numpy()),
        ("vv+", stress_shear["y_over_h"].to_numpy(), stress_shear["vv+"].to_numpy()),
        ("-uv+", stress_shear["y_over_h"].to_numpy(), stress_shear["-uv+"].to_numpy()),
    ])
    add({
        "id": "A05_line_dns_stresses", "kind": "line", "frame": stresses, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y/h", "ylabel": "Reynolds stress / u_tau^2",
        "title": "Channel DNS: Reynolds stresses",
        "source": "Kawamura Lab Poi395_4th_D.dat 的均值表（uu+、ww+）和剪切表（vv+、-uv+）。",
        "meaning": "Re_tau=395 的法向雷诺应力和负雷诺剪切应力。不是速度脉动均方根。",
        "parameters": "两套交错网格各自保留原始 y+，y/h=y+/Re_tau；不做插值合并。",
    })

    outer = stack([
        (f"Re_tau = {re_tau:g}", cases[re_tau]["mean"]["y_over_h"].to_numpy(), cases[re_tau]["mean"]["u_over_ub"].to_numpy())
        for re_tau in (180, 395, 640, 1020)
    ])
    add({
        "id": "A06_line_dns_outer", "kind": "line", "frame": outer, "group_kind": "ordered",
        "series_styles": reynolds_styles, "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y/h", "ylabel": "Mean velocity, u/Ub",
        "title": "Channel DNS: outer scaling",
        "source": "同上四个 Kawamura Poiseuille 均值表。",
        "meaning": "用体积速度无量纲化的半通道速度剖面，看雷诺数对外尺度形状的影响。",
        "parameters": "Ub+=Re_bulk/(2·Re_tau)；u/Ub=u+/Ub+；y/h=y+/Re_tau；全部原始点，有序配色从低雷诺数到高雷诺数。",
    })

    time = np.linspace(0, 80, 1601)
    lift = 0.32 * (1 - np.exp(-time / 10)) * np.sin(2 * np.pi * 0.165 * time)
    drag = 1.34 * (1 - np.exp(-time / 8)) + 0.045 * np.exp(-time / 12) * np.sin(2 * np.pi * 0.33 * time)
    forces = stack([("Cd (synth.)", time, drag), ("Cl (synth.)", time, lift)])
    add({
        "id": "A07_line_cylinder", "kind": "line", "frame": forces, "group_kind": "categorical",
        "series_styles": {
            "Cd (synth.)": {"color": "#0A5270", "linestyle": "-", "line_width": 1.5},
            "Cl (synth.)": {"color": "#D35400", "linestyle": "--", "line_width": 1.5},
        },
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Dimensionless time, tU/D", "ylabel": "Force coefficient (-)",
        "title": "Synthetic cylinder forces",
        "source": "按 Re_D≈100 圆柱绕流的典型量级构造的时间信号，不是 CFD 计算。",
        "meaning": "阻力系数趋于定常、升力系数进入涡脱落振荡的时间历程。",
        "parameters": "示意 St=0.165；Cd 基值 1.34；Cl 饱和振幅 0.32；tU/D=0–80，1601 个点。升力有正有负，因此不用对数轴。",
    })

    sample_time = np.arange(0, 80.0001, 1.0)
    reference_lift = 0.32 * (1 - np.exp(-sample_time / 10)) * np.sin(2 * np.pi * 0.165 * sample_time)
    cfd_lift = 0.305 * (1 - np.exp(-sample_time / 11)) * np.sin(2 * np.pi * 0.165 * sample_time + 0.08)
    measured_lift = reference_lift + random.normal(0, 0.012, len(sample_time))
    lift_points = stack([
        ("Reference (synth.)", sample_time, reference_lift),
        ("CFD (synth.)", sample_time, cfd_lift),
        ("Samples (synth.)", sample_time, measured_lift),
    ])
    add({
        "id": "B01_pointline_lift", "kind": "point-line", "frame": lift_points, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Dimensionless time, tU/D", "ylabel": "Lift coefficient, Cl",
        "title": "Synthetic lift: every series marked",
        "source": "合成参考信号、合成 CFD 和合成测量，三者都是离散采样。无真实实验。",
        "meaning": "启动后进入周期涡脱落的升力历程。此图严格按点线图：每条序列都有标记和连线。",
        "parameters": "示意 Re_D=100，St=0.165；tU/D=0–80，步长 1；测量噪声标准差 0.012；seed=20261019。",
    })

    schemes = stack([
        ("2nd-order DNS", second["mean"]["y_over_h"].to_numpy(), second["mean"]["u_over_ub"].to_numpy()),
        ("4th-order DNS", cases[180]["mean"]["y_over_h"].to_numpy(), cases[180]["mean"]["u_over_ub"].to_numpy()),
    ])
    add({
        "id": "B02_pointline_dns_schemes", "kind": "point-line", "frame": schemes, "group_kind": "categorical",
        "series_styles": {
            "2nd-order DNS": {"color": "#D35400", "linestyle": "--", "marker": "s"},
            "4th-order DNS": {"color": "#0A5270", "linestyle": "-", "marker": "o"},
        },
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y/h", "ylabel": "Mean velocity, u/Ub",
        "title": "Channel DNS at Re_tau = 180",
        "source": "Kawamura Lab Poi180_2nd_A.dat 与 Poi180_4th_E.dat，均为数据库原始剖面。",
        "meaning": "同一名义摩擦雷诺数下两套 DNS 的外尺度速度。网格和格式同时不同，不能单独归因于离散阶数。",
        "parameters": f"二阶 Re_bulk={second['Re_bulk']:g}，{second['mean_rows']} 点；四阶 Re_bulk={cases[180]['Re_bulk']:g}，{cases[180]['mean_rows']} 点。两套原网格都不插值。",
    })

    add({
        "id": "B03_pointline_dns_reynolds", "kind": "point-line", "frame": outer, "group_kind": "ordered",
        "series_styles": {
            label: {**style, "marker": marker}
            for (label, style), marker in zip(reynolds_styles.items(), ("o", "s", "^", "D"), strict=True)
        },
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y/h", "ylabel": "Mean velocity, u/Ub",
        "title": "Channel DNS: Reynolds number",
        "source": "四个 Kawamura 均值剖面的全部原始点。",
        "meaning": "不同摩擦雷诺数的外尺度速度，用点线图区分。近壁点很密，标记可能挤在一起。",
        "parameters": "Re_tau=180/395/640/1020；不抽稀、不使用 markevery。有序配色。",
    })

    station = np.linspace(0, 1, 21)
    exact_station = 2 * (1 - station ** 2)
    pipe_points = stack([
        ("Exact", station, exact_station),
        ("CFD (synth.)", station, exact_station * (1 + 0.025 * station ** 2)),
        ("Samples (synth.)", station, exact_station + random.normal(0, 0.012, len(station)) * (1 - station ** 2)),
    ])
    add({
        "id": "B04_pointline_pipe", "kind": "point-line", "frame": pipe_points, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Radius, r/R", "ylabel": "Axial velocity, u/Ub",
        "title": "Pipe stations: all series connected",
        "source": "解析解、合成 CFD 和合成测点，三组都落在相同的 21 个半径上。",
        "meaning": "层流圆管剖面的点线对比。按点线图定义，理论值也显示标记，不是纯理论线。",
        "parameters": "u/Ub=2[1-(r/R)^2]；CFD 乘子 1+0.025(r/R)^2；测点噪声 0.012·(1-(r/R)^2)；seed=20261019。",
    })

    eta_station = np.linspace(0, 8, 25)
    blasius_station = np.interp(eta_station, eta, blasius)
    boundary_points = stack([
        ("Blasius", eta_station, blasius_station),
        ("CFD (synth.)", eta_station, blasius_station - 0.018 * eta_station * np.exp(-eta_station / 1.6)),
        ("Samples (synth.)", eta_station,
         blasius_station + random.normal(0, 0.006, len(eta_station)) * np.minimum(eta_station, 1)),
    ])
    add({
        "id": "B05_pointline_blasius", "kind": "point-line", "frame": boundary_points, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Similarity coordinate, eta", "ylabel": "Velocity, u/Uinf",
        "title": "Boundary layer: connected stations",
        "source": "Blasius 打靶解线性插值到 25 个 eta 站位，再构造合成 CFD 和合成测点。插值只用于生成这条理论采样。",
        "meaning": "平板边界层速度剖面的三组点线对比。",
        "parameters": "eta=0, 1/3, …, 8；偏差与 A04 相同；测点噪声标准差 0.006·min(eta,1)；seed=20261019。",
    })

    shear_profiles = stack([
        (f"Re_tau = {re_tau:g}", cases[re_tau]["shear"]["y_over_h"].to_numpy(), cases[re_tau]["shear"]["-uv+"].to_numpy())
        for re_tau in (180, 395, 640, 1020)
    ])
    add({
        "id": "B06_pointline_dns_shear", "kind": "point-line", "frame": shear_profiles, "group_kind": "ordered",
        "series_styles": {
            label: {**style, "marker": marker}
            for (label, style), marker in zip(reynolds_styles.items(), ("o", "s", "^", "D"), strict=True)
        },
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Wall distance, y/h", "ylabel": "Reynolds shear stress, -uv+",
        "title": "Channel DNS: shear stress",
        "source": "四个案例剪切应力表中的 -uv+ 列，不是均值表。",
        "meaning": "负雷诺剪切应力的外尺度分布。各雷诺数保留自己的交错网格。",
        "parameters": "不把 -uv+ 插值到均值速度网格上；y/h=y+/Re_tau。图例能放进坐标框就放进去，避免挡住近壁峰值；否则放到图顶。",
    })

    dense_time = np.linspace(0, 80, 1601)
    dense_cfd = 0.305 * (1 - np.exp(-dense_time / 11)) * np.sin(2 * np.pi * 0.165 * dense_time + 0.08)
    mixed_lift = stack([
        ("CFD (synth.)", dense_time, dense_cfd),
        ("Samples (synth.)", sample_time, measured_lift),
    ])
    add({
        "id": "M01_mixed_lift", "kind": "mixed", "frame": mixed_lift, "group_kind": "categorical",
        "series_styles": {
            "CFD (synth.)": {"kind": "line", "color": "#0A5270", "linestyle": "-", "line_width": 1.5},
            "Samples (synth.)": {"kind": "scatter", "color": "#D35400", "marker": "o", "marker_size": 5.2},
        },
        "error": {"reference": "CFD (synth.)", "definition": "signed", "interpolation": "linear",
                  "ylabel": "Sample minus CFD, Cl"},
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Dimensionless time, tU/D", "ylabel": "Lift coefficient, Cl",
        "title": "Mixed lift: line plus samples",
        "source": "合成 CFD 密时间序列连线，合成测点不连线。不是实验验证。",
        "meaning": "典型的“数值曲线 + 离散测点”时间历程，以及测点相对 CFD 曲线的有符号差。",
        "parameters": "CFD 为 1601 点；测点步长 1，与 B01 的 Samples 相同。误差按线性插值把 CFD 取到测点时刻，不外推。",
    })

    sample_radius = np.linspace(0, 1, 16)
    cfd_station = exact_station * (1 + 0.025 * station ** 2)
    mixed_pipe = stack([
        ("Exact", radius, exact_pipe),
        ("CFD (synth.)", station, cfd_station),
        ("Samples (synth.)", sample_radius,
         2 * (1 - sample_radius ** 2) + random.normal(0, 0.015, len(sample_radius)) * (1 - sample_radius ** 2)),
    ])
    add({
        "id": "M02_mixed_pipe", "kind": "mixed", "frame": mixed_pipe, "group_kind": "categorical",
        "series_styles": {
            "Exact": {"kind": "line", "color": "#0A5270", "linestyle": "-", "line_width": 1.8},
            "CFD (synth.)": {"kind": "point-line", "color": "#D35400", "linestyle": "--", "marker": "s"},
            "Samples (synth.)": {"kind": "scatter", "color": "#2F6DB5", "marker": "^", "marker_size": 5.5},
        },
        "error": {"reference": "Exact", "definition": "signed", "interpolation": "linear",
                  "ylabel": "Signed error in u/Ub"},
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Radius, r/R", "ylabel": "Axial velocity, u/Ub",
        "title": "Pipe: theory, CFD, samples",
        "source": "解析解为纯线，合成 CFD 为点线，合成测点为散点。",
        "meaning": "理论线、数值点和实验点放在同一张层流管流图上，并给出相对解析解的有符号误差。",
        "parameters": "解析解为 401 点纯线；CFD 为 21 个半径上的点线；16 个测点为散点。误差都相对解析解线性插值，不外推。壁面速度为 0，所以不用相对误差。图例放在上图空白处，不遮挡曲线。",
    })

    mixed_boundary = stack([
        ("Blasius", eta_plot, blasius_plot),
        ("CFD (synth.)", eta_plot, blasius_plot - 0.018 * eta_plot * np.exp(-eta_plot / 1.6)),
        ("Samples (synth.)", eta_station,
         np.interp(eta_station, eta, blasius) + random.normal(0, 0.008, len(eta_station)) * np.minimum(eta_station, 1)),
    ])
    add({
        "id": "M03_mixed_blasius", "kind": "mixed", "frame": mixed_boundary, "group_kind": "categorical",
        "series_styles": {
            "Blasius": {"kind": "line", "color": "#0A5270", "linestyle": "-", "line_width": 1.8},
            "CFD (synth.)": {"kind": "line", "color": "#D35400", "linestyle": "--", "line_width": 1.5},
            "Samples (synth.)": {"kind": "scatter", "color": "#AA3377", "marker": "D", "marker_size": 5.2},
        },
        "error": {"reference": "Blasius", "definition": "signed", "interpolation": "linear",
                  "ylabel": "Signed error in u/Uinf"},
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Similarity coordinate, eta", "ylabel": "Velocity, u/Uinf",
        "title": "Boundary layer: three representations",
        "source": "Blasius 打靶解、合成数值线和合成测点。",
        "meaning": "理论线、数值线和离散测点的边界层对比，下图是相对 Blasius 的有符号差。",
        "parameters": "理论与 CFD 在 eta≤8 的打靶网格上精确对齐；测点为 B05 的 25 个站位，线性插值，不外推。",
    })

    scatter_profile = cases[395]["mean"]
    add({
        "id": "C01_scatter_dns", "kind": "scatter",
        "frame": pd.DataFrame({"x": scatter_profile["u_mean"], "y": scatter_profile["uu+"], "series": "Re_tau = 395"}),
        "group_kind": "categorical", "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Mean velocity, u+", "ylabel": "Streamwise stress, uu+",
        "title": "DNS scatter, no connecting line",
        "source": "Kawamura Lab Poi395_4th_D.dat 均值表，同一套 y+ 上的 u_mean 与 uu+。",
        "meaning": "把两个同网格统计量做成散点。点的轨迹看起来像曲线，但图类型要求不连线。",
        "parameters": f"Re_tau=395，{len(scatter_profile)} 个原始点；无拟合、无连线。",
    })

    centerline = pd.DataFrame({
        "x": [f"{re_tau:g}" for re_tau in (180, 395, 640, 1020)],
        "y": [cases[re_tau]["centerline_u_plus"] for re_tau in (180, 395, 640, 1020)],
    })
    add({
        "id": "C02_bar_centerline", "kind": "bar", "frame": centerline, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Friction Reynolds number, Re_tau", "ylabel": "Largest-y+ sample of u+",
        "title": "DNS centerline sample",
        "source": "四个均值表各自 y+ 最大的一行。",
        "meaning": "中心线附近的平均速度样本。柱高不是插值到 y/h=1 的值。",
        "parameters": "Re_tau=180/395/640/1020 的最大 y+ 分别为 "
                      + ", ".join(f"{cases[re_tau]['y_plus_mean'][1]:.2f}" for re_tau in (180, 395, 640, 1020))
                      + "。",
    })

    targets = (1.0, 0.8, 0.5, 0.3, 0.15, 0.05, 0.01)
    heat_rows = []
    heat_notes = []
    for target in targets:
        for re_tau in (180, 395, 640, 1020):
            profile = cases[re_tau]["mean"]
            position = int(np.argmin(np.abs(profile["y_over_h"].to_numpy() - target)))
            actual = float(profile["y_over_h"].iloc[position])
            heat_rows.append({"x": f"{re_tau:g}", "y": f"{target:g}", "u+": float(profile["u_mean"].iloc[position])})
            heat_notes.append((re_tau, target, actual, float(profile["y+"].iloc[position])))
    add({
        "id": "C03_heatmap_velocity", "kind": "heatmap",
        "frame": pd.DataFrame(heat_rows), "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Re_tau", "ylabel": "Nominal y/h",
        "title": "Nearest DNS samples of u+",
        "source": "四个均值表。每个名义 y/h 只取该表中最近的一个原始点。",
        "meaning": "用一张小热图看 u+ 随雷诺数和墙距的变化。这是抽点后的矩阵，不是完整剖面。",
        "parameters": "名义 y/h = 1, 0.8, 0.5, 0.3, 0.15, 0.05, 0.01；最近点数偏差见 manifest 的 heatmap_nearest。",
        "heatmap_nearest": [
            {"Re_tau": re_tau, "nominal_y_over_h": target, "actual_y_over_h": actual, "actual_y_plus": y_plus}
            for re_tau, target, actual, y_plus in heat_notes
        ],
    })

    violin = pd.concat([
        pd.DataFrame({"x": f"{re_tau:g}", "y": cases[re_tau]["mean"]["uu+"].to_numpy()})
        for re_tau in (180, 395, 640, 1020)
    ], ignore_index=True)
    add({
        "id": "C04_violin_uu", "kind": "violin", "frame": violin, "group_kind": "categorical",
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Friction Reynolds number, Re_tau", "ylabel": "Tabulated uu+",
        "title": "Distribution of tabulated uu+",
        "source": "四个均值表的全部 uu+ 行。",
        "meaning": "表格样本的分布形状。近壁点更密，所以这不是按高度均匀抽样的概率密度，也不是实验重复测量。",
        "parameters": "每个小提琴使用该 Re_tau 均值表的全部原始 uu+，不平滑剖面。",
    })

    radius = np.array([0.15, 0.30, 0.45, 0.60, 0.75, 0.90])
    baseline = np.array([1.86, 1.70, 1.46, 1.14, 0.74, 0.28])
    generator = np.random.default_rng(21)
    repeats = {
        "Probe A (synth.)": baseline + generator.normal(0.0, 0.05, size=(4, radius.size)),
        "Probe B (synth.)": baseline - 0.08 + generator.normal(0.0, 0.06, size=(4, radius.size)),
    }
    probes = pd.concat([
        pd.DataFrame({"x": radius, "y": values.mean(axis=0), "sd": values.std(axis=0, ddof=1), "series": label})
        for label, values in repeats.items()
    ], ignore_index=True)
    if (probes["y"] <= 0).any() or (probes["sd"] <= 0).any():
        raise RuntimeError("Synthetic probe summary is not a positive velocity with a positive sample standard deviation")
    add({
        "id": "D01_errorbar_probe", "kind": "point-line", "frame": probes, "group_kind": "categorical",
        "error_bars": {"y": "sd", "definition": "sample standard deviation of 4 synthetic repeats (ddof=1)"},
        "xscale": "linear", "yscale": "linear", "size": "double",
        "xlabel": "Radius, r/R", "ylabel": "Mean axial velocity, u/Ub",
        "title": "Synthetic probe uncertainty",
        "source": "两组人为生成的重复测点，不是实验，也不是 DNS。",
        "meaning": "每个点是 4 次合成重复的平均值，误差棒是这 4 次的样本标准差。它不表示相对解析解的偏差。",
        "parameters": "半径 0.15–0.90；Probe A 以 1.86, 1.70, 1.46, 1.14, 0.74, 0.28 为中心，正态噪声标准差 0.05；"
                      "Probe B 低 0.08，噪声标准差 0.06。生成器种子 21，n=4，ddof=1。"
                      "母板只读取表里的平均值和 sd，不重新计算。",
    })
    return catalog


def marker_name(artist) -> str | None:
    marker = artist.get_marker()
    if marker in (None, "None", "", " "):
        return None
    return str(marker)


def render_catalog(template, catalog: list[dict]) -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audits = []
    for case in catalog:
        frame = case["frame"]
        frame.to_csv(OUTPUT_DIR / f"{case['id']}.csv", index=False)
        kwargs = {
            "kind": case["kind"], "x": "x", "y": "y", "size": case["size"],
            "xlabel": case["xlabel"], "ylabel": case["ylabel"],
            "output": OUTPUT_DIR / case["id"], "formats": ("png",), "dpi": 300,
            "xscale": case["xscale"], "yscale": case["yscale"],
        }
        if case["kind"] == "heatmap":
            kwargs.update(x="x", y="y", value="u+")
        elif case["kind"] in ("line", "point-line", "scatter", "mixed"):
            kwargs.update(group="series", group_kind=case["group_kind"])
        if case.get("series_styles") is not None:
            kwargs["series_styles"] = case["series_styles"]
        if case.get("legend"):
            kwargs["legend"] = case["legend"]
        if case.get("error") is not None:
            kwargs["error"] = case["error"]
        if case.get("error_bars") is not None:
            kwargs["error_bars"] = case["error_bars"]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            figure, axes, paths = template.render_plot(frame, **kwargs)
        warning_text = [str(item.message) for item in caught]
        plotted = [line for line in axes.lines if not getattr(line, "_scientific_errorbar", False)]
        if case["kind"] == "line":
            if any(marker_name(line) is not None for line in plotted):
                raise RuntimeError(f"{case['id']} drew markers on a line plot")
        elif case["kind"] == "point-line":
            if not plotted or any(marker_name(line) is None for line in plotted):
                raise RuntimeError(f"{case['id']} is missing point-line markers")
        elif case["kind"] == "scatter":
            if plotted:
                raise RuntimeError(f"{case['id']} connected a scatter plot")
        elif case["kind"] == "mixed":
            kinds = {label: item["kind"] for label, item in figure.scientific_metadata["series"].items()}
            expected = {label: style["kind"] for label, style in case["series_styles"].items()}
            if kinds != expected:
                raise RuntimeError(f"{case['id']} mixed kinds changed: {kinds}")
        audit = {
            "id": case["id"], "kind": case["kind"], "png": str(paths[0]),
            "rows": int(len(frame)), "warnings": warning_text,
            "source": case["source"], "meaning": case["meaning"], "parameters": case["parameters"],
            "xlabel": case["xlabel"], "ylabel": case["ylabel"], "title": case["title"],
            "xscale": case["xscale"], "yscale": case["yscale"], "size_mm": [183, 136],
            "metadata_series": figure.scientific_metadata.get("series"),
            "markers": [marker_name(line) for line in plotted],
            "line_widths_pt": [float(line.get_linewidth()) for line in plotted],
        }
        uncertainty = figure.scientific_metadata.get("error_bars")
        if uncertainty:
            audit["error_bars"] = {"definition": uncertainty["definition"], "x": uncertainty["x"],
                                   "y": uncertainty["y"], "capsize_pt": uncertainty["capsize_pt"],
                                   "elinewidth_pt": uncertainty["elinewidth_pt"]}
        if case.get("heatmap_nearest") is not None:
            audit["heatmap_nearest"] = case["heatmap_nearest"]
        audits.append(audit)
        plt.close(figure)
    return audits


def write_report(cases: dict[int, dict], second: dict, audits: list[dict], font_name: str) -> None:
    manifest = {
        "source_page": SOURCE_PAGE,
        "font": font_name,
        "files": [{key: value for key, value in case.items() if key not in ("mean", "shear")}
                  for case in (*cases.values(), second)],
        "figures": audits,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CFD 折线与点线测试",
        "",
        f"字体：请求 Arial，实际使用 {font_name}。画布均为双栏 183 × 136 mm，300 dpi，只导出 PNG。",
        "真实数据只来自 Kawamura Lab 充分发展通道流数据库的本地缓存；原始文件保留实验室的权利声明和引用要求。",
        "解析解、残差、圆柱力和带 synth. 的测点都是为测试图类型构造的，不能当作求解器或实验验证。",
        "误差棒是可选项。只有 D01 使用，数值是合成重复测量的样本标准差，不是 DNS 或实验不确定度。",
        "图内不画标题。下面的建议图注留给论文里的 Fig. N，不写进图片。",
        "",
        "## 数据文件",
        "",
    ]
    for case in (*cases.values(), second):
        lines.append(f"- `{case['file']}`：Re_tau={case['Re_tau']:g}，Re_bulk={case['Re_bulk']:g}，"
                     f"均值 {case['mean_rows']} 行，剪切 {case['shear_rows']} 行，"
                     f"交错网格={case['staggered']}，SHA256 `{case['sha256']}`")
    lines.extend(["", "## 图", ""])
    for audit in audits:
        lines.extend([
            f"### {audit['id']}（{audit['kind']}）",
            "",
            f"![{audit['id']}]({audit['id']}.png)",
            "",
            f"- 建议图注：{audit['title']}。",
            f"- 数据来源：{audit['source']}",
            f"- 物理含义：{audit['meaning']}",
            f"- 关键参数：{audit['parameters']}",
            f"- 行数 {audit['rows']}；坐标 {audit['xscale']}/{audit['yscale']}；标记 {audit['markers'] or '无'}；"
            f"线宽 {audit['line_widths_pt'] or '无'} pt。",
        ])
        if audit.get("error_bars"):
            lines.append(f"- 误差棒：{audit['error_bars']['definition']}。")
        lines.extend([
            f"- 警告：{audit['warnings'] or '无'}。",
            "",
        ])
    (OUTPUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    template = load_template()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        font_name = template.resolve_font("Arial")
    if caught:
        print("FONT:", "; ".join(str(item.message) for item in caught))
    else:
        print("FONT:", font_name)
    cases = {re_tau: read_case(RAW_DIR / name) for re_tau, name in RAW_NAMES.items()}
    second = read_case(RAW_DIR / SECOND_ORDER_NAME)
    eta, blasius, curvature = blasius_profile()
    print(f"Blasius f''(0)={curvature:.10f}, u(10)={blasius[-1]:.12f}")
    catalog = build_catalog(cases, second, curvature, eta, blasius)
    audits = render_catalog(template, catalog)
    write_report(cases, second, audits, font_name)
    for audit in audits:
        print(f"{audit['id']:28} rows={audit['rows']:5} markers={audit['markers']} warnings={audit['warnings']}")


if __name__ == "__main__":
    sys.exit(main())
