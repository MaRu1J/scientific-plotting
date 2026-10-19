# 验证记录

## 基线与完整测试

- 当前工作基线确认为 `4cc1c1c — Add CFD plotting validation suite and fix long-form heatmaps`。
- 开始时已有 `examples/plot_scatter_pointline_datasets.py` 和 `figures/scatter_pointline/` 两处未跟踪内容，本轮未修改、删除或纳入产物。
- 仓库及父目录未发现适用的 AGENTS.md；已读取现有 Skill、风格规范、母板、两组测试、CFD 示例和上轮报告。
- 环境中没有 `python` 别名，使用项目已有 `.venv/bin/python`，未添加依赖。
- 基线测试：**37 passed, 2 warnings**，原始输出为 `baseline_pytest.txt`。
- 最终完整测试：**82 passed, 2 warnings**，增加 **45** 项；原始输出为 `pytest.txt`。两条为旧校验测试中的 Arial→Liberation Sans 警告，无 AutoMinorLocator-on-log 警告。
- Skill 检查 `quick_validate.py scientific-plotting`：**Skill is valid!**
- README 的两条实际 CLI 示例（残差、mixed+误差）及生成的 CLI 启动器均执行成功，记录为 `cli_validation.txt`；临时输出未混入本轮 13 张验证原图。
- `git diff --check` 通过；上轮图集、原始 DNS 和 `.gitattributes` 均无改动。

主要新增测试覆盖：两轴/双轴对数、十数量级次刻度、非正数拒绝、混合显式启用、纯线/点线不可被配置暗改、样式参数合法性、逐组尺寸覆盖、log-display 密度、图例布局后重算、稀疏/密集重合独立、散点独立密度、三种误差、零参考、错位/倒序网格拒绝、线性插值记录、拒绝排序和外推、自定义虚线跨主图/图例/误差图一致、单/双栏长图例、误差轴单位标签、导出 dpi 不改变尺寸、DNS 原始交错网格以及搬移断网逐字节复现。

## 原生 CFD 成图审计

- 13/13 个场景绘制成功。每组 artist 的坐标和数值与 CSV 逐项一致，保留组内输入顺序。
- line 均无点标记；point-line 均有连接和点标记，`markevery=None`；mixed 各组类型明确。
- 13/13 图检查物理尺寸、PNG 像素、四边框和朝内双侧刻度，所有可见主/次刻度标签、轴名、偏移文本和图例均在固定画布中。
- 图例覆盖变换后曲线/散点的采样检查为 0 hits；此检查是离散几何审计，仍辅以视觉检查，不声称形式化证明所有像素不相交。
- 真实 DNS 仅读缓存；均值/uu/ww 与 vv/-uv 的各自坐标在回归测试中与原表精确核对，未插值对齐。
- 验证结束后原始三份 DNS 的 SHA256 与开始读取时及旧报告一致。原作者文本、引用和 `.gitattributes` 原始文件保护未改变。

## 图像复核

- 实际打开 DNS、误差、密度三类总览，覆盖全部 13 个场景；另外打开 01、05、06 原图及四场景黑白拼图检查细节。
- 01 初次检查发现十数量级对数次刻度会被默认 LogLocator 的步长策略整体省略，已修复；全量 2–9 网格在单栏又过密，因此根据最终每十倍区间的显示长度选择标准 2/5 次刻度，最终原图复核清楚可辨。
- 05/06 中的主图小差异不可强行视觉放大解释；误差下图清楚区分约 1e-3 和 2.5e-4 的正偏差，以及合成测点的正负偏差。
- 10 的长图例移动到画布上方，保持 Times 替代字体与 9.5 pt 图例文字；未缩字号或扩大预设尺寸。
- 11/12 每组分别保持 5 pt 和 2.4 pt 标记；密点仍可互相覆盖，完全重合的主曲线在黑白下不可能凭空分开。黑白主要依靠已定义的线型和点形；误差图比高度重合的主图更适合比较精度。
- 未观察到轴名、刻度、图例的明显裁切；单栏误差图仍较紧凑，图例多、密度高时优先选择双栏。此检查不是纸质印刷打样。

## 搬移与禁网复现

执行 `examples/validate_cfd_optimization.py --verify-replay figures/cfd_optimization`：

1. 新建仓库外临时目录，只复制 `manifest.json`、`data/`、母板快照、runner 与 `reproduce.py`。
2. **不复制原始 DNS**、已有图片或原路径下的任何脚本；工作目录也在仓库外。
3. 用临时 `sitecustomize.py` 在启动器及子进程中禁止 socket connect/connect_ex/create_connection。
4. 实际执行搬移后的 `reproduce.py`；13 个案例从 CSV、参数和本地母板离线重绘。
5. **17/17 PNG 字节一致**（13 原图、3 总览、1 黑白拼图）。
6. **5/5 误差 metadata JSON 字节一致**，共 **22/22** 文件一致。

机器可读结果为 `replay_verification.json`；该流程也加入自动化测试。母板、runner 和每张 CSV 的 SHA256 在重绘前检查，防止悄悄使用已变的输入。
同环境的字节一致不保证跨字体、Python/Matplotlib 版本或操作系统一致；这类变更仍需重新审图。

运行环境记录于 `manifest.json`：Python 3.14.4、Matplotlib 3.11.2、NumPy 2.5.4、pandas 3.0.6。
