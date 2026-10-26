# Scientific Plotting Skill

面向论文和科研报告的**定量数据绘图 Skill 与 Python 母板**。输入 CSV、Excel 或 Python 表格／数组，输出统一风格、可审查、可复现的图。

本项目不负责物理场、粒子或三维渲染；流场／温度场可先在 ParaView 等工具中处理，再把导出的定量数据交给本 Skill。默认只导出 JPEG，TIFF 需显式指定。

## 从哪里开始

| 你现在要做什么 | 阅读入口 |
| --- | --- |
| 想根据科研问题选择图型 | [科研选图指南](scientific-plotting/references/user-guide.md#selection)：数据层次、13 种图型、误差棒／色带、工程案例 |
| 想完整了解输入要求与能力边界 | [中文使用手册](scientific-plotting/references/user-guide.md) |
| 已经有数据，想直接画第一张图 | 本页“快速开始” |
| 想让 Agent 正确选择流程、按需加载说明 | [Skill 执行入口](scientific-plotting/SKILL.md) |
| 需要具体高级字段、限制和代码 | 本页“专项参考” |

**使用原则：先明确科学问题与数据含义，再选一种基础图型，最后只叠加确有需要且兼容的功能。** 图型、样式、分析变换和交付方式是不同层级，不是需要全部开启的功能清单。

## 能力总览

目前母板有 **13 个 `kind` 值**；多面板、双轴、误差棒等不是额外的 `kind`。

| 任务 | 图型或接口 | 关键边界 |
| --- | --- | --- |
| 趋势、剖面、离散观测 | `point-line`、`line`、`scatter` | 连线保留组内原始行序，不自动排序或拟合 |
| 已有分类数值对比 | `bar` | 不把重复测量自动当成均值 |
| 数值矩阵、样本分布 | `heatmap`、`violin` | 热图不是物理场渲染；小提琴涉及核密度估计 |
| 同图混合理论线、数值曲线与测点 | `mixed` | 每个系列显式声明 `line`／`point-line`／`scatter` |
| 频数、概率、密度、累积比例与分位数 | `histogram`、`ecdf`、`box` | 这些图按各自定义进行统计变换，不是逐点原样展示 |
| 两变量联合分布、顺序轨迹、正负预算项 | `joint`、`trajectory`、`contribution` | 保留配对、顺序和符号；不自动计算物理机制或预算 |
| 多工况／多指标组合 | `render_multipanel` | Python 接口；不同物理量优先分面 |
| 求解器与算法比较 | 对数轴、参考误差子图、参考线、局部放大 | 只绘制已给定的量；不自动估计收敛阶或速度提升 |
| 跨图一致表达 | `style_registry`、`palette`、`encoding` | 依赖明确标签与变量角色，不猜测最优方法 |
| 审查与交付 | `report`、`bundle`、`include_data` | 报告不是合规认证；复现包默认不带输入数据 |

完整数据要求、兼容矩阵与常见混淆见[使用手册](scientific-plotting/references/user-guide.md)。

## 快速开始

### 1. 准备运行环境

建议 Python 3.10+。在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` 是绘图运行依赖，不包括测试工具 `pytest`。字体不随仓库分发，缺失时会警告并采用指定后备字体；中文图请明确使用思源黑体或思源宋体。

### 2. 直接调用 CLI

把路径和列名替换为自己的数据；这里假设 CSV 有 `distance`、`temperature`、`case` 三列：

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/observations.csv --kind point-line \
  --x distance --y temperature --group case --group-kind categorical \
  --xlabel 'Distance (m)' --ylabel 'Temperature (K)' \
  --size double --output /path/to/figures/profile --report
```

无桌面环境时，在命令前加 `MPLBACKEND=Agg`。Excel 可用 `--input results.xlsx --sheet 0` 或工作表名称。全部单图选项用 `--help` 查看；多面板用 Python API，不存在多面板 CLI 模式。

本例保存 `profile.jpg`、CLI 母板副本 `profile_template.py`、重跑脚本 `profile_reproduce.py`，以及显式启用的 `profile_review.json`／`.md`。旧重跑脚本使用原来的绝对路径；跨电脑搬迁应使用 `bundle`，不要误以为它已经包含原数据。

### 3. 在 Python 中复用

以下代码在仓库根目录运行，数据是**合成演示**：

```python
from pathlib import Path
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path("scientific-plotting/scripts").resolve()))
from plot_template import render_plot

observations = {
    "distance": [0.02, 0.00, 0.01],
    "temperature": [410, 390, 400],
}
figure, axes, paths = render_plot(
    observations, kind="point-line", x="distance", y="temperature",
    xlabel="Distance (m)", ylabel="Temperature (K)",
    output="figures/temperature", report=True,
)
plt.close(figure)
```

连线顺序为 `0.02 → 0.00 → 0.01`，不会自动按 x 排序。不传 `output` 时只返回画布，不写文件；Python API 不额外生成旧式 CLI 重跑脚本。所有图片路径返回值都只包含图片，不包含报告或复现包。

### 4. 安装为个人 Skill

把仓库内的 `scientific-plotting/` 目录复制或链接到 `${CODEX_HOME:-$HOME/.codex}/skills/scientific-plotting`。若目标已有版本，先检查并备份，不要盲目覆盖。Skill 安装不代替 Python 依赖和字体准备，也不修改全局配置。

安装后可在后续对话使用：

```text
请用 $scientific-plotting 绘制 /path/to/results.csv。
x 为 time（s），y 为 temperature（K），case 表示不同工况。
使用点线图，保持原始行序，输出双栏 JPEG 和审查报告。
```

可安装的 Skill 本体只有 `scientific-plotting/`；完整手册放在本体的 `references/` 中，随 Skill 一起携带。

## 参考配色与不确定性带示例

`palette="soft"` 提供柔和的冷暖分类色，`palette="coastal"` 提供蓝／青／绿主导的分类色；细线颜色经过加深，浅色用于不确定性填充。两者是可选扩展，不替换 `classic` 默认。

连续曲线可传 `error_bars={"y": "sd", "definition": "sample SD, n=24", "display": "band"}`。这是已给定不确定度的显示方式，不会自动计算或推断置信区间。每组 x 必须严格单调；详细限制见[色带规范](scientific-plotting/references/style.md#optional-uncertainty-bands)。

```bash
MPLBACKEND=Agg .venv/bin/python examples/plot_soft_uncertainty.py --output figures/soft_uncertainty
```

示例以 24 条**合成**重复轨迹计算均值与样本 SD，生成原配色／误差棒与新配色／色带的同数据对比、另一套配色的单图、审查报告及复现包。统计含义保存在独立图注文件中，不能作为实验或 CFD 验证结果。

## 专项参考

| 文档 | 解决的问题 |
| --- | --- |
| [中文使用手册](scientific-plotting/references/user-guide.md) | 选图、数据准备、功能兼容、操作流程、交付、排错 |
| [风格约定](scientific-plotting/references/style.md) | 字体、字号、四边框、网格、密度自适应、CFD 对比、误差棒 |
| [定量分析](scientific-plotting/references/quantitative-analysis.md) | 六种分析图的参数、权重、分箱、归一化与限制 |
| [语义化设计](scientific-plotting/references/semantic-design.md) | 配色、材料／方法 × 指标、实空心、分解图例、受控双轴 |
| [算法比较](scientific-plotting/references/algorithm-comparisons.md) | 系列注册、显式参考阶、局部放大、跨格面板、热图共享色标 |
| [交付与复现](scientific-plotting/references/delivery.md) | 报告、无数据／含数据包、搬迁重跑、完整性校验与隐私边界 |
| [期刊快照](scientific-plotting/references/journals.md) | 当前实现采用的 2026-10-19 检查记录，不是实时投稿规范 |
| [参考记录](scientific-plotting/references/sources.md) | 外部设计参考及借鉴边界 |

## 示例、测试与维护

`examples/` 是用法与验证程序，不是 Skill 运行时必需内容。三个独立合成图集分别演示分析图、语义表达和算法比较；运行命令及相应测试见[手册中的验证入口](scientific-plotting/references/user-guide.md#validation)。其他公开数据／CFD 示例可能需要本地缓存或联网，应先查看脚本，不要把下载当成默认绘图步骤。

```bash
.venv/bin/python -m pip install pytest
MPLBACKEND=Agg .venv/bin/python -m pytest -q
```

部分数据验证测试在缺少本地缓存时会跳过；测试通过不能替代按最终排版尺寸检查图片。开发时只维护 `scientific-plotting/scripts/plot_template.py` 这一份母板，不在示例中另起一套风格。后续增加能力时，同步更新手册的图型表、兼容矩阵和专项参考，而不是继续在 README 顶部追加“新增功能”。

仓库不发布本机生成的 `figures/` 与 `data/`。第三方数据仍须遵守其原始许可与署名要求。绘图代码和 Skill 采用 MIT 许可，见 `LICENSE`。
