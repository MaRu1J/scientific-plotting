# CFD 科研绘图 skill 原生增强报告

基线：`4cc1c1c`；本轮目录独立于上一轮 `figures/cfd_validation/`。
本轮实际修改中央母板、Skill、风格规范、README，新增回归测试和原生 CFD 图集。
所有验证图默认仅 PNG、300 dpi；未创建分支、提交或推送。

## 五项任务

| 任务 | 实现与验证 |
| --- | --- |
| 原生对数轴 | API `xscale`/`yscale` 与 CLI 同名选项，默认 linear；严格拒绝零/负值；LogLocator 十进制主刻度和真实对数次刻度，绝不使用 AutoMinorLocator；最终布局后每十倍区间不足 60 工作像素时选择 2/5 次刻度，避免单栏十数量级残差网格过密。01、02、03、04、13 验证。 |
| 逐系列类型 | 显式 `kind='mixed'` + `series_styles` / `--series-config` JSON。每组必须给 kind；理论纯线、数值纯线或点线、测点纯散点。允许逐组颜色、线型、点形、线宽和点径。02、05、06、10 验证。原生 line 和 point-line 语义保持。 |
| 小误差比较 | 原生共享横轴误差子图，明确参考与 signed/absolute/relative 定义；默认严格坐标匹配；仅显式 linear 才插值参考，拒绝外推或自动排序；相对零参考仅明确报错。05–08、10 验证。 |
| 逐组密度自适应 | 使用每组原始相邻点在最终坐标框内的显示间距，不再把不同组间距再次合并。包含对数变换、图例外置后的布局。逐组显式尺寸优先于全局尺寸，误差图和图例复制主图最终视觉身份。11/12 中稀疏组 5 pt、密集组 2.4 pt，未删点、未跳标记。 |
| 排版与回归 | 单栏 89×66 mm、双栏 183×136 mm；长图例可外置上方，不缩字号；保留四边框/朝内主次刻度/主实次虚网格。包含稀疏测点+密集 DNS、黑白、字体替代、非单调连接及文本/图例裁切检查。 |

## 数据与科研含义

- 真实数据只读取现有 `data/cfd_validation/raw/` 的 Kawamura 缓存，无下载、无原始字节改写。文件原作者说明和引用要求仍在原始文件中，使用或发表时必须遵循，不能把本图集当作完整的数据引用。
- 使用 `Poi180_4th_E.dat`、`Poi395_4th_D.dat`、`Poi180_2nd_A.dat`；来源 URL、Re_tau/Re_bulk、原文件 SHA256 在 `manifest.json` 的 provenance 中。与上一轮原始哈希一致。
- 04 将 uu/ww 与 vv/-uv 分别从原均值表和剪切表读取，各保留 240 个原始位置，不按 j 共用 y+。对应回归测试逐坐标、逐数值核对原表。
- 02 的两组 Re_tau=180 数据同时具有不同网格和离散格式，不能当作控制变量下的阶数验证。理论粘性底层律只在显式生成的 `0.1<=y+<=5` 范围内绘制。
- 泊肃叶流使用 `u/Ub=2*(1-r²)`；粗/细数值示意分别乘 `1+0.002*r²`、`1+0.0005*r²`。**全部 CFD 数值、测量点、残差和幂律示例均为合成，不是真实求解器或实验输出**。
- 理论/粗数值显式生成 201 点，细数值网格显式生成 41 点，合成测点显式生成 21 点；这是预先声明的不同输入网格，不是从密集数据自动抽稀。固定随机种子 20261019，合成测量噪声标准差 `0.0004*(1-r²)`。
- 05/06/10 明确授权原始数据坐标中的线性参考插值，并逐组记录实际方法（完全匹配仍记录 exact）。所有输入 CSV、具体参数和样式 JSON 均已交付。

## 图像索引

| PNG | 尺寸/类型 | 行数 | 检验重点 |
| --- | --- | ---: | --- |
| 01_residual_single | 单栏 line，log-y | 6003 | 迭代从 0 开始；跨十数量级残差；真实次网格 |
| 02_dns_mixed_double | 双栏 mixed，log-x | 324 | 240 密集 DNS 点线 + 33 稀疏 DNS 散点 + 51 理论线点 |
| 03_dns_single | 单栏 line，log-x | 480 | 两组真实 u+–y+，全部纯线 |
| 04_dns_staggered | 双栏 line，log-x | 960 | 四种应力及两套原始交错坐标 |
| 05_pipe_error_double | 双栏 mixed + signed error | 464 | 主图几乎重合，下图分清约 1e-3 与 2.5e-4 偏差 |
| 06_pipe_error_single | 单栏 mixed + signed error | 464 | 物理宽度/字号与误差可辨性 |
| 07_relative_error | 双栏 point-line + relative error | 102 | 所有组均点+线；生成域 0<=r<=0.95，无零参考 |
| 08_absolute_single | 单栏 line + absolute error | 402 | 包含壁面零值；绝对误差可正常定义 |
| 09_source_order | 单栏 point-line | 6 | x 顺序 .2→.8→.5→1→.1→.6 不变 |
| 10_long_legend_times | 双栏 mixed + error，长图例外置 | 464 | Times 字体替代、显式尺寸、图例在画布内上方 |
| 11_density_single | 单栏 point-line，外置图例 | 1006 | 5 稀疏点与 1001 密集点重合但尺寸独立 |
| 12_density_double | 双栏 point-line，外置图例 | 1006 | 最终坐标框改变不破坏逐组自适应 |
| 13_loglog_pointline | 双栏 point-line，log-log | 81 | 双轴对数变换、次刻度及密度 |

三张 overview 是审阅拼图，不是论文最终版面；`review_grayscale.png` 是四个代表性场景的黑白审阅拼图。
单栏原图 1051×779 px，双栏原图 2161×1606 px；不得把双栏图缩成单栏替代重绘。

## 误差定义与可辨性

- signed：`y-reference`，保留正负；absolute：`abs(y-reference)`；relative：`(y-reference)/abs(reference)`，为比例而非百分比。
- 下图纵轴始终线性，横轴与主图共享。参考不生成虚假的误差曲线；未添加零参考线、平滑、拟合、误差棒或置信区间。
- 相对误差只支持 `zero_reference='raise'`。不能加 epsilon、跳过零值或暗中截断；含壁面零值的完整管流例使用 signed/absolute。07 的非零域是显式生成输入，不是绘图时删除壁面。
- 不同网格默认报错，只有明确授权才线性插值**参考**。不在 log 空间插值，不排序参考或比较系列，不外推。各组输入坐标及误差值写入 `*_metadata.json` 和 `audit.json`。
- 05/06 的主图高度重叠是小偏差问题本身；误差子图可区分粗数值约 1e-3、细数值约 2.5e-4 以及正负合成测量偏差。黑白误差图依赖虚线、菱形和三角形仍可区分。

## 兼容性与限制

- 原 API 三元返回值和 CLI 旧选项保留；新增参数均为可选 keyword。未指定格式仍只有 PNG 图像，`paths` 仍仅包含图像路径。
- 不再需要在示例中自行设置对数 Locator、叠 scatter 或重写风格。旧基线示例/快照保留，不覆盖上轮 16 张图。
- 图例避让考虑变换后的曲线/散点及标记/线宽；最终尺寸复制到图例/误差图，包括自定义 JSON 虚线。误差导出增加明确的 `*_metadata.json` 旁车文件。
- 修复逐系列尺寸/布局后，相同旧输入的 PNG 不保证与旧母板字节一致；这不是数据变化。旧归档快照的离线复现方式不变。
- 当前机器 Arial、Times New Roman 缺失，明确警告后分别使用 Liberation Sans、Liberation Serif，保留既定字号。跨机器字体和 Matplotlib 版本变化可能改变版式或图像字节。
- 所有点和连接均保留，密集 DNS 或完全重合的曲线仍可能遮挡，不能承诺仅靠尺寸自适应消除真实重叠。尤其单栏中大量点线仍较密；选择双栏或显式尺寸，而非偷偷抽稀。
- 本轮没有实现局部放大；只提供实用误差子图。仅支持线性参考插值及零参考拒绝策略，不自动推断误差/不确定性。
- 本轮为屏幕视觉检查与物理尺寸/字号程序校核，未做纸质打样及跨平台后端测试。

## 复现与检查

```bash
.venv/bin/python examples/validate_cfd_optimization.py
.venv/bin/python figures/cfd_optimization/reproduce.py
.venv/bin/python examples/validate_cfd_optimization.py --verify-replay figures/cfd_optimization
.venv/bin/python -m pytest -q
```

`data/` 包含每图 CSV、`*_options.json` 和 mixed 的 `*_styles.json`；`manifest.json` 固定数据/快照哈希与全部调用参数；`audit.json` 含字体、行数、类型、最终尺寸、误差和警告。
`plot_template_snapshot.py` 和 `optimization_runner.py` 与本轮源代码一致；`reproduce.py` 不引用原仓库位置。
严格验证结果、测试日志和已观察限制见 `VALIDATION.md`。
