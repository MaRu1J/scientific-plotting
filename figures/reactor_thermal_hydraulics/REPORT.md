# 核反应堆热工水力科研绘图 skill 实测报告

## 结果与复现

- 共 14 张独立科研图：4 张 line、6 张 point-line，合计 10/14 = **71.43%**；scatter、bar、heatmap、violin 各 1 张。
- 所有科学数据图使用提供的 `scientific-plotting/scripts/plot_template.py` 的 `render_plot`；未使用其他绘图库替代模板，未修改原 skill。
- PNG only，300 dpi，double 预设 183 × 136 mm。`preview_*.png` 仅为索引缩略图，不计入图数；印刷请使用各图原文件。
- Arial 不可用，按 skill 回退到 Liberation Sans；中文按字形回退到 Noto Sans CJK JP。运行器只适配字体解析返回字体链，不改变模板色彩、线宽、字号、边框、刻度或版式规则。
- `plot_template_snapshot.py` 是此次使用模板的逐字节快照；`reproduce.py`、`raw/`、`data/`、`sources.lock.json`、`manifest.json`、`audit.json` 可离线复现。
- 在本目录运行：`../../.venv/bin/python reproduce.py`；或使用装有 numpy/pandas/matplotlib/Pillow 的 Python。移动整个目录后，运行 `python reproduce.py`。
- 可用 `python reproduce.py --output-dir /tmp/reactor-replay` 向新目录复现；默认只读缓存且校验 SHA-256，不联网。`--download` 只下载缺失的原文件。

## 数据真实性与边界

1. **NPPAD 是公开的 PCTRAN 模拟数据，不是核电厂实测，也不是 HWAT 的模拟解。** LOCA 的 1、10、50 分别表示 100 cm² 基准面积的 1%、10%、50%，即 1、10、50 cm²；SGBTR/10 为一根完整管破口的 10%。正常运行仅作为数值基线，不冒充实验验证。
2. README 表格遗漏 `P`，所以另外下载原始 LOCA/1.mdb，以数据库中明确的 `Press RCS (bar)` 核实一次系统压力单位。P 和 PSGA/PSGB 均由 bar × 0.1 转为 MPa；VOID 保留原始百分数。THA 是热段 A 温度，**不改称堆芯出口温度**；TPCT 是模拟峰值包壳温度。
3. **HWAT 是实验数据**，使用 2023-08-09 Run 09、10、13；XML 文件逐个通过发布者 Zenodo MD5 校验。z 为 m，壁温为 °C，速度按发布说明为 m/s，空泡份额无量纲。Run 09 与 10 边界接近，仅称邻近工况，不宣称严格重复性实验。Run 13 入口温度不同。
4. XML 的 RADIUS 约 0.34–7.77，而说明笼统称 SI，存在单位歧义。本任务不擅自把它标成 m 或 mm，而逐工况使用 `r / max(RADIUS)`；分母为**最外侧实测坐标**，不是管壁半径 R，各工况坐标各自保留，未插值至共同网格。
5. XML 的 POWER、HEATFLUX 数量级与小流量加热回路不相称，且动态压力单位未另行核实，因此**不使用这些字段，不自行乘除 1000 修正**；多工况标签采用可核验的入口温度，不标可疑功率。
6. 图 10 的理论参照由 IAPWS-IF97 饱和线 Eq. (31)、Table 34 计算，使用该工况入口压力。它是恒压近似的饱和温度基准，**不是轴向局部饱和温度实测、不是壁温解析解，也不是 CFD 壁温预测**。因数据源未提供同工况计算壁温，本任务不伪造“计算 vs 实验”的验证对。
7. 图 07、10 保留同一 z 的多支热电偶，严格按 XML 原顺序连线；同 z 的垂直连接仅是测点连接，并非轴向温度梯度。空间点线图不抽样、不去重、不拟合、不平滑。
8. 时序 line 保留全量记录。图 05、06 为避免点密集，保留 23 个等行距基础点、0–300 s 每隔三条记录，以及指定参数的精确极值；只按行号升序取原始行，不改时间和值。每个抽样图的 CSV 包含原始 `source_row`，manifest 记录被保留行。无插值，无推测的事故注入时刻。
9. 图 12 用完整时序 TPCT 的 max，而非对抽样结果取峰值；图 13 为**轴向传感器 × 实验工况**实测壁温矩阵，不假造径向–轴向温度场。同高度多支热电偶按传感器号区分，无重复格聚合。
10. 图 14 的 violin 使用每个工况全部 23 个壁温传感器，表示**空间样本**的 KDE 分布，不是时间波动、重复测量不确定度或置信区间；KDE 只是 skill 自带 violin 展示，不作为物理拟合。
11. NPPAD VOID 有约 10⁻⁶ % 的微负值，视为源文件数值残差，原样保留且在 audit 记录，不夹到零、不静默删除。各时序长度不同，画各自真实时间区间，不外推。

## 来源

- NPPAD：[GitHub](https://github.com/thu-inet/NuclearPowerPlantAccidentData)；Qi et al., Scientific Data (2022), DOI: 10.1038/s41597-022-01879-1；仓库 MIT。具体下载地址、字节数、SHA-256 见 sources.lock.json。
- KTH/HWAT：Le Corre, Li, Grishchenko, Kipiela, Persson, Kudinov & Anglart, *KTH/HWAT loop: 2023 experimental databank for the internal structure of boiling two-phase water flow under LWR core operating conditions*, Zenodo, 2025-01-10, [DOI: 10.5281/zenodo.14627088](https://doi.org/10.5281/zenodo.14627088)，CC BY 4.0。
- IAPWS：[Revised Release on IF97 (2007)](https://iapws.org/public/documents/UWTF-/IF97-Rev.pdf)，Region 4, Eq. (31), Tables 34/36；官方 PDF 缓存在 raw/IF97-Rev.pdf。

## 下载／解析问题与替代

- GitHub 递归树及部分目录 API 出现 TLS EOF；改用相同公开仓库的 raw CSV 下载，成功。正常工况目录实际为 `Normal/1.csv`，不是按类别缩写猜测的 `NORM/0.csv`；404 文件未用于任何图。
- **skill 测试发现**：原模板的 grouped bar 在 `_sync_legend → _copy_identity` 中将 BarContainer 当作 Line2D，调用不存在的 `get_color()` 而失败。本图集仅需单系列汇总柱状图，因此使用原生非分组 `bar`，给已有矩形设置计算结果标签，再调用模板的图例放置函数。未改动 skill；不把 grouped bar 判为通过。violin 同样给模板已有的 body 设置分类标签；heatmap 色标补充中英文单位。
- 原模板自动图例避让依据线与散点，不识别柱体／violin 的填充区域；视觉检查发现默认顶部图例可能遮住顶部数据。因此图 12、14 显式使用模板 `outside` 图例，保持原 183 × 136 mm 画布和字号，增加图例与数据轴不相交断言。
- 可选 MSR DOI 10.5281/zenodo.7821694 的元数据可访问，唯一压缩包为 359,198,346 字节；尝试范围下载获取 ZIP 目录时 TLS 失败，立即放弃该可选数据，采用已成功下载的 HWAT 和 NPPAD，不制造多方法剖面。MSR 元数据仅作失败记录，不参与绘图。
- 无需登录、无付费数据。公开网络只用于获取原始文件和来源说明，生成/复现可完全离线。

## 工况边界

| HWAT Run | p_in / MPa | T_in / °C | G / kg m⁻² s⁻¹ | x_out / − |
|---|---:|---:|---:|---:|
| 09 | 7.26755 | 158.7685 | 697.0522 | 0.18398 |
| 10 | 7.18879 | 159.1031 | 696.7067 | 0.18246 |
| 13 | 7.14167 | 201.7501 | 706.1656 | 0.30944 |

## 图编号 – 图类型 – 数据来源 – 测试重点

| 图编号 | 图类型 | 数据来源／数据类型 | 测试重点 |
|---|---|---|---|
| 01 | line | NPPAD；PCTRAN 多破口模拟时序 | 全量纯连线无点；多工况颜色＋线型；单位转换 |
| 02 | line | NPPAD；PCTRAN 多破口模拟时序 | 纯 line 无标记；多工况原序连线 |
| 03 | line | NPPAD；PCTRAN 多破口模拟时序 | 纯 line 无标记；多工况原序连线 |
| 04 | line | NPPAD；PCTRAN SG A/B 模拟时序 | 纯连线；同工况不同回路；虚实线冗余 |
| 05 | point-line | NPPAD；事故计算＋正常运行数值参考 | 双系列均有点有线；关键极值保留；明确数值参考非实验 |
| 06 | point-line | NPPAD；热段与稳压器饱和温度模拟时序 | 不同点形＋线型；瞬态取样与精确极值；不伪称解析解 |
| 07 | point-line | KTH/HWAT；3 个工况的轴向热电偶实验 | 原生 point-line；不排序；保留同 z 多传感器；多工况对比 |
| 08 | point-line | KTH/HWAT；3 个工况的径向空泡实验 | 径向 point-line；各自原网格；归一化坐标不猜单位 |
| 09 | point-line | KTH/HWAT；3 个工况的径向速度实验 | 不同点形与虚实线；径向原序；全部测量点 |
| 10 | point-line | HWAT + IAPWS；实验壁温＋官方饱和温度理论参照 | 实验与理论参照同为点线；明确恒入口压力近似而非壁温预测 |
| 11 | scatter | KTH/HWAT；同一径向测点的空泡与速度实验配对 | 只显示点不连线；多组重叠点形区分；不拟合 |
| 12 | bar | NPPAD；完整TPCT时序最大值的明确汇总 | 预聚合bar；不从抽样数据求峰值；边框与图例 |
| 13 | heatmap | KTH/HWAT；23传感器×3实验工况的实测矩阵 | 原生heatmap；cividis色标；无空间插值；同z传感器分别保留 |
| 14 | violin | KTH/HWAT；每组23支热电偶的空间样本 | 原生violin KDE；全部实测值；分类图例；非测量置信区间 |

## 自动验证

- 14 张图的 267 项图级断言全部通过：原始／选取行顺序和值、line 无点、point-line 有点有线、scatter 不连线、bar 高度、heatmap 原矩阵和 nearest、四边框、双侧内刻度、主次网格、标题、轴标签、图例或色标、画布范围、183 mm 物理宽度。
- IAPWS 在 0.1、1、10 MPa 的输出通过官方 Table 36 的 1e-6 K 精度校验。
- 每图样式选项在 data/*_options.json，输入在 data/*.csv；PNG 的 SHA-256、尺寸、标记及线宽记录在 manifest.json。所有标题、标签和图例的缺字警告会令生成失败。
- 视觉复核见 VALIDATION.md；线型、点形冗余兼顾灰度识别，未宣称经过正式色觉缺陷测试。
