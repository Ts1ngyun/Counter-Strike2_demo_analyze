# CS2 Demo Evidence Lab

双击 **start.cmd**，打开 **http://127.0.0.1:8765**。双击 **stop.cmd** 停止。

当前开发电脑已准备好依赖；合作伙伴收到源码包后，先安装 Python 3.12（64 位）和 Node.js 24，再运行 setup.cmd，完成后运行 start.cmd。源码包不是免安装 EXE。

**合作伙伴先读：[交接与模块接入规范](docs/PARTNER_HANDOFF.md)** · [新增模块需求/交付模板](docs/MODULE_HANDOFF_TEMPLATE.md)。

| 模块 | 当前交付 |
|---|---|
| 基础统计 | 真实事件、回合与玩家统计；有效伤害无法完全封顶时保留 raw ADR，并把有效 ADR 标为不可用 |
| 击杀前瞄准变化 | 击杀前 1 秒垂直角度变化；排除 AWP/电击枪，霰弹枪致死距离未知样本单列；旧几何头线保留实验视图 |
| 停步 | 默认移动后首枪，可切换全部射击及武器范围；34% 最大速度参考规则，逐枪证据与说明 |
| 连续射击 | 逐 tick 瞄准方向、攻击输入观测、开枪/受伤标记；不生成压枪准度 |
| 交战与死亡复盘 | 事件时间线、交战前状态、复盘优先级、人工标注与备注，证据可定位到回放 |
| 闪光弹分析 | 敌人、队友、自闪与游戏记录的闪光助攻；原生事件缺失时明确标注估计与未知 |
| 人物定位 / 选位 | 仅空 planned 接口，禁用 |

新增 **2D 战术回放**（离线底图、事件跳转、片段收藏与绘图）及 **个人存档**（一个存档容纳多个 SteamID，独立趋势、去重与历史快照）。使用方式与本次验证见 [复盘与存档更新](docs/REVIEW_V3.md)。

详细使用、离线安装与目录说明：[docs/README.md](docs/README.md)

界面右上角的“显示设置”提供浅色、深色、跟随系统及舒适 / 紧凑布局。默认隐藏 100% 覆盖率和技术明细；覆盖不足、未知、估计及小样本提示继续保留。显示偏好保存在当前浏览器，不影响分析和导出数据。详见 [界面更新与验收](docs/UI_APPEARANCE.md)。

本次修改验收：[docs/REVISION_VALIDATION.md](docs/REVISION_VALIDATION.md) · 历史验收：[docs/VALIDATION.md](docs/VALIDATION.md) · 算法：[docs/ALGORITHMS.md](docs/ALGORITHMS.md) · 字段/时间契约：[docs/CONTRACTS.md](docs/CONTRACTS.md) · 增加模块：[docs/EXTENDING.md](docs/EXTENDING.md) · 来源：[docs/SOURCES.md](docs/SOURCES.md)
