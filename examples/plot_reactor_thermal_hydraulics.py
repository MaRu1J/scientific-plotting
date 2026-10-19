"""Reproducible real-data tests of the supplied scientific-plotting skill."""

import argparse
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import warnings
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.text import Text
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
BUNDLE = HERE if (HERE / "raw").is_dir() else HERE.parent / "figures/reactor_thermal_hydraulics"
NPPAD = "https://raw.githubusercontent.com/thu-inet/NuclearPowerPlantAccidentData/main/"
HWAT = "https://zenodo.org/records/14627088/files/"
IAPWS = "https://iapws.org/public/documents/UWTF-/IF97-Rev.pdf"
RUNS = ("09", "10", "13")
COLORS = ("#126b80", "#b16a25", "#75629b")
MARKERS = ("o", "s", "^")
DASHES = ("-", "--", "-.")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_urls():
    sources = {f"LOCA_{severity}.csv": NPPAD + f"Operation_csv_data/LOCA/{severity}.csv"
               for severity in (1, 10, 50)}
    sources.update({"Normal_1.csv": NPPAD + "Operation_csv_data/Normal/1.csv",
                    "SGBTR_10.csv": NPPAD + "Operation_csv_data/SGBTR/10.csv",
                    "NPPAD_README.md": NPPAD + "README.md",
                    "LOCA_1.mdb": NPPAD + "NPPAD/LOCA/1.mdb",
                    "HWAT_record.json": "https://zenodo.org/api/records/14627088",
                    "HWAT_readme.txt": HWAT + "readme.txt",
                    "IF97-Rev.pdf": IAPWS})
    sources.update({f"ID_20230809_Run_{run}.xml": HWAT + f"ID_20230809_Run_{run}.xml" for run in RUNS})
    return sources


def prepare_sources(bundle, download=False):
    raw = bundle / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, url in source_urls().items():
        path = raw / name
        if download and not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "ScientificPlottingRealDataTest/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
            path.write_bytes(content)
        if not path.exists():
            raise FileNotFoundError(f"Missing cached source: {path}; use --download to fetch missing files.")
    lock_path = bundle / "sources.lock.json"
    if lock_path.exists():
        for name, record in json.loads(lock_path.read_text(encoding="utf-8")).items():
            if file_hash(raw / name) != record["sha256"]:
                raise ValueError(f"Cached source does not match its pinned SHA-256: {name}")
    metadata = json.loads((raw / "HWAT_record.json").read_text(encoding="utf-8"))
    checksums = {record["key"]: record["checksum"] for record in metadata["files"]}
    for run in RUNS:
        name = f"ID_20230809_Run_{run}.xml"
        digest = hashlib.md5((raw / name).read_bytes()).hexdigest()
        if checksums[name] != "md5:" + digest:
            raise ValueError(f"Zenodo publisher checksum mismatch: {name}")
    if b"Press RCS (bar)" not in (raw / "LOCA_1.mdb").read_bytes():
        raise ValueError("Original MDB no longer confirms the RCS pressure unit.")
    records = {name: {"url": url, "sha256": file_hash(raw / name), "bytes": (raw / name).stat().st_size}
               for name, url in source_urls().items()}
    write_json(lock_path, records)
    return raw


def load_template(bundle):
    snapshot = bundle / "plot_template_snapshot.py"
    if not snapshot.exists():
        shutil.copy2(HERE.parent / "scientific-plotting/scripts/plot_template.py", snapshot)
    spec = importlib.util.spec_from_file_location("thermal_plot_template", snapshot)
    template = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(template)
    resolve_font = template.resolve_font
    available = {entry.name for entry in font_manager.fontManager.ttflist}
    chinese = next((name for name in ("Noto Sans CJK JP", "Noto Sans CJK SC", "Droid Sans Fallback")
                    if name in available), None)
    if chinese is None:
        raise RuntimeError("A Chinese-capable font is required for bilingual labels.")

    def bilingual_font(requested):
        return [resolve_font(requested), chinese]

    template.resolve_font = bilingual_font
    return template, chinese


def saturation_temperature(pressure_mpa):
    pressure = np.asarray(pressure_mpa, dtype=float)
    if np.any(~np.isfinite(pressure)) or np.any((pressure < 0.000611212677) | (pressure > 22.064)):
        raise ValueError("IAPWS-IF97 region-4 saturation pressure is outside its validity range.")
    coefficients = np.array([1167.0521452767, -724213.16703206, -17.073846940092,
                             12020.824702470, -3232555.0322333, 14.915108613530,
                             -4823.2657361591, 405113.40542057, -0.23855557567849,
                             650.17534844798])
    root_pressure = np.power(pressure, 0.25)
    quadratic = root_pressure ** 2 + coefficients[2] * root_pressure + coefficients[5]
    linear = coefficients[0] * root_pressure ** 2 + coefficients[3] * root_pressure + coefficients[6]
    constant = coefficients[1] * root_pressure ** 2 + coefficients[4] * root_pressure + coefficients[7]
    auxiliary = -2 * constant / (linear + np.sqrt(linear ** 2 - 4 * quadratic * constant))
    temperature_sum = coefficients[9] + auxiliary
    return 0.5 * (temperature_sum - np.sqrt(temperature_sum ** 2
                                           - 4 * (coefficients[8] + coefficients[9] * auxiliary)))


def load_hwat(path):
    root = ET.parse(path).getroot()
    wall = root.find("walltemperature")
    elevation = [float(item.text) for item in wall.findall("ELEVATIONS")]
    temperature = [float(item.text) for item in wall.findall("TWALL")]
    if len(elevation) != len(temperature) or not elevation:
        raise ValueError(f"Unpaired HWAT wall sensors: {path}")
    axial = pd.DataFrame({"sensor": np.arange(1, len(elevation) + 1), "z_m": elevation, "wall_c": temperature})
    radial = pd.DataFrame([{key: float(node.findtext(key)) for key in ("RADIUS", "VOIDFRACTION", "VELOCITY")}
                           for node in root.findall("radial")])
    radial["r_normalized"] = radial["RADIUS"] / radial["RADIUS"].max()
    boundary = {key: float(root.findtext(key)) for key in ("PRESSURE", "TIN", "MASSFLOW", "MASSFLUX", "XIN", "XOUT")}
    assert np.isfinite(axial.to_numpy()).all() and np.isfinite(radial.to_numpy()).all()
    assert radial.VOIDFRACTION.between(0, 1).all()
    return {"axial": axial, "radial": radial, "boundary": boundary, "file": path.name}


def sampled_indices(frame, columns, count=23):
    selected = set(np.linspace(0, len(frame) - 1, min(count, len(frame)), dtype=int))
    for column in columns:
        values = frame[column].to_numpy()
        selected.update((int(values.argmin()), int(values.argmax())))
    early = np.flatnonzero(frame.TIME.to_numpy() <= 300)
    selected.update(early[::3].tolist())
    return np.array(sorted(selected), dtype=int)


def series_styles(frame, kind):
    styles = {}
    for index, label in enumerate(pd.unique(frame.series)):
        style = {"color": COLORS[index % len(COLORS)]}
        if kind != "scatter":
            style["linestyle"] = DASHES[index % len(DASHES)]
        if kind != "line":
            style["marker"] = MARKERS[index % len(MARKERS)]
        styles[label] = style
    return styles


def inspect_plot(figure, axes, frame, options):
    kind = options["kind"]
    checks = {"four_spines": all(spine.get_visible() for spine in axes.spines.values()),
              "title": bool(axes.get_title()), "xlabel": bool(axes.get_xlabel()), "ylabel": bool(axes.get_ylabel()),
              "bilingual_title": "/" in axes.get_title(),
              "print_width_183mm": bool(np.isclose(figure.get_figwidth() * 25.4, 183)),
              "legend_or_colorbar": axes.get_legend() is not None or len(figure.axes) > 1}
    if kind in ("line", "point-line", "scatter"):
        groups = list(frame.groupby("series", sort=False))
        artists = axes.lines if kind != "scatter" else [artist for artist in axes.collections if isinstance(artist, PathCollection)]
        checks["series_count"] = len(groups) == len(artists)
        for index, ((label, rows), artist) in enumerate(zip(groups, artists)):
            observed = np.column_stack((artist.get_xdata(), artist.get_ydata())) if kind != "scatter" else artist.get_offsets()
            checks[f"source_order_{index}"] = bool(np.array_equal(observed, rows[["x", "y"]].to_numpy()))
            if kind != "scatter":
                checks[f"marker_semantics_{index}"] = (artist.get_marker() in (None, "None", "", " ")) == (kind == "line")
                checks[f"connected_{index}"] = artist.get_linestyle() not in (None, "None", "", " ")
            else:
                checks[f"scatter_only_{index}"] = not axes.lines
    elif kind == "heatmap":
        checks["exact_matrix"] = bool(np.array_equal(axes.images[0].get_array(), frame.to_numpy()))
        checks["no_interpolation"] = axes.images[0].get_interpolation() == "nearest"
    elif kind == "bar":
        checks["exact_heights"] = bool(np.array_equal([patch.get_height() for patch in axes.patches], frame.y.to_numpy()))
    else:
        checks["violin_groups"] = sum(isinstance(artist, PolyCollection) for artist in axes.collections) == 3
    major_ticks = axes.xaxis.get_major_ticks() + axes.yaxis.get_major_ticks()
    checks["inward_ticks"] = all(tick._tickdir == "in" for tick in major_ticks)
    checks["both_sides"] = all(tick.tick1line.get_visible() and tick.tick2line.get_visible() for tick in major_ticks)
    if kind != "heatmap":
        checks["major_grid"] = any(tick.gridline.get_visible() and tick.gridline.get_linestyle() == "-" for tick in axes.yaxis.get_major_ticks())
        checks["minor_grid"] = any(tick.gridline.get_visible() and tick.gridline.get_linestyle() == "--" for tick in axes.yaxis.get_minor_ticks())
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    if kind in ("bar", "violin"):
        checks["filled_legend_outside"] = not axes.get_window_extent(renderer).overlaps(axes.get_legend().get_window_extent(renderer))
    checks["text_within_canvas"] = all(figure.bbox.contains(*text.get_window_extent(renderer).p0)
                                       and figure.bbox.contains(*text.get_window_extent(renderer).p1)
                                       for text in figure.findobj(Text)
                                       if text.get_visible() and text.get_text() and not text.get_text().isspace()
                                       and text.axes is not None and text in (text.axes.title, text.axes.xaxis.label, text.axes.yaxis.label))
    if not all(checks.values()):
        raise AssertionError({name: state for name, state in checks.items() if not state})
    return checks


def create_gallery(bundle, records):
    cards = []
    for record in records:
        title = html.escape(record["title"])
        cards.append(f'<article><a href="{record["png"]}"><img src="{record["png"]}" alt="{title}"></a>'
                     f'<h2>{record["number"]:02d} · {record["kind"]}</h2><p>{title}</p>'
                     f'<p>{html.escape(record["focus"])}</p></article>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>热工水力真实数据绘图测试</title>'
    page += '<style>body{font-family:sans-serif;margin:2rem;background:#f1f4f6;color:#18303b}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:1rem}article{background:white;padding:1rem;border-radius:8px}img{width:100%}h2{font-size:18px}p{line-height:1.5}</style>'
    page += '<h1>热工水力真实数据：scientific-plotting skill 测试</h1><p>14 张；line + point-line = 10/14 = 71.4%。PNG 为 183 × 136 mm、300 dpi。缩略图不代表印刷字号。</p>'
    page += '<p>NPPAD 为 PCTRAN 模拟，不是实验；HWAT 为实验；IAPWS 仅作入口压力下饱和温度参照，不是壁温预测。径向采用 r/r_max,meas，不推断管径。</p><main>' + ''.join(cards) + '</main></html>'
    (bundle / "index.html").write_text(page, encoding="utf-8")
    font = ImageFont.truetype(font_manager.findfont("Liberation Sans"), 21)
    for name, selection in (("preview_main", records[:10]), ("preview_other", records[10:])):
        tile_width, tile_height = 720, 570
        canvas = Image.new("RGB", (tile_width * 2, tile_height * ((len(selection) + 1) // 2)), "#edf1f3")
        drawing = ImageDraw.Draw(canvas)
        for index, record in enumerate(selection):
            image = Image.open(bundle / record["png"]).convert("RGB")
            image.thumbnail((710, 530), Image.Resampling.LANCZOS)
            left, top = (index % 2) * tile_width, (index // 2) * tile_height
            canvas.paste(image, (left + (tile_width - image.width) // 2, top))
            drawing.text((left + 20, top + 535), f'{record["number"]:02d} | {record["kind"]} | {record["source_short"]}', fill="#18303b", font=font)
        canvas.save(bundle / f"{name}.png")


def write_report(bundle, records, audit, hwat, nppad, chinese):
    lines = ["# 核反应堆热工水力科研绘图 skill 实测报告", "", "## 结果与复现", "",
             "- 共 14 张独立科研图：4 张 line、6 张 point-line，合计 10/14 = **71.43%**；scatter、bar、heatmap、violin 各 1 张。",
             "- 所有科学数据图使用提供的 `scientific-plotting/scripts/plot_template.py` 的 `render_plot`；未使用其他绘图库替代模板，未修改原 skill。",
             "- PNG only，300 dpi，double 预设 183 × 136 mm。`preview_*.png` 仅为索引缩略图，不计入图数；印刷请使用各图原文件。",
             f"- Arial 不可用，按 skill 回退到 Liberation Sans；中文按字形回退到 {chinese}。运行器只适配字体解析返回字体链，不改变模板色彩、线宽、字号、边框、刻度或版式规则。",
             "- `plot_template_snapshot.py` 是此次使用模板的逐字节快照；`reproduce.py`、`raw/`、`data/`、`sources.lock.json`、`manifest.json`、`audit.json` 可离线复现。",
             "- 在本目录运行：`../../.venv/bin/python reproduce.py`；或使用装有 numpy/pandas/matplotlib/Pillow 的 Python。移动整个目录后，运行 `python reproduce.py`。",
             "- 可用 `python reproduce.py --output-dir /tmp/reactor-replay` 向新目录复现；默认只读缓存且校验 SHA-256，不联网。`--download` 只下载缺失的原文件。",
             "", "## 数据真实性与边界", "",
             "1. **NPPAD 是公开的 PCTRAN 模拟数据，不是核电厂实测，也不是 HWAT 的模拟解。** LOCA 的 1、10、50 分别表示 100 cm² 基准面积的 1%、10%、50%，即 1、10、50 cm²；SGBTR/10 为一根完整管破口的 10%。正常运行仅作为数值基线，不冒充实验验证。",
             "2. README 表格遗漏 `P`，所以另外下载原始 LOCA/1.mdb，以数据库中明确的 `Press RCS (bar)` 核实一次系统压力单位。P 和 PSGA/PSGB 均由 bar × 0.1 转为 MPa；VOID 保留原始百分数。THA 是热段 A 温度，**不改称堆芯出口温度**；TPCT 是模拟峰值包壳温度。",
             "3. **HWAT 是实验数据**，使用 2023-08-09 Run 09、10、13；XML 文件逐个通过发布者 Zenodo MD5 校验。z 为 m，壁温为 °C，速度按发布说明为 m/s，空泡份额无量纲。Run 09 与 10 边界接近，仅称邻近工况，不宣称严格重复性实验。Run 13 入口温度不同。",
             "4. XML 的 RADIUS 约 0.34–7.77，而说明笼统称 SI，存在单位歧义。本任务不擅自把它标成 m 或 mm，而逐工况使用 `r / max(RADIUS)`；分母为**最外侧实测坐标**，不是管壁半径 R，各工况坐标各自保留，未插值至共同网格。",
             "5. XML 的 POWER、HEATFLUX 数量级与小流量加热回路不相称，且动态压力单位未另行核实，因此**不使用这些字段，不自行乘除 1000 修正**；多工况标签采用可核验的入口温度，不标可疑功率。",
             "6. 图 10 的理论参照由 IAPWS-IF97 饱和线 Eq. (31)、Table 34 计算，使用该工况入口压力。它是恒压近似的饱和温度基准，**不是轴向局部饱和温度实测、不是壁温解析解，也不是 CFD 壁温预测**。因数据源未提供同工况计算壁温，本任务不伪造“计算 vs 实验”的验证对。",
             "7. 图 07、10 保留同一 z 的多支热电偶，严格按 XML 原顺序连线；同 z 的垂直连接仅是测点连接，并非轴向温度梯度。空间点线图不抽样、不去重、不拟合、不平滑。",
             "8. 时序 line 保留全量记录。图 05、06 为避免点密集，保留 23 个等行距基础点、0–300 s 每隔三条记录，以及指定参数的精确极值；只按行号升序取原始行，不改时间和值。每个抽样图的 CSV 包含原始 `source_row`，manifest 记录被保留行。无插值，无推测的事故注入时刻。",
             "9. 图 12 用完整时序 TPCT 的 max，而非对抽样结果取峰值；图 13 为**轴向传感器 × 实验工况**实测壁温矩阵，不假造径向–轴向温度场。同高度多支热电偶按传感器号区分，无重复格聚合。",
             "10. 图 14 的 violin 使用每个工况全部 23 个壁温传感器，表示**空间样本**的 KDE 分布，不是时间波动、重复测量不确定度或置信区间；KDE 只是 skill 自带 violin 展示，不作为物理拟合。",
             "11. NPPAD VOID 有约 10⁻⁶ % 的微负值，视为源文件数值残差，原样保留且在 audit 记录，不夹到零、不静默删除。各时序长度不同，画各自真实时间区间，不外推。",
             "", "## 来源", "",
             "- NPPAD：[GitHub](https://github.com/thu-inet/NuclearPowerPlantAccidentData)；Qi et al., Scientific Data (2022), DOI: 10.1038/s41597-022-01879-1；仓库 MIT。具体下载地址、字节数、SHA-256 见 sources.lock.json。",
             "- KTH/HWAT：Le Corre, Li, Grishchenko, Kipiela, Persson, Kudinov & Anglart, *KTH/HWAT loop: 2023 experimental databank for the internal structure of boiling two-phase water flow under LWR core operating conditions*, Zenodo, 2025-01-10, [DOI: 10.5281/zenodo.14627088](https://doi.org/10.5281/zenodo.14627088)，CC BY 4.0。",
             f"- IAPWS：[Revised Release on IF97 (2007)]({IAPWS})，Region 4, Eq. (31), Tables 34/36；官方 PDF 缓存在 raw/IF97-Rev.pdf。",
             "", "## 下载／解析问题与替代", "",
             "- GitHub 递归树及部分目录 API 出现 TLS EOF；改用相同公开仓库的 raw CSV 下载，成功。正常工况目录实际为 `Normal/1.csv`，不是按类别缩写猜测的 `NORM/0.csv`；404 文件未用于任何图。",
             "- **skill 测试发现**：原模板的 grouped bar 在 `_sync_legend → _copy_identity` 中将 BarContainer 当作 Line2D，调用不存在的 `get_color()` 而失败。本图集仅需单系列汇总柱状图，因此使用原生非分组 `bar`，给已有矩形设置计算结果标签，再调用模板的图例放置函数。未改动 skill；不把 grouped bar 判为通过。violin 同样给模板已有的 body 设置分类标签；heatmap 色标补充中英文单位。",
             "- 原模板自动图例避让依据线与散点，不识别柱体／violin 的填充区域；视觉检查发现默认顶部图例可能遮住顶部数据。因此图 12、14 显式使用模板 `outside` 图例，保持原 183 × 136 mm 画布和字号，增加图例与数据轴不相交断言。",
             "- 可选 MSR DOI 10.5281/zenodo.7821694 的元数据可访问，唯一压缩包为 359,198,346 字节；尝试范围下载获取 ZIP 目录时 TLS 失败，立即放弃该可选数据，采用已成功下载的 HWAT 和 NPPAD，不制造多方法剖面。MSR 元数据仅作失败记录，不参与绘图。",
             "- 无需登录、无付费数据。公开网络只用于获取原始文件和来源说明，生成/复现可完全离线。",
             "", "## 工况边界", "", "| HWAT Run | p_in / MPa | T_in / °C | G / kg m⁻² s⁻¹ | x_out / − |", "|---|---:|---:|---:|---:|"]
    for run, record in hwat.items():
        boundary = record["boundary"]
        lines.append(f'| {run} | {boundary["PRESSURE"] / 1e6:.5f} | {boundary["TIN"]:.4f} | {boundary["MASSFLUX"]:.4f} | {boundary["XOUT"]:.5f} |')
    lines.extend(["", "## 图编号 – 图类型 – 数据来源 – 测试重点", "",
                  "| 图编号 | 图类型 | 数据来源／数据类型 | 测试重点 |", "|---|---|---|---|"])
    for record in records:
        lines.append(f'| {record["number"]:02d} | {record["kind"]} | {record["source_short"]}；{record["data_type"]} | {record["focus"]} |')
    lines.extend(["", "## 自动验证", "",
                  f'- {len(records)} 张图的 {sum(len(record["checks"]) for record in records)} 项图级断言全部通过：原始／选取行顺序和值、line 无点、point-line 有点有线、scatter 不连线、bar 高度、heatmap 原矩阵和 nearest、四边框、双侧内刻度、主次网格、标题、轴标签、图例或色标、画布范围、183 mm 物理宽度。',
                  "- IAPWS 在 0.1、1、10 MPa 的输出通过官方 Table 36 的 1e-6 K 精度校验。",
                  "- 每图样式选项在 data/*_options.json，输入在 data/*.csv；PNG 的 SHA-256、尺寸、标记及线宽记录在 manifest.json。所有标题、标签和图例的缺字警告会令生成失败。",
                  "- 视觉复核见 VALIDATION.md；线型、点形冗余兼顾灰度识别，未宣称经过正式色觉缺陷测试。", ""])
    (bundle / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def build(bundle, output=None, download=False):
    raw = prepare_sources(bundle, download)
    destination = Path(output).resolve() if output else bundle
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "data").mkdir(exist_ok=True)
    template, chinese = load_template(bundle)
    nppad = {name: pd.read_csv(raw / f"{name}.csv") for name in ("LOCA_1", "LOCA_10", "LOCA_50", "SGBTR_10", "Normal_1")}
    for name, frame in nppad.items():
        if not frame.TIME.is_monotonic_increasing or frame.TIME.duplicated().any():
            raise ValueError(f"Nonmonotone or repeated source time: {name}")
        if not np.isfinite(frame.to_numpy(dtype=float)).all():
            raise ValueError(f"Nonfinite source data: {name}")
        frame["source_row"] = np.arange(len(frame))
    hwat = {run: load_hwat(raw / f"ID_20230809_Run_{run}.xml") for run in RUNS}
    np.testing.assert_allclose(saturation_temperature([0.1, 1, 10]), [372.755919, 453.035632, 584.149488], rtol=0, atol=1e-6)
    records = []

    def draw(number, slug, frame, kind, title, xlabel, ylabel, source_short, data_type, focus, sources, notes, **extra):
        stem = f"{number:02d}_{slug}"
        options = {"kind": kind, "title": title, "xlabel": xlabel, "ylabel": ylabel, "size": "double", "dpi": 300}
        if kind in ("line", "point-line", "scatter"):
            options.update(x="x", y="y", group="series", group_kind="categorical", series_styles=series_styles(frame, kind))
        elif kind in ("bar", "violin"):
            options.update(x="x", y="y", legend="outside")
        options.update(extra)
        frame.to_csv(destination / "data" / f"{stem}.csv", index=kind == "heatmap")
        write_json(destination / "data" / f"{stem}_options.json", options)
        with warnings.catch_warnings(record=True) as captured, matplotlib.rc_context({"font.family": ["Liberation Sans", chinese]}):
            warnings.simplefilter("always")
            figure, axes, _ = template.render_plot(frame, **options)
            if kind == "violin":
                bodies = [artist for artist in axes.collections if isinstance(artist, PolyCollection)]
                for run, body in zip(RUNS, bodies):
                    body.set_label(f"实验 / Exp. R{run}")
                template._place_legend(figure, axes, "double", options["legend"])
                template._hide_edge_grids(axes)
                template._check_text_layout(figure)
            if kind == "bar":
                axes.patches[0].set_label("计算 / Calculation")
                template._place_legend(figure, axes, "double", options["legend"])
                template._hide_edge_grids(axes)
                template._check_text_layout(figure)
            if kind == "heatmap":
                figure.axes[1].set_ylabel("壁温 / Wall T (°C)")
                figure.tight_layout(pad=1.0)
                template._check_text_layout(figure)
            checks = inspect_plot(figure, axes, frame, options)
            figure.savefig(destination / f"{stem}.png", dpi=300, facecolor="white")
            missing = sorted(set(str(item.message) for item in captured if "Glyph" in str(item.message) and "missing" in str(item.message)))
            if missing:
                raise RuntimeError(f"Missing glyphs in bilingual figure: {missing}")
        paths = destination / f"{stem}.png"
        with Image.open(paths) as image:
            pixels = list(image.size)
        record = {"number": number, "kind": kind, "title": title, "png": paths.name, "source_short": source_short,
                  "data_type": data_type, "focus": focus, "sources": sources, "notes": notes, "rows": len(frame),
                  "sha256": file_hash(paths), "pixels": pixels, "checks": checks,
                  "metadata": getattr(figure, "scientific_metadata", {}),
                  "warnings": sorted(set(str(item.message) for item in captured))}
        if "source_row" in frame:
            record["selected_source_rows"] = {str(label): [int(row) for row in rows.source_row]
                                               for label, rows in frame.groupby("series", sort=False)}
        records.append(record)
        plt.close(figure)
        print(f"{number:02d} {kind}: {paths.name}", flush=True)

    def transient_frame(column, factor=1):
        return pd.concat([pd.DataFrame({"x": frame.TIME, "y": frame[column] * factor,
                                        "series": f"计算 / Calc. {severity} cm²", "source_row": frame.source_row})
                          for severity in (1, 10, 50) for frame in [nppad[f"LOCA_{severity}"]]], ignore_index=True)

    loca_sources = [f"LOCA_{severity}.csv" for severity in (1, 10, 50)]
    common = "完整时序，未抽样；保留原始时间与行序，工况各自真实时长。"
    for number, slug, column, factor, title, ylabel in (
            (1, "loca_pressure_line", "P", .1, "失水事故一回路压力 / LOCA primary pressure", "一回路压力 / Pressure (MPa)"),
            (2, "loca_hotleg_line", "THA", 1, "失水事故热段温度 / LOCA hot-leg temperature", "热段 A 温度 / Hot-leg A T (°C)"),
            (3, "loca_void_line", "VOID", 1, "失水事故系统空泡率 / LOCA system void", "系统空泡率 / RCS void (%)")):
        draw(number, slug, transient_frame(column, factor), "line", title, "时间 / Time (s)", ylabel,
             "NPPAD", "PCTRAN 多破口模拟时序", "全量纯连线无点；多工况颜色＋线型；单位转换" if number == 1 else "纯 line 无标记；多工况原序连线",
             loca_sources, common)
    sgtr = nppad["SGBTR_10"]
    frame = pd.concat([pd.DataFrame({"x": sgtr.TIME, "y": sgtr[column] * .1, "series": f"计算 / Calc. SG {loop}", "source_row": sgtr.source_row})
                       for loop, column in (("A", "PSGA"), ("B", "PSGB"))], ignore_index=True)
    draw(4, "sgtr_secondary_line", frame, "line", "蒸汽发生器破管瞬态 / SGTR secondary pressure", "时间 / Time (s)",
         "蒸汽压力 / Steam pressure (MPa)", "NPPAD", "PCTRAN SG A/B 模拟时序", "纯连线；同工况不同回路；虚实线冗余", ["SGBTR_10.csv"], common)
    series = []
    for name, label in (("LOCA_10", "计算 / Calc. LOCA 10"), ("Normal_1", "参考 / Ref. normal")):
        frame = nppad[name]
        selected = frame.iloc[sampled_indices(frame, ["P"])]
        series.append(pd.DataFrame({"x": selected.TIME, "y": selected.P * .1, "series": label, "source_row": selected.source_row}))
    draw(5, "loca_reference_pointline", pd.concat(series, ignore_index=True), "point-line",
         "事故与数值基线 / Accident vs numerical baseline", "时间 / Time (s)", "一回路压力 / Pressure (MPa)", "NPPAD",
         "事故计算＋正常运行数值参考", "双系列均有点有线；关键极值保留；明确数值参考非实验", ["LOCA_10.csv", "Normal_1.csv"],
         "正常工况不是实验。各自抽样，不插值、不强制同一时长。")
    frame = nppad["LOCA_10"]
    selected = frame.iloc[sampled_indices(frame, ["THA", "TSAT"])]
    series = [pd.DataFrame({"x": selected.TIME, "y": selected[column], "series": label, "source_row": selected.source_row})
              for column, label in (("THA", "计算 / Calc. hot leg"), ("TSAT", "计算 / Calc. PZR sat."))]
    draw(6, "loca_temperature_pointline", pd.concat(series, ignore_index=True), "point-line",
         "失水事故温度响应 / LOCA temperature response", "时间 / Time (s)", "温度 / Temperature (°C)", "NPPAD",
         "热段与稳压器饱和温度模拟时序", "不同点形＋线型；瞬态取样与精确极值；不伪称解析解", ["LOCA_10.csv"],
         "TSAT 是源模拟器的稳压器饱和温度变量，不是实验或外加壁温理论解。")
    def spatial_frame(section, xcolumn, ycolumn):
        return pd.concat([pd.DataFrame({"x": record[section][xcolumn], "y": record[section][ycolumn],
                                        "series": f"实验 / Exp. R{run}", "source_row": np.arange(len(record[section]))})
                          for run, record in hwat.items()], ignore_index=True)

    xml_sources = [hwat[run]["file"] for run in RUNS]
    draw(7, "hwat_axial_pointline", spatial_frame("axial", "z_m", "wall_c"), "point-line",
         "沸腾回路轴向壁温 / Axial wall temperature", "轴向高度 / Axial height z (m)", "壁面温度 / Wall T (°C)", "KTH/HWAT",
         "3 个工况的轴向热电偶实验", "原生 point-line；不排序；保留同 z 多传感器；多工况对比", xml_sources,
         "保留 XML 下降 z 顺序；同 z 连线不解释为空间轴向梯度。R09/R10 入口约159°C；R13约202°C。")
    draw(8, "hwat_radial_void_pointline", spatial_frame("radial", "r_normalized", "VOIDFRACTION"), "point-line",
         "径向空泡份额 / Radial void fraction", "径向位置 / r/r_max,meas (−)", "空泡份额 / Void fraction (−)", "KTH/HWAT",
         "3 个工况的径向空泡实验", "径向 point-line；各自原网格；归一化坐标不猜单位", xml_sources,
         "每组保留全部12测点；r_max,meas是最外侧测量位置，不是管半径R；未对齐或插值。")
    draw(9, "hwat_radial_velocity_pointline", spatial_frame("radial", "r_normalized", "VELOCITY"), "point-line",
         "径向速度分布 / Radial velocity profiles", "径向位置 / r/r_max,meas (−)", "速度 / Velocity (m/s)", "KTH/HWAT",
         "3 个工况的径向速度实验", "不同点形与虚实线；径向原序；全部测量点", xml_sources,
         "速度保留源 VELOCITY 变量名，不在来源未明示时自行改称液相或气相速度。")
    wall = hwat["10"]["axial"]
    saturation_c = float(saturation_temperature(hwat["10"]["boundary"]["PRESSURE"] / 1e6)) - 273.15
    series = pd.concat([pd.DataFrame({"x": wall.z_m, "y": wall.wall_c, "series": "实验 / Exp. wall R10"}),
                        pd.DataFrame({"x": wall.z_m, "y": saturation_c, "series": "理论 / Analytical sat."})], ignore_index=True)
    draw(10, "hwat_saturation_pointline", series, "point-line", "壁温与饱和参照 / Wall T vs saturation reference",
         "轴向高度 / Axial height z (m)", "温度 / Temperature (°C)", "HWAT + IAPWS", "实验壁温＋官方饱和温度理论参照",
         "实验与理论参照同为点线；明确恒入口压力近似而非壁温预测", [hwat["10"]["file"], "IF97-Rev.pdf"],
         f"IAPWS Eq.(31), p_in={hwat['10']['boundary']['PRESSURE'] / 1e6:.8f} MPa, Tsat={saturation_c:.6f} °C；不计算壁温误差。")
    draw(11, "hwat_scatter", spatial_frame("radial", "VOIDFRACTION", "VELOCITY"), "scatter",
         "径向测点相态关系 / Radial measurement phase relation", "空泡份额 / Void fraction (−)", "速度 / Velocity (m/s)", "KTH/HWAT",
         "同一径向测点的空泡与速度实验配对", "只显示点不连线；多组重叠点形区分；不拟合", xml_sources,
         "x/y严格来自同一XML radial元素，不重排、不拟合。")
    frame = pd.DataFrame({"x": ["1 cm²", "10 cm²", "50 cm²"], "y": [nppad[f"LOCA_{severity}"].TPCT.max() for severity in (1, 10, 50)],
                          "series": "计算 / Calculation"})
    draw(12, "loca_peak_clad_bar", frame, "bar", "破口工况峰值包壳温度 / Peak clad temperature", "破口面积 / Break area (cm²)",
         "峰值包壳温度 / Peak clad T (°C)", "NPPAD", "完整TPCT时序最大值的明确汇总", "预聚合bar；不从抽样数据求峰值；边框与图例", loca_sources,
         "每个bar=max(完整TPCT时序)；各工况记录时长不同，不解释为统一终止时刻的温度。")
    elevations = hwat["09"]["axial"].z_m.to_numpy()
    if not all(np.array_equal(record["axial"].z_m, elevations) for record in hwat.values()):
        raise ValueError("HWAT axial grids differ; do not build an aligned matrix without authorization.")
    matrix = pd.DataFrame({f"实验 / Exp. R{run}": record["axial"].wall_c.to_numpy() for run, record in hwat.items()},
                          index=[f"{sensor:02d}: {elevation:.2f}" for sensor, elevation in enumerate(elevations, 1)])
    draw(13, "hwat_axial_heatmap", matrix, "heatmap", "轴向壁温实测矩阵 / Measured axial wall T",
         "实验工况 / Experimental run (−)", "测点号: 轴向高度 / Sensor: z (m)", "KTH/HWAT", "23传感器×3实验工况的实测矩阵",
         "原生heatmap；cividis色标；无空间插值；同z传感器分别保留", xml_sources,
         "仅为轴向传感器×工况，不是虚构的径向–轴向温度场；色标作为连续变量图例。")
    frame = pd.concat([pd.DataFrame({"x": f"R{run}", "y": record["axial"].wall_c}) for run, record in hwat.items()], ignore_index=True)
    draw(14, "hwat_wall_violin", frame, "violin", "壁温空间样本分布 / Spatial wall-T distribution",
         "实验工况 / Experimental run (−)", "壁面温度 / Wall T (°C)", "KTH/HWAT", "每组23支热电偶的空间样本",
         "原生violin KDE；全部实测值；分类图例；非测量置信区间", xml_sources,
         "KDE表示空间样本分布，非时间重复测量；不标虚构误差棒或显著性。")
    assert len(records) == 14
    counts = {kind: sum(record["kind"] == kind for record in records) for kind in template.KINDS if kind != "mixed"}
    assert (counts["line"] + counts["point-line"]) / len(records) >= .7
    audit = {"figure_count": len(records), "kind_counts": counts, "line_pointline_fraction": 10 / 14,
             "all_checks_pass": all(all(record["checks"].values()) for record in records), "chinese_font": chinese,
             "template_sha256": file_hash(bundle / "plot_template_snapshot.py"),
             "iapws_check_pressures_mpa": [.1, 1, 10], "iapws_check_temperatures_k": saturation_temperature([.1, 1, 10]).tolist(),
             "nppad_source_rows": {name: len(frame) for name, frame in nppad.items()},
             "nppad_void_min_percent": {name: float(frame.VOID.min()) for name, frame in nppad.items()},
             "hwat_boundaries": {run: record["boundary"] for run, record in hwat.items()},
             "hwat_zenodo_md5_verified": True, "primary_pressure_unit_verified_from_mdb": True}
    write_json(destination / "manifest.json", records)
    write_json(destination / "audit.json", audit)
    create_gallery(destination, records)
    write_report(destination, records, audit, hwat, nppad, chinese)
    if destination == bundle and Path(__file__).resolve() != bundle / "reproduce.py":
        shutil.copy2(Path(__file__), bundle / "reproduce.py")
    print(f"PASS: 14 figures, line + point-line = {10 / 14:.2%}", flush=True)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--download", action="store_true", help="Download missing pinned-source files; default is offline.")
    arguments = parser.parse_args()
    build(BUNDLE, output=arguments.output_dir, download=arguments.download)
