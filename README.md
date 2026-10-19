# Scientific Plotting Skill

科研数据绘图 Skill + Python 母板：保持统一风格，在不同电脑和项目里复用；默认只导出 PNG。第一版支持 `point-line`（按原始顺序连点）、`line`、`bar`、`scatter`、`heatmap`、`violin`。

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

## 风格和贡献

默认 Arial（缺失时会警告并改用 Liberation Sans），可选 `--font 'Times New Roman'`（缺失时警告并改用 Liberation Serif）。单幅图依参考图采用约 4:3 的画布：`single` 为 89 × 66 mm，`double` 为 183 × 136 mm；点线图等会留出更接近参考图的坐标框四周空间，而不是把坐标框撑满画布。有序时间组采用琥珀黄、黄绿、绿色到深蓝绿的渐变，避免亮黄在白底上不清楚；互不相关的方法则使用另一组克制的分类色。线型和点形辅助黑白辨识。点线图、折线图与散点图会根据成图后的点间距微调线宽与点大小（稀疏稍粗稍大，稠密或重叠变细变小，不删除数据）。四边坐标轴、朝内刻度、主实次虚网格及图例规则见 [风格约定](scientific-plotting/references/style.md)。需要根据新机器安装依赖或替代字体可以直接做；若要改变其他风格，先明确提出要求并检查结果，不要因为缺字体或图例密集就偷偷更改规则。

字号以**实际排版宽度**为准：单栏图（89 mm）坐标名称 10 pt、刻度及图例 8.5 pt；双栏图和多面板档（183 mm）坐标名称 11 pt、刻度及图例 9.5 pt。插入论文时不要把双栏图缩成单栏图，否则文字也会等比变小；应直接选择 `--size single` 重绘。具体期刊的图稿要求如有不同，请按其要求明确调整。

四个参考仓库的星标快照、许可证和借鉴边界见 [参考记录](scientific-plotting/references/sources.md)。这里没有拷贝其代码或图像，尚未发布远程仓库。

测试：安装 `pytest` 后运行 `python -m pytest -q`，并在最终尺寸下查看样图，确认图例、标签及四边刻度未被裁切。若希望 Codex 自动识别此 Skill，可把 `scientific-plotting` 目录链接或复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`；仓库本身不修改用户的全局配置。
