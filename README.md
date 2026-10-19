# Scientific Plotting Skill

科研数据绘图 Skill + Python 母板：保持统一风格，在不同电脑和项目里复用；默认只导出 PNG。支持 `point-line`（按原始顺序连点）、`line`、`bar`、`scatter`、`heatmap`、`violin`，以及显式 `mixed` 系列、CFD 对数坐标与参考误差子图。

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

输出 `profile.png`、`profile_template.py`（当次所用母板的副本）、`profile_reproduce.py`（重跑命令的脚本）。输入数据仍位于原位置；移动项目或换电脑后，在复现脚本里修改输入路径并安装依赖。不要把个人数据与绘图脚本不经检查地公开发布。脚本支持 `--help` 查看全部参数。

需要其他格式时显式多次指定 `--format`，例如 `--format svg --format pdf --format tiff --format eps`；如果还需要 PNG，额外加 `--format png`。`--format` 未指定时只有 PNG。常见用途：PNG 快速分享/汇报；SVG 可编辑矢量；PDF 排版；TIFF/EPS 按投稿要求启用。导出的 TIFF/PNG 默认为 300 dpi，`--dpi 600` 可提升；SVG/PDF/EPS 不依赖 dpi 定义矢量清晰度。EPS 不使用透明填充。

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
    output="figures/temperature", formats=["png"]
)
plt.close(figure)
```

此例的点按 `0.02 → 0.00 → 0.01` 连线，不做排序。Python API 接受 pandas DataFrame、等长列数组字典；二维 NumPy 数组也可直接作为热力图矩阵。未指定 `output` 时只返回画布而不写文件；CLI 才额外生成复现脚本。

## CFD 系统测试

`examples/test_cfd_plotting.py` 使用 Kawamura Lab 的真实通道流 DNS 文本数据，以及明确标注的解析/理论参考与合成示意数据，优先验证 5 个 `line` 和 5 个 `point-line` 场景，再生成 2 个纯线+散点混合补充图，最后简单验证另外四种图形。DNS 文件缓存于 `data/cfd_validation/raw/`，保留原作者的署名和引用要求；不同物理量的交错网格分别保留，不按相同序号误合并。合成曲线不能用于声明 CFD 模型或求解器获得物理验证。

```bash
.venv/bin/python examples/test_cfd_plotting.py
.venv/bin/python -m pytest -q
.venv/bin/python figures/cfd_validation/reproduce.py
```

输出目录 `figures/cfd_validation/` 是保留的上一轮基线，包含 16 张 PNG、逐图输入 CSV、数据源/校验和/审计记录 `manifest.json`、中文报告、画廊和离线复现快照。旧快照保留当时通过 Axes 实现的对数轴及混合图方式；当前母板已原生支持这些功能，不需手工叠图。

## CFD 原生增强

原有调用默认不变：`line` 所有组纯线，`point-line` 所有组点+线，`scatter` 纯散点；混合图必须显式 `--kind mixed`。`--xscale` / `--yscale` 支持 `linear`（默认）和 `log`，对数轴输入出现零或负数会报错，不删除数据。仅线、点线、散点和混合图接受非线性坐标。

先生成本轮独立图集（仅读取已缓存 DNS，不联网、不覆盖旧图）：

```bash
.venv/bin/python examples/validate_cfd_optimization.py
.venv/bin/python figures/cfd_optimization/reproduce.py
.venv/bin/python -m pytest -q
```

`figures/cfd_optimization/` 包含 13 张原生验证图、3 张总览及黑白复核图、输入 CSV、逐图参数与系列 JSON、原始 DNS 校验和、`manifest.json`、`audit.json`、误差定义/插值记录、母板和运行脚本快照。复制整个目录后可离线运行 `reproduce.py`，无需原仓库或原始 DNS 路径；需要当前项目已有的 Python 科学计算依赖及 Pillow。`REPORT.md` 和 `VALIDATION.md` 记录图像检查与验证结果。

### CLI 示例

残差收敛（保留迭代 0，只有残差轴取对数）：

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input figures/cfd_optimization/data/01_residual_single.csv \
  --kind line --x x --y y --group series --yscale log \
  --xlabel 'Iteration (-)' --ylabel 'Normalized residual (-)' \
  --output figures/cfd_optimization/cli_residual
```

混合泊肃叶流对比及误差子图（使用图集内实际交付的系列配置）：

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input figures/cfd_optimization/data/05_pipe_error_double.csv \
  --kind mixed --x x --y y --group series --group-kind categorical --size double \
  --series-config figures/cfd_optimization/data/05_pipe_error_double_styles.json \
  --error-reference Theory --error-definition signed --error-interpolation linear \
  --xlabel 'Radius, r/R' --ylabel 'Velocity, u/Ub' --error-ylabel 'Signed error in u/Ub' \
  --output figures/cfd_optimization/cli_pipe
```

系列配置形如（键必须与 CSV 分组标签一致）：

```json
{
  "Theory": {"kind": "line", "linestyle": "-", "color": "#126b80", "line_width": 1.8},
  "CFD (synth.)": {"kind": "point-line", "linestyle": "--", "marker": "s", "marker_size": 4},
  "Samples (synth.)": {"kind": "scatter", "marker": "^", "marker_size": 5.5}
}
```

配置可按系列指定线型、点形、颜色、线宽与点径；纯线不接受点形，纯散点不接受连接线型。原生 `line`/`point-line` 也接受配置外观，但不允许在配置中偷偷改变系列类型。全局尺寸覆盖自动值，系列尺寸再覆盖全局值。`--legend outside` 显式外置：优先右侧，长标签尝试上方，不缩字号、不加大画布；仍放不下则明确报错。

CLI 默认仍只导出 PNG 图像，原有母板副本和启动器保留，额外固定一份系列 JSON 防止源配置丢失。启用误差子图后增加 `*_metadata.json` 记录公式、参考和逐组比较方法。通用 CLI 启动器仍记录绝对输入路径，数据移动需改路径；上述完整图集的复现包则可整体搬移。

### Python 误差对比

```python
figure, axes, paths = render_plot(
    observations, kind="mixed", x="x", y="y", group="series", size="double",
    xscale="linear", yscale="linear", series_styles=styles,
    error={"reference": "Theory", "definition": "signed", "interpolation": "linear",
           "ylabel": "Signed error in u/Ub"},
    output="figures/comparison",
)
error_axes = figure.scientific_error_axes
audit = figure.scientific_metadata
```

这里 `observations`/`styles` 是调用方自己的长表和配置；可用图集 CSV 与对应 `*_styles.json` 实例化。有符号误差 `y-ref`，绝对误差 `abs(y-ref)`，相对误差 `(y-ref)/abs(ref)`（比例而非百分比）。默认**严格匹配坐标和顺序**，不是按等长行号相减；只有显式指定 `linear` 才在线性数据坐标中插值参考，参考必须严格递增且唯一，禁止外推。相对误差参考为零仅支持明确报错（`zero_reference='raise'`），不加 epsilon、不掩码、不删零点；可选择绝对误差。下图纵轴始终线性、横轴与主图共享，视觉身份跟随主图，不添加拟合、平滑、误差棒或置信区间。

自动线宽/点径现在按**每个系列最终坐标框中的相邻点间距**独立判断，包含对数变换和图例外置后的坐标框变化。修复旧逻辑把多系列间距的中位数再次混合的问题；不会因为密集 DNS 或重合的另一组缩小稀疏组。空心/实心及透明度约定不变，未抽稀、未跳过标记。散点的密度判断同样局限在自身系列。因修复尺寸/布局，旧输入的 PNG 不保证与旧母板字节一致；旧快照的离线复现不受影响。

限制：仍可能存在真实密点重叠；误差面板会减少主图可用高度，单栏长图例尤需检查实际印刷尺寸；不提供局部放大、自动平滑/拟合、外推或零参考替换策略。Kawamura 的 mean/uu/ww 和 vv/-uv 始终保留各自交错网格。合成 CFD、测量及残差仅用于绘图检验，不能据此宣称求解器或实验精度得到验证。

## 风格和贡献

默认 Arial（缺失时会警告并改用 Liberation Sans），可选 `--font 'Times New Roman'`（缺失时警告并改用 Liberation Serif）。单幅图依参考图采用约 4:3 的画布：`single` 为 89 × 66 mm，`double` 为 183 × 136 mm；点线图等会留出更接近参考图的坐标框四周空间，而不是把坐标框撑满画布。有序时间组采用琥珀黄、黄绿、绿色到深蓝绿的渐变，避免亮黄在白底上不清楚；互不相关的方法则使用另一组克制的分类色。线型和点形辅助黑白辨识。点线图按同一系列相邻点的成图间距调整粗细（不会因其他系列靠近就缩小标记），散点图独立保持可辨认的点大小；密集点使用有限的透明度而不删除数据。如自动尺寸不合适，可分别指定 `--line-width 1.8`（线宽，pt）和 `--marker-size 5`（标记直径，pt；散点面积为直径平方）；Python API 用 `line_width` 和 `marker_size`。四边坐标轴、朝内刻度、主实次虚网格及图例规则见 [风格约定](scientific-plotting/references/style.md)。需要根据新机器安装依赖或替代字体可以直接做；若要改变其他风格，先明确提出要求并检查结果，不要因为缺字体或图例密集就偷偷更改规则。

字号以**实际排版宽度**为准：单栏图（89 mm）坐标名称 10 pt、刻度及图例 8.5 pt；双栏图和多面板档（183 mm）坐标名称 11 pt、刻度及图例 9.5 pt。插入论文时不要把双栏图缩成单栏图，否则文字也会等比变小；应直接选择 `--size single` 重绘。具体期刊的图稿要求如有不同，请按其要求明确调整。

四个参考仓库的星标快照、许可证和借鉴边界见 [参考记录](scientific-plotting/references/sources.md)。这里没有拷贝其代码或图像，尚未发布远程仓库。

测试：安装 `pytest` 后运行 `python -m pytest -q`，并在最终尺寸下查看样图，确认图例、标签及四边刻度未被裁切。若希望 Codex 自动识别此 Skill，可把 `scientific-plotting` 目录链接或复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`；仓库本身不修改用户的全局配置。
