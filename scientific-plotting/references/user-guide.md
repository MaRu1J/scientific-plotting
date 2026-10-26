# Scientific Plotting 中文使用手册

本手册面向使用者，也用于 Agent 在任务不明确时查阅选图和能力边界。以本仓库当前母板为准；它描述的是**已实现能力**，不是后续开发计划，也不保证任意功能都能组合。

## 目录

- [1. 定位与边界](#scope)
- [2. 根据科研需求选择绘图类型](#selection)
- [3. 准备数据与说明绘图需求](#data)
- [4. 图型、参数与兼容矩阵](#compatibility)
- [5. 三种使用入口](#interfaces)
- [6. 风格、尺寸与导出](#appearance)
- [7. 交付、复现与数据边界](#delivery)
- [8. 常见问题与排错](#troubleshooting)
- [9. 示例与验证](#validation)
- [10. 文档维护规则](#maintenance)

<a id="scope"></a>
## 1. 定位与边界

### 本 Skill 负责什么

把已有的科研定量数据组织成可读、统一、可复现的二维图：趋势与剖面、离散观测、分类比较、数值矩阵、统计分布、参数轨迹、正负贡献，以及多工况和求解器比较。使用同一份 `scripts/plot_template.py`，不为不同案例复制一套新风格。

### 不负责什么

- 物理空间场渲染、粒子渲染、三维几何／体渲染、ParaView 管线或截图拼版。
- 从参考截图恢复真实观测、把合成样例当实验数据，或由分布图推断因果机制。
- 默认计算误差范数、收敛阶、加速比、相关系数、预算闭合、滞回面积或置信区间。
- 自动整理全部项目文件、搜索无关数据、联网补齐测量值或打包完整工作簿。
- PNG、SVG、PDF、EPS 导出。即使某期刊接受这些格式，本母板也不会因此支持它们。

另行明确请求的数据分析可以在绘图前开展，但要把计算方法、假设与绘图步骤区分开；母板不是通用统计分析器。对于未支持的功能，说明限制并提供已有接口内的替代方案，不通过私自改写风格或忽略参数来“兼容”。

### 四个互不替代的层级

| 层级 | 负责的事 | 例子 |
| --- | --- | --- |
| 基础图型 | 这组数据表达什么关系 | `line`、`histogram`、`joint` |
| 组织与表达 | 怎样辨识系列、组织面板或突出局部 | 配色、注册表、分面、局部放大、双轴 |
| 统计／参考定义 | 图上的统计量或比较量具体是什么 | 分箱密度、SD、相对参考误差、显式二阶参考线 |
| 导出与交付 | 保存什么、怎样审查与重跑 | JPEG、TIFF、报告、复现包 |

例如，`histogram` 不是 `bar` 的样式选项，双轴不是新的图型，误差棒不等于参考误差子图，开启复现包也不意味着授权打包原始数据。

<a id="selection"></a>
## 2. 根据科研需求选择绘图类型

### 2.0 从要回答的问题开始

先用一句话说明“读者看完图，要比较或判断什么”，再检查每行数据代表什么。不要从喜欢的配色或手边已有的图型出发。用户已指定且科学上适用的图型应保留；只有会造成误读或当前不支持时，解释原因并提出替代。

按下面的顺序判断即可，不必每次让用户填写问卷：

1. **数据是什么层次？** 是逐次／逐单元原始样本、已汇总的均值及不确定度、已计算的类别值，还是现成矩阵？只有汇总均值不能还原箱线图、小提琴图或原始分布；只有已有 PDF 数值不能再当原始样本分箱。
2. **问题依赖什么关系？** 依赖时间／空间位置的变化选趋势图；依赖个体配对选散点或联合分布；依赖先后路径选轨迹；依赖总体分布选分布图；依赖类别差异选类别比较。
3. **连线是否有科学含义？** x 有物理顺序且相邻观测之间的连接有意义时才连线。少量实测点宜显示标记；已有充分采样的数值／参考曲线可用纯线。无序类别或未配对样本之间不连线；连线不等于拟合或已知连续解。
4. **比较哪些身份、量与工况？** 相同量／单位的方法可同轴；不同量优先分面；条件较多或重叠严重时分面。之后才选不确定度表达、坐标尺度和配色。

数据含义明确时直接选一个主方案，简要说明理由；不要把全部图型交给用户挑。只有会改变结论的缺项才追问，例如样本是否配对、不确定度是什么、体积权重是否适用。未知信息应如实保留，不能借选图补造数据。

### 2.1 按科学问题选基础图型

母板接受下列 **13 个 `kind`**。先选最简单、最能直接回答问题的一种，不为了展示功能而把所有选项叠在同一张图上。

| 想回答的问题 | `kind` | 最小数据映射 | 解释与边界 |
| --- | --- | --- | --- |
| 每个采样点及其连接趋势是什么？ | `point-line` | 数值 `x`、`y`；可选 `group` | 所有点按组内原始行序连接，默认带实心标记 |
| 已有连续参考／数值曲线怎样变化？ | `line` | 数值 `x`、`y`；可选 `group` | 纯线，无可见点标记；仍不自动排序或拟合 |
| 离散观测如何分布，是否需要避免暗示连续性？ | `scatter` | 数值 `x`、`y`；可选 `group` | 纯散点，无连接线 |
| 各类别已有数值相差多少？ | `bar` | 类别 `x`、数值 `y`；可选 `group` | 数值应事先定义；不自动汇总重复测量 |
| 数值矩阵有哪些差异？ | `heatmap` | 二维矩阵；或长表 `x`、`y`、`value` | 完整数值网格，线性 `cividis`，不是空间场渲染 |
| 各组样本的平滑分布形状如何？ | `violin` | 样本 `y`；可选分类 `x` | 涉及核密度估计，不是原始频数，也不是新增独立 KDE 接口 |
| 理论线、CFD 点线、实验散点怎样同图对照？ | `mixed` | 数值 `x`、`y`、系列 `group` | `series_styles` 逐系列声明三种普通系列类型之一 |
| 样本在各区间有多少／多大概率／多大密度？ | `histogram` | 原始样本 `x`；可选 `group` | 必须显式给分箱和统计量；可加权 |
| 小于或等于某阈值的比例是多少？ | `ecdf` | 原始样本 `x`；可选 `group` | 经验累计阶梯；对副本排序并合并同值跳跃，可加权 |
| 各组中位数、四分位数与离群值怎样比较？ | `box` | 原始样本 `x`；可选 `group` | 非加权箱线图；注意样本在 `x` 而非 `y` |
| 两个量在同一批观测中怎样共同出现？ | `joint` | 逐行配对的数值 `x`、`y` | 二维分箱；每面板一个总体，不传 `group` |
| 输入变化时响应按什么先后路径演化？ | `trajectory` | 顺序配对的数值 `x`、`y`；可选 `group` | 保留原始顺序、标起点；可显式校验时间和加方向箭头 |
| 已计算的贡献／预算项正负和大小如何？ | `contribution` | 类别 `x`、带符号数值 `y`；可选 `group` | 必须解释符号；零基线，不自动归一化或求总预算 |

选图时特别注意：

- **已有 PDF 曲线**用 `line`，不要把密度值再当原始样本送进 `histogram`。
- **`bar` 与 `histogram`**：前者比较已有类别值，后者对原始样本按区间统计。
- **`violin`、`box` 与 `ecdf`**：分别侧重平滑形状、分位数汇总、经验累积比例，不能解释为同一种变换。要求不做核密度估计时，不选小提琴图。
- **`point-line` 与 `trajectory`**：都不自动按 x 排序；后者明确表达序列路径，有起点／方向和可选顺序校验，不是“自动滞回分析”。
- **`heatmap` 与 `joint`**：前者展示已有矩阵值，后者由配对样本计算二维分箱统计；它们的色标接口不能互换。

另一个关键区别是**均值差异与总体差异**：只关心已定义的类别指标，可用 `bar`；关心偏态、多峰、尾部或离群值，就需要原始样本的分布图。柱高和对称误差棒不能完整表达分布。箱线图压缩了形状信息；小提琴图的平滑形状又受核密度估计影响。样本很少时不要仅凭平滑外形判断多峰；如需逐点核对，另配原始观测散点面板，并使用真实数值坐标，不擅自增加分类抖动图接口。

### 2.2 再决定组织方式

1. **相同量、相同单位，不同方法／材料**：通常同轴多系列，用颜色、点型和线型辨识。
2. **相同指标，不同工况**：通常把工况放到不同面板，保持系列身份一致。
3. **不同指标／不同单位**：优先共享 x、分行展示；不要塞进一个普通 y 轴。
4. **确需紧凑同步阅读且用户接受双轴**：才使用 `secondary_y`，说明量名、单位、两轴范围和理由。
5. **主图范围大、局部差异难读**：在支持的系列图中显式指定 `inset`，不要裁掉主图数据。
6. **多张图要保持方法身份一致**：用同一份 `style_registry`；不要依赖每张图的自动分色恰好相同。

不同物理量共享坐标轴需要科学上的可比性，不因 API 允许就默认合理。`sharex`／`sharey` 是链接坐标轴，不会进行单位换算。

### 2.3 最后选择必要的增强功能

| 需要 | 使用 | 不要混淆为 |
| --- | --- | --- |
| 测量不确定度 | `error_bars`（误差棒或连续曲线浅色色带） | 相对理论曲线的偏差 |
| 与指定参考逐点比较 | `error` 参考误差子图 | SD、SEM 或置信区间 |
| 给定容差或理论阶数的视觉对照 | `reference_guides` | 自动拟合阶数或统计显著性 |
| 材料／方法 × 指标的身份编码 | `encoding` | 从列名、标签或截图自动猜角色 |
| 强调一个已指定对象 | `palette="focus"` + `focus` | 自动发现并突出“最佳方法” |
| 同量数值热图用一个色标比较 | `shared_colorbar` | `joint` 的共享色条 |
| 输出后检查和搬迁重跑 | `report`、`bundle` | 原始数据自动授权或期刊认证 |

### 2.4 不确定度：先定含义，再选误差棒或色带

**误差棒与不确定性带是并列的显示方式，没有上下级关系。** 同一组区间可以用不同方式显示；统计含义由区间来源决定，不由画法决定。两种方式都可能表示 SD、SEM、置信区间或其他有明确定义的范围。

| 科研需求／数据结构 | 优先考虑 | 需要检查的条件 |
| --- | --- | --- |
| 少量离散测点、若干独立工况或类别汇总 | 误差棒，通常配散点／点线／柱图 | 每一点的范围容易对应；只有连接有意义时才用点线 |
| 连续时间响应、剖面或已给定预测曲线及逐点区间 | 不确定性带，配 `line`／`point-line` | 区间随 x 有定义；本接口每组 x 必须严格单调且至少两点 |
| x 与 y 都存在已量化的不确定度 | 横向与纵向误差棒 | 当前色带仅支持纵向；不把 x 误差塞进 y 色带 |
| 多组区间大幅重叠 | 分面，各面板保留同一种统计定义 | 不靠增加不透明度或隐藏某些系列解决 |
| 原始重复样本的形状本身是研究重点 | 分布图，必要时配原始散点 | 不能只画均值及区间来代替样本分布 |
| 单次确定性模拟／公式曲线，没有区间依据 | 直接画曲线，不加统计区间 | 容差、残差或与参考的偏差单独表达 |

图注应写清中心值、范围定义、相关样本数及计算方法。例如“24 次独立重复实验的均值 ± 样本 SD”描述样本离散程度；“均值的 95% 置信区间”描述均值估计的不确定性，需说明估计方法。网格点或相关时间点的数量不自动等于独立重复次数。

SD 不是 SEM，置信区间不是预测区间；逐点 95% 置信区间连接成色带后，也不会自动成为覆盖整条曲线的同时置信带。均值上下的区间是否重叠，不是通用显著性检验。母板仅绘制已给定范围，不执行这些统计推断。

色带使用曲线同色的浅填充，中心线保持清晰；配色不会改变统计定义。当前 API、幅度／绝对边界转换及不兼容组合见[不确定性带规范](style.md#optional-uncertainty-bands)。

### 2.5 工程科研需求示例

以下是选图示例，不是预设分析结论；没有输入数据时不生成真实科研结果。

| 具体需求 | 主方案及理由 | 必要补充／易误用处 |
| --- | --- | --- |
| 比较理论速度剖面、数值解与实验测点 | `mixed`：理论／充分采样数值解用线，实验用散点 | 数值采样位置本身重要时用点线；各自保留原生网格，实验不确定度用误差棒 |
| 比较不同工况的重复实验瞬态响应 | 均值曲线＋已定义的 SD／CI 色带 | 工况多则分面；明确样本是否为独立重复，不把时间波动自动当均值置信区间 |
| 判断温度超过安全阈值的样本占比 | `ecdf`，以 `1-F(T)` 读严格大于 T 的经验占比 | 明确是观测占比还是体积／时间加权占比；大于等于阈值与严格大于在阈值有样本时不同 |
| 比较网格单元温度的偏态和高温尾部 | 共用箱边界的 `histogram`；主要关心阈值比例时选 `ecdf` | 非均匀网格若研究体积分布，需要已确认的体积权重；不能拿单元数替代体积 |
| 比较几种方案的典型值和离散范围 | 有原始样本时选 `box`；重点研究平滑形状且样本支持时选 `violin` | 只有预计算均值时改用 `bar`／普通系列及给定区间；不能反造样本 |
| 研究速度与温度如何共同变化 | 样本可辨时 `scatter`；密集样本关心二维分布时 `joint` | 必须逐行配对；相关、因果、热通量均需另行定义与计算 |
| 展示加载—卸载路径 | `trajectory`，保留先后顺序与起点 | 不按 x 排序；有回路形状不自动证明滞回机制，不自动计算面积 |
| 比较网格精度、迭代残差和计算成本 | 分面普通系列：误差—网格、残差—迭代、误差—成本 | 正值跨数量级时考虑对数轴；残差下降不等于解误差下降，成本比较需注明硬件与计时范围 |
| 展示能量方程各项的正负与大小 | `contribution`，统一单位、保留零基线 | 只画已提供项；未提供项不补零，不由图宣称预算闭合 |
| 比较多个方案在多个指标上的表现 | 各指标分面；已有完整同量矩阵可用 `heatmap` | 不同单位不混用同一色标，不默认归一化或改画雷达图 |

坐标也是科学表达的一部分：有意义零点的类别柱图应保留零基线，避免夸大差异；局部曲线比较可使用明确的非零显示范围。对数轴适合比例或数量级比较，但要求正值及合法区间端点；当前分析图仍只支持线性轴。需要截断、缩放或转换时说明含义，不改变观测本身。

### 2.6 选图后的简短说明

在图注说明、交付说明或选图讨论中，用一两句话说明关键决定即可，不把这些解释自动画进图内。例如：

> 目标是比较三种方案的瞬态响应，采用均值曲线和样本 SD 色带；颜色及线型区分方案，工况分面。色带来自已提供的独立重复样本汇总，不表示均值的 95% 置信区间。

说明应覆盖**研究问题、选定图型及理由、实际统计变换／不确定度定义、影响解读的限制**，只写当前任务相关的内容。数据不足时指出缺什么；多种图均适用时先给主方案，仅在互补视角能帮助回答问题时再给备选，不为同一任务批量堆图。

<a id="data"></a>
## 3. 准备数据与说明绘图需求

### 3.1 输入约定

- **CLI**：CSV、`.xlsx`、`.xls`。Excel 用 `--sheet` 选一张工作表，默认第 0 张。
- **Python**：pandas DataFrame、等长列数组字典；二维 NumPy 数组可直接作为热图矩阵。
- **普通系列**：每行一条观测；`x`、`y` 是坐标列，`group` 是系列身份列。
- **分布图**：`histogram`／`ecdf`／`box` 的原始样本映射到 `x`，不传 `y`；`box` 用 `ylabel` 标样本变量名称与单位。
- **配对／路径**：`joint`／`trajectory` 的 x、y 必须来自同一观测；不要各自排序后再拼起来。
- **矩阵热图**：长表需要 `--x`、`--y`、`--value`；矩阵文件可用 `--index-col` 指定行标签列。格点必须形成完整有限数值矩阵，不自动插值补空格。

示例长表，仅用于说明列结构：

```csv
time,temperature,case,sd
0,300,A,0.5
1,303,A,0.7
0,302,B,0.6
1,306,B,0.8
```

这里 `case` 是工况，`sd` 只有在已确认表示温度样本标准差时才能作为温度的不确定度。保留来源、试验条件与样本数，不从四行演示数据推导真实结论。

### 3.2 行序、分组与缺失值

普通连线和轨迹保留**每个组内的原始行序**。数据若需要按时间重排，应在绘图前明确执行并披露，不把“看起来更顺”当成排序授权。不要静默平滑、拟合、抽稀、删点、重采样或填补缺失值。

`group_kind="auto"` 会把数值／日期时间分组识别为有序系列；不同方法即使编号是数字，也应显式用 `group_kind="categorical"`。文本时间标签如 `t=0.2s` 若代表有序工况，可显式用 `ordered`；不要期望脚本从标签文本推断完整物理含义。

对缺失／非有限值或不适用的输入，先说明并按报错定位，不以删除观测来通过检查。分布图的零权重观测允许保留；负权重、总体总权重不为正或非有限权重不允许。对数轴要求坐标及误差棒下端严格为正。

### 3.3 不确定度与重复测量

Agent 使用 Skill 时，应检查是否存在属于该观测的 SD、SEM、CI 等列；含义明确就可以采用，无须用户额外说“加误差棒”。名称只是线索：求解误差、残差、容差不是不确定度，SD 也不能当成 SEM。

如果同一位置有真实重复测量，且任务应展示汇总值，可以明确报告算术均值、样本 SD（`ddof=1`）、n 与单位；如果用户要看原始散点或分布，就保留原始样本。单条 DNS、模拟或公式曲线不能凭空生成不确定度。

直接调用 API／CLI 时，脚本只画给定幅度，不计算统计量，必须提供 `definition`。不对称误差传的是**非负幅度**，不是绝对上下界：若值为 y、上下界为 L／U，则应先明确转换为 `y-L`／`U-y`。不要混用同一方向的对称和非对称参数。

### 3.4 推荐的需求描述

不必每次填写所有高级参数，但至少让数据身份、量与单位明确：

```text
使用 $scientific-plotting 绘制：
数据：/path/to/results.xlsx，工作表 profiles。
问题：比较不同求解器的速度剖面，不进行拟合或插值。
映射：x = radius（m），y = velocity（m/s），group = solver（分类方法）。
图型：point-line，保留原始行序。
不确定度：sd 列为样本标准差，n = 5；无该列的参考曲线不加误差棒。
版式：double，Arial，轴标签英文，默认不加图内标题或来源脚注。
交付：JPEG + 审查报告；需要复现包，但不允许包含输入数据。
```

分布任务还应说明每行代表时间、网格单元、粒子还是独立试验，以及区域、时间窗、权重和总体范围。样本数不自动等于独立样本数，非均匀网格的计数占比也不自动等于体积占比。

<a id="compatibility"></a>
## 4. 图型、参数与兼容矩阵

### 4.1 基础能力兼容表

“支持”只指当前接口允许，仍需满足各功能自身约束；“不支持”不可通过忽略参数来绕过。所有原生图型都可作为 `render_multipanel` 的面板，但不代表任意面板都适合共享坐标轴或图例。

| 图型 | 对数轴 | 误差棒 | 参考误差子图 | 系列注册／语义编码 | 参考线／局部放大 | 独立双 y 轴 |
| --- | --- | --- | --- | --- | --- | --- |
| `line`／`point-line`／`scatter` | 支持 | x／y | 支持 | 支持 | 支持 | 有条件支持 |
| `mixed` | 支持 | x／y | 支持 | 支持 | 支持 | 不支持 |
| `bar` | 不支持 | 仅 y | 不支持 | 不支持 | 不支持 | 不支持 |
| `heatmap` | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 |
| `violin` | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 |
| 六种 `analysis` 图型 | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 |

这里“六种 `analysis` 图型”指 `histogram`、`ecdf`、`box`、`joint`、`trajectory`、`contribution`。它们只通过 `analysis` 使用各自参数；不接受普通系列的 `series_styles`、`style_registry`、`encoding`、`secondary_y`、`reference_guides`、`inset`、`heatmap_scale`、`error`、`error_bars`。反过来，普通图型不接受 `analysis`。

浅色色带是 `error_bars` 的显示模式，仅支持 `line`／`point-line` 的纵向不确定度，每组 x 必须严格单调且至少两点；不支持局部放大。默认透明度 0.18，保留样本行序、不自动推断置信区间；统计含义必须注明。详见[色带规范](style.md#optional-uncertainty-bands)。

`palette` 可用于普通分类系列及多数分析图；有序分组保持原有渐变。`heatmap` 和 `joint` 只能保留定量 `cividis`，不使用分类调色板。空心／实心 `fillstyle` 是点线／散点系列样式，不是箱线图或分布图的全局填充选项。

### 4.2 六种分析图的参数

传入形式为 `analysis={...}`；CLI 的 JSON 文件直接保存花括号内的映射，**不要再包一层 `analysis` 键**。

| 图型 | 必需参数 | 可选参数 | 不能省略的解释 |
| --- | --- | --- | --- |
| `histogram` | `bins`、`statistic` | `weight`、`weight_definition` | 分箱与 count／probability／density 的含义 |
| `ecdf` | 无；可省略 `analysis` | `weight`、`weight_definition` | 经验累计比例，不是假设分布的拟合 |
| `box` | 无；可省略 `analysis` | `whis`，默认 1.5 | 非加权；须线延伸到 IQR 规则范围内的实际观测，保留全部离群点 |
| `joint` | `bins=[x_bins, y_bins]`、`statistic` | `weight`、`weight_definition`、`vmax` | 配对总体、两轴单位及二维分箱统计 |
| `trajectory` | 无；可省略 `analysis` | `order`、`arrows` | 原始组内序列；`order` 仅验证严格递增，不排序 |
| `contribution` | `definition` | 无 | 各项含义及正负号约定 |

- `bins` 可为 1–1000 的整数或有限严格递增的边界序列。直方图多组共用箱边界；跨面板比较时显式传相同边界。`joint` 总格数不超过 250000。
- `count` 是观测数或权重和；`probability` 为各箱质量除以该组总质量，和为 1；`density` 再除以箱宽／二维箱面积，积分为 1。各总体分别归一化，不是混合总体占比。
- 显式边界必须覆盖全部样本；不自动丢弃范围外观测。加权必须提供 `weight_definition`，不能只因为有体积列就默认加权。`box` 不实现加权分位数。
- `joint` 不接收 `group`：先拆分数据，再画多个面板。对比时用相同边界、统计量、权重含义与 `vmax`；`vmax` 不能截断箱值峰值。每面板独立色条，不能使用热图的 `shared_colorbar`。
- `trajectory.arrows` 是各组都有效的零起始线段索引，不是时间值；不允许零长度方向箭头。它不闭合轨迹、不计算围成面积。
- `contribution` 同一组内重复项会报错；缺失组合不补成 0，不堆叠或转百分比。

完整示例与统计定义见[定量分析](quantitative-analysis.md)。目前无独立 KDE／拟合 PDF、联合条件均值、自动象限贡献或统计置信区间接口；普通 `violin` 内部的核密度估计不意味着具备这些能力。

### 4.3 普通系列的高级功能

| 参数 | 使用条件与重要约束 | 详细说明 |
| --- | --- | --- |
| `series_styles` | 用精确字符串标签配置；`mixed` 中每个实际系列必须有 `kind` | [风格约定](style.md#native-cfd-comparisons) |
| `style_registry` | 跨图固定身份；可含未出场系列；未登记系列会警告并退回局部分配 | [算法比较](algorithm-comparisons.md) |
| `encoding` | 明确 `categories`、`metrics`、`series`；声明量与单位，不能同轴混用不兼容量 | [语义化设计](semantic-design.md) |
| `secondary_y` | 仅三种普通系列；明确主／次轴量名、单位、全数据及误差棒范围、归属与理由 | [语义化设计](semantic-design.md) |
| `reference_guides` | 常值线或显式幂律；幂律要求双对数轴及已给定阶数、锚点、范围 | [算法比较](algorithm-comparisons.md) |
| `inset` | 显式 `xlim`、`ylim`、`bounds`；复制主图全部观测与已解析样式，不独立抽稀或缩点 | [算法比较](algorithm-comparisons.md) |
| `error` | 给参考标签与 signed／absolute／relative 定义；默认精确坐标及顺序匹配 | [风格约定](style.md#native-cfd-comparisons) |
| `error_bars` | 给非负幅度及统计 `definition`；对数轴误差棒不能到达 0 或负值 | [风格约定](style.md#optional-error-bars) |

不要把下列组合视为已经实现：

- **双轴 + `mixed`／`inset`／`reference_guides`／参考误差子图**：不支持。双轴可以有各自的不确定度棒，但多面板中不能再用全局 `sharey=True`。
- **双轴模拟单位换算轴**：独立双指标接口不是单位换算接口；同一量的换算轴尚未实现。
- **热图 `shared_colorbar` + `joint`**：不支持。该接口只用于至少两个同 `quantity`／`unit` 的数值 `heatmap`，必须给 `vmin`、`vmax`、`label`。
- **分析图 + 普通系列注册表**：不支持。多面板的全局注册表只传给普通系列面板；分析图跨图身份需保持相同分组顺序。

参考误差定义分别是 `y-ref`、`abs(y-ref)`、`(y-ref)/abs(ref)`。默认不按行号硬减、不插值；显式选择线性插值时也不外推，参考值为零时相对误差报错。误差子图保持线性 y 轴，不继承或传播主图误差棒。

样式冲突时，显式 `series_styles` 的单项属性优先于注册表；无语义编码时再回到自动分配。有 `encoding` 时不要一边定义语义身份、一边用另一套配置覆盖它而不核对角色一致性，具体解析规则见语义化设计参考。

<a id="interfaces"></a>
## 5. 三种使用入口

### 5.1 对话调用：由 Agent 选择流程

使用 `$scientific-plotting` 并说明第 3 节的信息即可。Agent 应先确认输入和数据语义，选图，再按需读取专项参考；简单点线图不需要把所有高级模式加载一遍。

只有歧义会改变科学含义时才追问，例如不清楚误差列是 SD 还是 SEM、权重是否代表体积，或两个不同物理量是否被要求共轴。普通字号、默认 JPEG 等已有约定不必反复询问。

### 5.2 CLI：单图与单图增强

以下命令在仓库根目录运行。把示例路径／列名替换为真实输入；它们不会自动下载数据。

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py --help
```

| 目的 | CLI 参数 | Python 参数 |
| --- | --- | --- |
| 数据映射 | `--kind --x --y --group --value --group-kind` | `kind, x, y, group, value, group_kind` |
| 坐标／外观 | `--xscale --yscale --font --size --height-mm --legend` | 对应下划线参数 |
| 母板线宽／标记直径 | `--line-width --marker-size` | `line_width, marker_size`，单位 pt |
| 每系列配置 | `--series-config styles.json` | `series_styles={...}` |
| 跨图身份 | `--style-registry registry.json` | `style_registry={...}` |
| 配色／重点 | `--palette --focus` | `palette, focus` |
| 语义角色／双轴 | `--encoding-config roles.json`／`--secondary-y-config axes.json` | `encoding, secondary_y` |
| 参考线／放大 | `--reference-config guides.json`／`--inset-config zoom.json` | `reference_guides, inset` |
| 六种分析图配置 | `--analysis-config analysis.json` | `analysis={...}` |
| 参考误差 | `--error-reference --error-definition --error-interpolation --error-ylabel` | `error={...}` |
| 对称误差棒 | `--yerr sd --errorbar-definition 'sample SD, n=5'`；横向用 `--xerr` | `error_bars={"y": "sd", "definition": "sample SD, n=5"}` |
| 连续曲线不确定性带 | `--yerr sd --errorbar-definition 'sample SD, n=24' --uncertainty-display band` | `error_bars={"y": "sd", "definition": "sample SD, n=24", "display": "band"}` |
| 非对称误差棒 | `--yerr-lower --yerr-upper`；横向用 `--xerr-lower --xerr-upper` | `y_lower, y_upper, x_lower, x_upper` 位于 `error_bars` |
| 导出与交付 | `--output --format --dpi --journal --report --bundle --include-data` | `output, formats, dpi, journal, report, bundle, include_data` |

`heatmap_scale`、多面板 `layout`／`shared_colorbar` 等没有对应 CLI 选项，应使用 Python。JSON 配置文件各自保存该参数的对象；参考线文件是列表，不是对象。

**残差对数轴示例：**

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/residuals.csv --kind line \
  --x iteration --y residual --group solver --group-kind categorical \
  --yscale log --xlabel 'Iteration (-)' --ylabel 'Normalized residual (-)' \
  --output /path/to/figures/residual --report
```

**分布示例：**先创建 `analysis.json`（这里的边界只是示例，须覆盖实际全部温度）：

```json
{"bins": [290, 300, 310, 330, 360], "statistic": "density"}
```

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/samples.csv --kind histogram --x temperature --group case \
  --group-kind categorical --analysis-config /path/to/analysis.json \
  --xlabel 'Temperature (K)' --ylabel 'Probability density (1/K)' \
  --output /path/to/figures/temperature_distribution --report
```

**混合系列示例：**`styles.json` 的键必须与实际系列标签完全对应：

```json
{
  "Theory": {"kind": "line", "linestyle": "-", "color": "#126b80", "line_width": 1.5},
  "CFD": {"kind": "point-line", "linestyle": "--", "marker": "s", "marker_size": 4},
  "Samples": {"kind": "scatter", "marker": "^", "marker_size": 5.5}
}
```

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/profiles.csv --kind mixed --x radius --y velocity --group series \
  --group-kind categorical --series-config /path/to/styles.json --size double \
  --xlabel 'Radius, r/R' --ylabel 'Velocity, u/Ub' \
  --output /path/to/figures/comparison --report
```

需要参考误差时，再显式添加 `--error-reference Theory --error-definition signed --error-ylabel 'Signed error in u/Ub'`。只有需要且接受插值时才添加 `--error-interpolation linear`；默认保持精确匹配。

### 5.3 Python：单图、组合图与自定义检查

导入路径指向 Skill 的 `scripts/`；仓库 README 有最小单图示例。`render_plot` 返回 `(figure, axes, image_paths)`；`render_multipanel` 返回 `(figure, axes_list, image_paths)`。不传 `output` 时不写文件，`report` 或 `bundle` 则要求明确的 `output`。

下面是可在仓库根目录运行的**合成双面板**示例。两个指标单位不同，故共享时间轴但不共享 y 轴；两图使用相同方法身份：

```python
from pathlib import Path
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path("scientific-plotting/scripts").resolve()))
from plot_template import render_multipanel

history = {
    "time": [0, 1, 2, 0, 1, 2],
    "method": ["Baseline"] * 3 + ["Candidate"] * 3,
    "temperature": [300, 303, 305, 300, 302, 304],
    "pressure": [100, 110, 115, 100, 108, 112],
}
registry = {
    "Baseline": {"color": "#2F6DB5", "marker": "o", "linestyle": "-"},
    "Candidate": {"color": "#D35400", "marker": "s", "linestyle": "--"},
}
panels = [
    {"data": history, "kind": "point-line", "x": "time", "y": "temperature",
     "group": "method", "group_kind": "categorical",
     "xlabel": "Time (s)", "ylabel": "Temperature (K)"},
    {"data": history, "kind": "point-line", "x": "time", "y": "pressure",
     "group": "method", "group_kind": "categorical",
     "xlabel": "Time (s)", "ylabel": "Pressure (kPa)"},
]
figure, axes, paths = render_multipanel(
    panels, ncols=1, sharex=True, sharey=False,
    style_registry=registry, size="double", height_mm=160,
    output="figures/synthetic_responses", report=True,
)
plt.close(figure)
```

多面板默认共享图例并自动标 `(a)`、`(b)` 等；`legend` 可选 `shared`／`each`／`none`，与单图 `auto`／`outside` 不同。跨格布局用面板 `id` 与 `layout` 矩阵，不能同时指定 `ncols`；重复格必须构成矩形。返回轴与面板字母按输入面板顺序，不按布局矩阵遍历顺序。

手动修改 artist 后，必须对最终画布重新运行 `review_figure`，再导出并目视检查。不要在母板返回后私自添加来源脚注、缩小图例文字或隐藏数据来规避规则。批量绘图结束后关闭 figure。

<a id="appearance"></a>
## 6. 风格、尺寸与导出

### 6.1 保持哪些默认约定

- 白底、完整四边框、四边向内主／次刻度。数值轴通常主实线／次虚线网格；柱／分布类和热图有各自例外，见[风格约定](style.md)。
- 默认 Arial；可选 Times New Roman、思源黑体、思源宋体及文档列出的别名。缺字体会警告并使用后备，不因安装了中文字体就给英文图换字体。
- 有序组使用琥珀至深蓝绿渐变；无序方法使用分类色。`classic` 保持旧默认，`jewel`／`muted`／`soft`／`coastal` 为显式分类配色；`focus` 必须指定重点身份。
- 默认点线图使用实心圆、方、三角、菱形等；密度自适应只改可读的大小，不删除观测。显式语义空心点仅用于支持的系列。
- 图例优先找图内不遮挡处；`outside` 贴在坐标框上沿（放不下则下沿），宽度不超过该边坐标轴，只留约 4 pt 间隙，不放到左右两侧，也不拉成整张图那么宽。不能为了放下图例缩小字号；必要时选择更宽预设或分面。
- 默认不画图内标题、面板／放大小标题和来源脚注；轴名、图例、面板字母和必要数据注记保留。来源、条件与解释放到稿件图注、独立图注文件或元数据。
- 角标可写 `t^*`、`t^+`、`x^2`、`10^-3`、`t_{wall}` 或数学定界表达式；中文标签要使用合适中文字体。

### 6.2 尺寸是实际排版尺寸

| `size` | 默认宽 × 高（mm） | 典型用途 |
| --- | --- | --- |
| `single` | 90 × 67.5 | 默认 Elsevier 单栏；JFM 的暂定宽度 |
| `medium` | 140 × 105 | 中等宽度 |
| `double` | 190 × 142.5 | 默认 Elsevier 双栏／多面板宽度 |
| `aip-single` | 85 × 63.75 | PoF 默认单图 |
| `aip-double` | 170 × 127.5 | PoF 默认多面板 |

单幅默认 4:3；支持 `height_mm=40–210`，不支持任意宽度，也没有 `size="multipanel"`。多面板通过真实 axes 组合，可根据行数增高，最高 210 mm。

85／90 mm 图默认轴名 10 pt、刻度与图例 8.5 pt；140／170／190 mm 图为 11 pt 和 9.5 pt。应在最终物理宽度下检查，不用放大屏幕预览代替论文排版判断。

### 6.3 格式、分辨率与期刊快照

- 未指定 `formats`／`--format`：只写 JPEG，300 dpi、质量 95、无色度抽样，扩展名 `.jpg`。
- 显式 `formats=("tiff",)` 或 `--format tiff` 才写 TIFF；需要两种格式时可同时指定。输出 basename 的后缀不能代替格式参数，命名为 `plot.png` 也不会启用 PNG。
- 显式 dpi 始终保留；低于所选快照要求时报告差异，不暗中提高或降低。
- 默认 `journal="elsevier"`；PoF 用 `pof`，JFM 用 `jfm`。期刊选择不会自动把 JPEG 改成 TIFF，也不会把明确指定的宽度替换掉。

省略 dpi 时，TIFF 使用的**实现快照值**：

| 期刊模式 | 线类 TIFF | 含 `heatmap`／`joint` 的 TIFF |
| --- | --- | --- |
| `elsevier` | 1000 dpi | 500 dpi |
| `jfm` | 1200 dpi | 600 dpi |
| `pof` | 600 dpi | 600 dpi |

以上源自实现采用的 **2026-10-19 快照**，不是已实时核验的投稿规则。JFM 的 90 mm 是暂定值，不能称为期刊官方毫米规范。投稿前按[期刊快照](journals.md)核对差异并检查目标期刊当时的要求；审查无提醒也不等于合规。

<a id="delivery"></a>
## 7. 交付、复现与数据边界

### 7.1 先选交付层级

| 方式 | 保存内容 | 何时用 |
| --- | --- | --- |
| 普通图片导出 | JPEG／显式 TIFF；特定模式还会写数值元数据 | 只需要图；仍应检查附带文件再分享 |
| CLI 旧式重跑 | 图片旁的母板副本、重跑脚本及用到的 JSON 配置副本 | 同机、原路径仍有效时重跑 |
| `report=True`／`--report` | 再保存 `_review.json` 与 `_review.md` | 检查实际图像导出、字体与已实现的可读性风险 |
| `bundle=DIR`／`--bundle DIR` | 固定母板、recipe、manifest、图片、报告、版本与校验记录 | 迁移或交付重跑；默认不含输入数据 |
| 再加 `include_data=True`／`--include-data` | 额外保存实际用到的列／工作表内容和必要误差数组 | 已明确授权携带数据时 |

`report`、`bundle` 要求 `output`；`bundle` 隐含开启报告。包目录须不存在或为空，原始导出须在包目录之外。`include_data` 不可脱离 `bundle` 使用。单图／多面板返回路径仍然只有图片；可通过 `figure.scientific_report_paths` 和 `figure.scientific_bundle_path` 获取交付位置。

### 7.2 默认无数据包不是自包含包

```bash
.venv/bin/python scientific-plotting/scripts/plot_template.py \
  --input /path/to/results.csv --kind line --x time --y residual \
  --output /path/to/figures/residual --bundle /path/to/delivery
```

搬迁后，需要按 `manifest.json` 的输入清单补齐数据：

```bash
python /new/location/delivery/reproduce.py --input main=/safe/used_columns.csv
```

单图通常是 `main`，多面板为 `panel_0`、`panel_1` 等；单独传入的误差数组会有额外 ID。外部替代输入支持符合约定的 CSV 或母板的带类型快照 JSON，不直接重开原 Excel 工作簿。精确 ID、列名和类型以 manifest 为准。

只有明确允许数据快照时才加 `--include-data`。含数据包可直接运行 `python /new/location/delivery/reproduce.py`；默认输出到包内 `replayed/`，再次重跑需另选新的空输出目录。包不复制整个工作簿、字体或虚拟环境，不联网、不自动安装依赖。

### 7.3 分享前需要检查什么

- **默认不带数据只约束便携包的输入快照**，不意味着导出的图不呈现数据，也不意味着所有旁文件都无数据。原始导出旁的 `_metadata.json` 可能含数值／误差数组；旧脚本和配置副本可能含原绝对路径。
- 报告会记录标签、定义、字体／环境以及分箱、样本数等摘要；即使没有逐条观测，也可能含敏感项目语义。对外分享仍要检查。
- 报告实际解码图片检查格式、像素、DPI、物理尺寸并记录部分版式／灰度风险；它不证明统计正确、色觉可达性或期刊接受。
- 普通提醒不阻断交付；导出文件损坏、格式或尺寸不符等错误会先保存报告再报错。不能通过删除提醒声称图已通过审查。
- SHA-256 用于检查受管理文件是否意外改变，不证明数据真实性或来源可信。重跑脚本是可执行代码，应来自可信来源。
- 版本记录不等于自动还原环境，含数据包也不包含 Python 运行时与字体；跨系统应比较数值、配置和导出属性，不要求图片字节一致。

完整结构、数据快照类型和报告范围见[交付与复现](delivery.md)。

<a id="troubleshooting"></a>
## 8. 常见问题与排错

| 现象／疑问 | 先检查什么 | 正确处理 |
| --- | --- | --- |
| 曲线来回折返 | 输入的组内行序；是否实际想画轨迹 | 保持现状或明确授权预排序，不默认按 x 重排 |
| 数字方法名被画成渐变 | `group_kind` 是否为 auto | 方法编号用 `categorical`，时间／参数序列才用 ordered |
| `box` 找不到样本或拒绝 y | 是否按普通图习惯把样本传给了 y | 样本放在 x，组名放 group，样本轴文字用 ylabel |
| 直方图／联合图要求配置 | 是否明确 bins 和 statistic | 给分箱、统计量、总体与单位；不要靠默认猜 |
| 箱高之和不为 1 | 是否用了 density 或非等宽箱 | 密度的面积／二维积分为 1，不是高度之和 |
| `joint` 不接受分组或共享色条 | 是否把它当成 heatmap | 每总体独立面板、相同显式边界及 vmax，各自色条 |
| SD 被当作置信区间，或上下界报负数 | 统计定义、幅度与绝对边界是否混淆 | 确认 SD／SEM／CI；先按明确定义转换非负幅度 |
| 对数坐标报错 | 坐标或误差棒下端是否到达 0／负值 | 报告无效值；改变图设计或修正已确认的数据问题，不删点／截断 |
| 参考误差计算失败 | 参考身份、网格坐标及顺序是否一致 | 保持原生网格；需要时显式授权线性插值，不外推 |
| 不同图的同名方法换了颜色 | 是否依赖每图自动分配、注册表是否漏项 | 共享完整注册表；分析图保持分组顺序或分面 |
| 双轴与放大／参考线组合失败 | 是否触发当前不支持的组合 | 改为普通分面，不绕过校验 |
| 图例／标签拥挤 | 最终宽度、系列数、图例文本与位置 | 先调整位置或分面，再选更宽预设；不缩字、不抽稀 |
| 中文方框或字体回退提醒 | 实际解析到的字体、混排／数学字形 | 使用合适中文字体并检查最终图，不只看字体名称 |
| 明明把文件名写成 .tiff 却还是 JPEG | 是否显式传 formats／--format | 用 `--format tiff`；扩展名不控制格式 |
| 移动旧重跑脚本后找不到输入 | 旧 launcher 保存的是原绝对路径 | 修改路径或改用便携 bundle；不要以为副本带了数据 |
| 复现包缺少 main／panel 输入 | 是否是默认不含数据的包 | 按 manifest 提供全部 ID；有权携带数据才制作含数据包 |
| 输出包／图集目录已存在 | 是否复用了非空目录 | 换新位置，不自动清空旧交付或覆盖原始结果 |
| 报告无提醒，是否可直接投稿？ | 当前期刊要求与最终尺寸人工检查 | 无提醒不是认证，仍需检查科学内容、图注、格式与版式 |

若请求超出当前范围，先说明“哪项接口没有实现”，再给已支持的替代路径。例如：独立双指标改分面、KDE 需求改用 ECDF 或显式选择已有 violin、空间温度场改在 ParaView 展示。

<a id="validation"></a>
## 9. 示例与验证

这一节在完整仓库中使用；单独安装的 Skill 不包含根目录的 `examples/`、`tests/` 与 `requirements.txt`。在仓库根目录运行，先准备 `.venv`。输出选择新位置，尤其不要复用已有图集／复现包目录。

### 自带合成示例与图集

| 脚本 | 演示内容 | 数据性质 |
| --- | --- | --- |
| `examples/plot_analysis_gallery.py` | 六种分析图、加权／配对分箱及联合分布对比 | 固定随机种子合成数据，不是 CFD 或实验结果 |
| `examples/plot_semantic_gallery.py` | 配色对照、指标 × 工况分面、受控双轴、灰度与三类色觉预览 | 合成曲线及 SD，不是附件测量或论文复现 |
| `examples/plot_soft_uncertainty.py` | 同数据误差棒／色带对比、柔和冷暖与蓝青绿配色、区间定义及复现 | 24 条合成重复轨迹的均值与样本 SD，不是置信区间 |
| `examples/plot_algorithm_comparisons.py` | 显式参考阶、精度—成本、局部放大、跨格布局、共享热图色标 | 合成算法比较，不是真实求解器性能验证 |

```bash
MPLBACKEND=Agg .venv/bin/python examples/plot_analysis_gallery.py --output figures/analysis_gallery
MPLBACKEND=Agg .venv/bin/python examples/plot_semantic_gallery.py --output figures/semantic_gallery
MPLBACKEND=Agg .venv/bin/python examples/plot_algorithm_comparisons.py
MPLBACKEND=Agg .venv/bin/python examples/plot_soft_uncertainty.py --output figures/soft_uncertainty_new
```

前三个图集附独立 `synthetic_caption_notes.txt`；色带示例使用 `caption.txt`。灰度和色觉预览是辅助检查，不是统计数据或可达性认证。其他 `examples/` 脚本包含公开数据／DNS／热工水力案例或混合合成内容，可能下载或依赖缓存；先读脚本和来源说明，不把所有脚本视为离线演示。

### 自动检查与人工检查

```bash
.venv/bin/python -m pip install pytest
MPLBACKEND=Agg .venv/bin/python -m pytest -q \
  tests/test_plot_template.py tests/test_analysis_plots.py \
  tests/test_semantic_plotting.py tests/test_algorithm_comparisons.py \
  tests/test_delivery.py
MPLBACKEND=Agg .venv/bin/python -m pytest -q
```

部分真实数据／已生成图集相关测试在无缓存时跳过。测试验证数值语义和程序行为，不替代最终排版宽度下的目视检查：四边刻度、图例与数据遮挡、轴名单位、字体回退、灰度身份、色标范围、面板字母、裁切，以及是否误加了图内标题／来源说明。

<a id="maintenance"></a>
## 10. 文档维护规则

- `SKILL.md` 维护 Agent 的执行原则与按需路由，不堆叠完整参数手册。
- 本手册维护统一选图表、输入约定、兼容矩阵与跨功能边界；专项参考维护详细字段、算法定义和高级示例，避免多份定义互相漂移。
- README 只保留定位、快速开始与文档导航；开发计划保留在仓库 `docs/`，不能当已实现能力介绍。
- 新增 `kind` 时同步更新图型表、分析参数／兼容矩阵、必要数据要求和对应测试；新增增强参数时明确支持哪些图型、哪些组合拒绝、如何保存及复现。
- 不因说明书示例需要而改动默认样式、扩展导出格式、改变数据授权、自动安装依赖或修改用户的既有数据。
