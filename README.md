# Scientific Plotting Skill

科研数据绘图 Skill + Python 母板：保持统一风格，在不同电脑和项目里复用；默认只导出 JPEG。支持 `point-line`（按原始顺序连点）、`line`、`bar`、`scatter`、`heatmap`、`violin`，以及显式 `mixed` 系列、CFD 对数坐标、参考误差子图和可选误差棒。

## 仓库

GitHub 仓库名是 `scientific-plotting`。可安装的 Skill 只有 `scientific-plotting/`。仓库根目录的说明、依赖和测试不是 Skill 本体；生成图和原始数据不发布。

公开仓库建好后，用 Codex 的安装脚本安装（把 `<OWNER>` 换成 GitHub 用户名）：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo <OWNER>/scientific-plotting \
  --path scientific-plotting
```

Skill 会装到 `${CODEX_HOME:-$HOME/.codex}/skills/scientific-plotting`，下一轮对话用 `$scientific-plotting`。也可以把 `scientific-plotting` 目录复制或链接到同一位置。本仓库不修改 Codex 的全局配置。

## 安装和使用

建议 Python 3.10+，在本仓库运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/observations.csv --kind point-line \
  --x distance --y temperature --group time \
  --xlabel 'Distance (m)' --ylabel 'Temperature (K)' \
  --size double --output /path/to/figures/profile
```

输出 `profile.jpg`、`profile_template.py`（当次所用母板的副本）、`profile_reproduce.py`（重跑命令的脚本）。输入数据仍位于原位置；移动项目或换电脑后，在复现脚本里修改输入路径并安装依赖。不要把个人数据与绘图脚本不经检查地公开发布。脚本支持 `--help` 查看全部参数。

未指定 `--format` 时只写一个 JPEG（`.jpg`，300 dpi，质量 95，无色度抽样）。需要 TIFF 时显式写 `--format tiff`。PNG、SVG、PDF 和 EPS 会直接拒绝。指定期刊后，省略 dpi 的 TIFF 使用该期刊快照的分辨率：Elsevier 线稿 1000 dpi、含热图 500 dpi；JFM 线稿 1200 dpi、含热图 600 dpi；PoF 600 dpi。手动 `--dpi` 始终照做，偏低时只在审查里警告。

Excel 示例：`--input results.xlsx --sheet 0`。矩阵热力图（首列是行标签）使用 `--kind heatmap --index-col sample`；长表热力图指定 `--x condition --y sample --value intensity`。数值型/时间型 `--group` 默认视为连续有序系列，非数值标签如 `t=0.2s` 可指定 `--group-kind ordered`；不同方法使用 `--group-kind categorical`。柱状图的 `--x` 是类别、`--y` 是预先计算的数值；小提琴图的 `--x` 是组名、`--y` 是逐条观测值。

## 在 Python 中复用

```python
from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path("scientific-plotting/scripts").resolve()))
from plot_template import render_plot

observations = {"distance": np.array([0.02, 0.00, 0.01]),
                "temperature": np.array([410, 390, 400])}
figure, axes, paths = render_plot(
    observations, kind="point-line", x="distance", y="temperature",
    xlabel="Distance (m)", ylabel="Temperature (K)",
    output="figures/temperature"
)
plt.close(figure)
```

此例的点按 `0.02 → 0.00 → 0.01` 连线，不做排序。Python API 接受 pandas DataFrame、等长列数组字典；二维 NumPy 数组也可直接作为热力图矩阵。未指定 `output` 时只返回画布而不写文件；CLI 才额外生成复现脚本。

## 仓库里有什么

安装和发布只包含 Skill 本体 `scientific-plotting/`：说明、绘图母板和风格约定。`figures/` 与 `data/` 是本机验证时生成的图和缓存的原始数据，不属于 Skill，也不再放进 GitHub 仓库。克隆后不会自带这些目录。

`examples/` 和 `tests/` 用来在本机检查母板。其中依赖 DNS、反应堆数据或已生成图集的检查，在缺少本地缓存时会跳过。母板本身的测试不需要这些数据：

```bash
.venv/bin/python -m pytest -q tests/test_plot_template.py tests/test_cfd_validation.py
```

## 对数轴、混合系列和误差子图

`line` 是纯线，`point-line` 是按原始顺序连点，`scatter` 是纯散点。混合图必须显式 `--kind mixed`，并为每个系列给出 `kind`。`--xscale` / `--yscale` 支持 `linear`（默认）和 `log`；对数轴出现零或负数会报错，不删除数据。只有线、点线、散点和混合图接受非线性坐标。

残差轴取对数：

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/residuals.csv \
  --kind line --x iteration --y residual --group solver --yscale log \
  --xlabel 'Iteration (-)' --ylabel 'Normalized residual (-)' \
  --output /path/to/figures/residual
```

混合对比和误差子图要把系列配置写成 JSON，键与 CSV 的分组标签一致：

```json
{
  "Theory": {"kind": "line", "linestyle": "-", "color": "#126b80", "line_width": 1.5},
  "CFD": {"kind": "point-line", "linestyle": "--", "marker": "s", "marker_size": 4},
  "Samples": {"kind": "scatter", "marker": "^", "marker_size": 5.5}
}
```

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/profiles.csv \
  --kind mixed --x radius --y velocity --group series --group-kind categorical --size double \
  --series-config /path/to/styles.json \
  --error-reference Theory --error-definition signed --error-interpolation linear \
  --xlabel 'Radius, r/R' --ylabel 'Velocity, u/Ub' --error-ylabel 'Signed error in u/Ub' \
  --output /path/to/figures/profile
```

纯线不接受点形，纯散点不接受连接线型。原生 `line` / `point-line` 可以改外观，但不能在配置里改系列类型。`--legend outside` 会跳过框内位置，把图例排成图顶的横条，顶上放不下再放到底部；不放在左右两侧，不缩小字号，也不加大画布，放不下就报错。论文图不要在图内写标题，标题交给 Fig. N 图注。

```python
figure, axes, paths = render_plot(
    observations, kind="mixed", x="x", y="y", group="series", size="double",
    series_styles=styles,
    error={"reference": "Theory", "definition": "signed", "interpolation": "linear",
           "ylabel": "Signed error in u/Ub"},
    output="figures/comparison",
)
error_axes = figure.scientific_error_axes
audit = figure.scientific_metadata
```

有符号误差是 `y - ref`，绝对误差是 `abs(y - ref)`，相对误差是 `(y - ref) / abs(ref)`。默认按坐标和顺序严格匹配，不按行号硬减，也不排序、外推或平滑。相对误差遇到零参考会报错。误差子图的纵轴保持线性，横轴与主图相同。误差线、阴影和统计标注必须来自已有数据和明确含义，不能为了好看临时添加。

## 可选误差棒

误差棒表示测点自身的不确定度，和上面相对参考曲线的误差子图不是一回事；两者可以同时使用，但误差子图不会继承或换算这些误差棒。

通过 Skill 绘图时，不必每次声明“加上误差棒”。Agent 先看数据：有标准差、标准误、置信区间或上下限这类列，就用该列；同一位置有重复测量、图又该显示汇总结果时，画平均值和样本标准差（ddof=1），并写明 n。一条没有不确定度的曲线，例如 DNS、公式或残差，不加误差棒。只有两种统计量会改变结论、或用户要求互相矛盾时才询问。直接调用母板或命令行时仍要传入幅度和 `definition`，因为脚本不能自行猜测，也不会把标准差换算成标准误或置信区间。


对称误差用一列，上下不对称就同时给下限和上限。幅度与坐标同一单位，允许为 0，不允许负数或空值。对数轴上，误差棒伸到 0 或负数会直接报错，不会裁掉。柱状图只有纵向误差棒，用深灰色画在柱心上。折线、点线、散点和混合图的误差棒跟该系列同色，画在标记后面，每个点都画，不抽稀。

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/repeats.csv \
  --kind point-line --x radius --y velocity --group probe \
  --yerr sd --errorbar-definition 'sample standard deviation, n=4' \
  --xlabel 'Radius, r/R' --ylabel 'Velocity, u/Ub' \
  --output /path/to/figures/uncertainty
```

```python
figure, axes, paths = render_plot(
    observations, kind="point-line", x="radius", y="velocity", group="probe",
    error_bars={"y": "sd", "definition": "sample standard deviation, n=4"},
)
```

不对称时用 `y_lower` 和 `y_upper`（命令行是 `--yerr-lower` 与 `--yerr-upper`）。需要横向误差棒时用 `x` 或 `x_lower`/`x_upper`。`--errorbar-capsize` 是端帽的半长，单位 pt，默认 2.2；`--errorbar-elinewidth` 是线宽，默认 0.8 pt。

## 风格和贡献

默认 Arial（缺失时会警告并改用 Liberation Sans），可选 `--font 'Times New Roman'`（缺失时警告并改用 Liberation Serif）。中文图用 `--font 思源黑体`（Noto Sans CJK SC，未安装时警告并改用文泉驿微米黑）或 `--font 思源宋体`（Noto Serif CJK SC，未安装时警告并改用 AR PL UMing CN）。坐标轴角标直接写 `t^*`、`t^+`、`x^2`、`10^-3`、`t_{wall}`，也可以写 `\(...\)` 或 `$...$`；无量纲时间优先用 `t^*`。单幅图默认接近 4:3：Elsevier 的 `single` 为 90 × 67.5 mm，`medium` 为 140 × 105 mm，`double` 为 190 × 142.5 mm；投 Physics of Fluids 时用 `aip-single` 85 × 63.75 mm 或 `aip-double` 170 × 127.5 mm。点线图等会留出更接近参考图的坐标框四周空间，而不是把坐标框撑满画布。有序时间组仍从琥珀黄走到深蓝绿，但各档更深、明度拉开，避免亮黄和相邻色糊在一起；组数不是 5 时在 Oklab 中插值。不同方法使用另一组区分度更高的分类色（蓝、橙、绿、品红，以及橄榄、红、靛蓝、灰）。线型和点形继续负责黑白辨识。点线图按同一系列相邻点的成图间距调整粗细（不会因其他系列靠近就缩小标记）：稀疏约 6.2 pt、普通约 5.0 pt、较密约 3.8 pt、极密约 2.6 pt，标记为实心，直径不小于 3.6 pt 时加白边。默认点形是圆、方、上三角、菱形、下三角、五边形。散点图独立使用约 6.2 / 5.0 pt 的实心点；密集点使用有限的透明度而不删除数据。如自动尺寸不合适，可分别指定 `--line-width 1.2`（线宽，pt）和 `--marker-size 5`（标记直径，pt；散点面积为直径平方）；Python API 用 `line_width` 和 `marker_size`。四边坐标轴、朝内刻度、主实次虚网格及图例规则见 [风格约定](scientific-plotting/references/style.md)。需要根据新机器安装依赖或替代字体可以直接做；若要改变其他风格，先明确提出要求并检查结果，不要因为缺字体或图例密集就偷偷更改规则。

字号以**实际排版宽度**为准：90 mm 和 85 mm 用坐标名称 10 pt、刻度及图例 8.5 pt；140、170 和 190 mm 用坐标名称 11 pt、刻度及图例 9.5 pt。多面板用 `render_multipanel`，不再使用已经删除的 `multipanel` 尺寸。期刊差异见 [期刊快照](scientific-plotting/references/journals.md)，审查只列差异，不表示已经符合要求。

高星绘图仓库和早期参考的借鉴边界见 [参考记录](scientific-plotting/references/sources.md)。这里没有拷贝其代码、色表或图像。

测试：安装 `pytest` 后运行 `python -m pytest -q`，并在最终尺寸下查看样图，确认图例、标签及四边刻度未被裁切。

## 许可

绘图代码和 Skill 以 MIT 许可发布，版权人为 RuiJin Ma，2026，见仓库根目录 `LICENSE`。本机验证用过的第三方数据不在仓库中，仍须遵守其原始许可和署名。
