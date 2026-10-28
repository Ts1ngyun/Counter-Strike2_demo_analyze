# CS2 Demo Evidence Lab

本地 FastAPI + React/TypeScript/Vite 应用。正式输入为原始 PBDEMS2 `.dem`；未读取旧 `demo_output/player_state_1hz.csv` 作为算法输入。原有脚本、依赖及旧输出均保留。

## 启动与停止

本工作区已经安装依赖并构建前端。双击 `app/start.cmd`，浏览器打开 **http://127.0.0.1:8765**。双击 `app/stop.cmd` 停止服务及任务进程。日志在 `app/data/server.log` 和 `server-error.log`。服务默认只监听 IPv4 回环；禁止跨站写请求和非本地主机名。

首次迁移到其他电脑，安装 Python 3.12 64 位和 Node.js 24（已验证版本），运行 `app/setup.cmd`。也可执行 `powershell -File app/setup.ps1 -Python C:\path\python.exe`。Python 依赖由 `requirements.lock` 精确锁定，前端由 `package-lock.json` 锁定。需要联网安装；安装完成后的分析、图表、内置雷达及导出不使用网络/CDN/API Key。当前交付是源码包，还不是免安装 EXE。

本次开发环境使用工作区 `.deps/` 中已有的 parser/Pandas/Arrow，通过 `.venv/Lib/site-packages/workspace_deps.pth` 引入，其他依赖装入隔离 `.venv`。迁移时不要复制该绝对路径 `.pth`；在新电脑按锁文件安装完整环境。不要直接拷贝 Windows venv 当成可移植安装包。

## 使用

1. 拖入一个或多个 `.dem`；浏览器直接发送 File，不调用 arrayBuffer 复制整份录像。后端 multipart 临时文件落盘，再分块哈希和保存应用副本。
2. 在“参数与模块”选择模块、编辑参数或限定十进制 SteamID；默认所有玩家、六个 active 模块。人物定位和选位两个 planned 模块无法启用。
3. 队列显示真实阶段，不显示虚构完成百分比。默认一个独立进程解析一个文件；可用环境变量 `CS2_WORKERS=2` 开启最多两个。相同内容的并发任务有文件锁，防止缓存互相覆盖。
4. 选择任务、玩家、模块。点击指标或证据行打开实际数值、时间窗口、规则和曲线；可定位到 2D 回放。回合和适用的其他筛选影响证据/专用卡片，指标分母仍是其声明的范围；分区/分页不改变算法样本。
5. 修改参数后“重算”：事实缓存、未变化模块缓存复用；修改模块代码、parser、规范化、provider 或配置将失效对应缓存。功能变化的模块仍应主动递增语义版本。
6. 导出完整 JSON、指标 CSV 或包含完整证据的离线 HTML。HTML 体积较大，证据折叠后按需查看。
7. “本地存储”可清理应用中的原始副本；高频事实、现有证据和外部原始文件仍保留。副本清理后，缺失字段无法补抽，需重新导入。

任务取消先设置取消标志；长时间停留在 Rust 原生解析时，调度器在约 2 秒后终止该工作进程。发布标记只在完整分区/特征完成后写入；失败的部分文件不会当成缓存命中。异常退出的任务在下次启动时标为失败，可重试。

## 已实现的分析与复盘

| 功能 | 当前范围 |
|---|---|
| 基础统计 `basic_stats` | 击杀、死亡、助攻、伤害与回合参与等；保留证据和未知覆盖 |
| 急停 `stop_shooting` | 默认移动后首枪达标率，可切换开枪低速达标率；全武器/排除跑打武器视图 |
| 交战瞄准变化 `head_line` v2.2.0 | 击杀、死亡、非击杀射击首枪前窗口分开统计；保留指定武器排除和未知规则 |
| 连续射击与压枪 `recoil_control` v1.2.0 | 视角轨迹、攻击输入、逐弹伤害关联及目标运动对照；不提供未验证的压枪准度 |
| 交战与死亡复盘 `combat_review` v1.0.0 | 事件支持的情形标签、优先复查片段、时间线，以及人工判断/备注/收藏 |
| 闪光弹 `utility_analysis` v2.0.0 | 逐颗闪的敌方/队友/自身影响，游戏闪助和闪后击杀时间关联；目前只做闪光弹 |

闪光原生事件缺失时，仅将新状态变化与唯一同 tick 爆炸关联并标记估计；未检测到变化不等于零效果。`flash_duration` 不是剩余致盲时间，不能累计持续值或据此判断死亡时仍在盲。闪后击杀仅表示时间关联，游戏闪光助攻单独展示。交战情形标签也不是自动失误判决。详细规则见 [COMBAT_REVIEW.md](COMBAT_REVIEW.md) 和 [闪光模块说明](../backend/modules/utility_analysis/README.md)。

## 2D 回放、收藏和个人存档

- **2D 回放：**显示真实玩家位置、朝向、生命与武器，使用随应用交付的离线雷达；也可切换世界坐标或导入本地底图。支持回合/玩家/事件筛选、时间轴、0.25—4 倍速、暂停逐 tick、证据跳转和有校准数据时的楼层选择。播放预览采用采样帧，暂停定位读取对应 tick 的观测状态，不重建玩家屏幕。
- **书签与画线：**保存当前回合、tick、关注玩家、备注和地图画线，相同 demo 的重跑任务共享书签；已移除的书签可以恢复。自定义底图与校准保存在当前浏览器。
- **个人存档：**创建并选择目标档案，手动勾选当前比赛的一个或多个 SteamID 后保存。一个档案允许多个 ID，各自隔离指标与趋势；同场同 ID 只计一次。再次保存重算结果或更新的标注时保留历史快照，可查看旧版、移出趋势和恢复。
- **跨场对比：**按玩家、地图和指标筛选，算法、参数、实现身份不同的记录分组；比率按总分子/总分母聚合，分位数不平均。重复复盘情形可以展开对应片段。趋势时间是保存时间，不冒充比赛发生日期。
- **离线保留：**存档保存所选玩家的指标、证据、人工标注、个人书签及单列的全场书签。可导出包含历史快照的存档 JSON；目前没有 JSON 导入/合并功能。快照不依赖原任务结果继续存在，但回放需要原任务事实缓存。

雷达资源版本与 demo 地图版本是否完全匹配尚未验证，只作视觉参考，不用于遮挡、烟雾或可见性判定。详见 [REPLAY.md](REPLAY.md)。

右上角“主题”打开新的主题与显示面板：五套撞色主题、明亮/暗黑/跟随系统、浅色/深色分别保存的自定义颜色，以及液态玻璃、减少动效和舒适/紧凑布局。核心指标均有面向普通用户的三层解释。默认隐藏完整的 100% 覆盖率，覆盖不足及未知仍保留；方法说明、样本明细和技术信息可选显示，偏好保存在浏览器。详见 [UI_REDESIGN.md](UI_REDESIGN.md) 与 [UI_APPEARANCE.md](UI_APPEARANCE.md)。

## 命令行与检查

在 `app/` 目录：

```powershell
.venv/Scripts/python.exe -X utf8 -m backend.cli 'C:\path\match.dem'
.venv/Scripts/python.exe -X utf8 -m backend.cli 'C:\path\match.dem' --modules basic_stats --players 76561198041683378
.venv/Scripts/python.exe -X utf8 -m pytest tests -q
cd frontend
npm.cmd run build
```

真实 HTTP 集成（先启动服务）：

```powershell
.venv/Scripts/python.exe -X utf8 scripts/integration.py 'C:\path\match.dem'
```

集成脚本针对原验收样例的断言位于测试脚本；新 demo 应建立对应验收数据。`scripts/finalize_validation.py` 仍含早期三个 planned 模块的断言与报告模板，使用前需更新，不能直接覆盖本版文档。产品算法不硬编码样例比分和玩家名单；内置雷达的地图资源/坐标变换有明确来源与版本。

## 文件组织

- `backend/adapters/demo/`：容器命令索引、demoparser2 适配和高频抽取。
- `backend/core/`：契约、能力表达式、依赖排序、SQLite 任务/模块状态、缓存、只读 DuckDB 查询、进程调度。
- `backend/features/`：共享 shots/bursts/engagements/movement；不会由每个模块重复解析 demo。
- `backend/providers/`：版本化武器实验参数、姿态模型、地图/可见性接口；分析路径实际调用这些 provider。
- `backend/modules/`：六个 active 模块，以及 `role_analysis`、`positioning_analysis` 两个空的 planned 模块。
- `backend/routers/`：回放帧/书签、人工交战标注、个人存档接口；`backend/services/results.py` 提供只读结果复用。
- `data/uploads/`、`facts/`、`module_cache/`、`results/`：应用拥有的数据；`jobs.sqlite` 存储任务、配置和模块结果索引。
- `data/review/annotations.sqlite3`：交战人工标注；`data/replay/`：按 demo 保存的书签；`data/profiles.sqlite`：个人档案、快照历史和趋势摘要。
- `frontend/`：React/TypeScript 应用；`src/app` 外壳与任务状态，`src/views` 页面，`src/theme` 设计 token 与偏好，`src/explain` 指标词典与三层解释，`src/ui` 统一组件；`frontend/public/maps/` 为内置雷达与来源清单。
- `docs/ALGORITHMS.md`、`CONTRACTS.md`、`SOURCES.md`：算法、字段/时间契约与来源；界面设计见 `UI_REDESIGN.md`，主题维护见 `UI_APPEARANCE.md`，本轮验证见 `UI_REDESIGN_VALIDATION.md`。`VALIDATION.md` 为早期验收记录，新版增量另见 `COMBAT_REVIEW.md`、`REPLAY.md`、`review-v3-validation.json` 和 `flash-validation.json`。

本期没有三维回放、TrueView 预测重建、完整可见性/烟雾模型、职业基线、综合能力分，以及人物定位、选位两个规划模块的业务算法。交接、继续开发与源码打包见 [PARTNER_HANDOFF.md](PARTNER_HANDOFF.md) 和 [EXTENDING.md](EXTENDING.md)。
