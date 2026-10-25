# 增加一个模块

1. 全新模块：复制 `app/module_template/` 到 `app/backend/modules/your_module/`，ID、目录名一致，使用 lower_snake_case。当前仅 `role_analysis`、`positioning_analysis` 两个 planned 模块保留空接口；继续开发时沿用原目录和 ID，按 [合作伙伴交接规范](PARTNER_HANDOFF.md) 补全文件并在验证后启用。`utility_analysis` 已是 active v2.0.0 闪光弹分析，不得再当空骨架覆盖；扩展其他道具时保留现有闪光语义和测试。
2. 编辑 module.yaml：版本、中文标题、order、字段依赖、能力表达式、共享 feature 依赖、可选 module_dependencies、metric_ids 与 views。需要新增原始字段时，只在 adapter 的 RAW/目录登记其路径、依赖、时间/类型/范围探针；模块不得自行调用 parser。
3. 定义 parameters.schema.json、defaults.yaml、result.schema.json、metrics.json。参数分事实常量、实验校准和用户参数；后两类要可追溯。每个指标声明分子分母、覆盖率/unknown、单位、公式和证据入口。
4. 实现 analyzer.py 中 analyze。通过 ctx.query 读取范围，不读取整场巨大表。频繁检查 cancellation。返回 status、metrics、evidence；MetricResult/Evidence 会被公共 schema 校验。describe/validate/plan 由 registry.Analyzer 包装；需要额外业务参数验证可在 analyze 起始处执行。
5. 编写本模块合成边界测试，再用真实 demo 验证字段/时序。未知字段导致 unavailable 或 partial，不能补零，也不能生成模拟结果伪装为解析结果。
6. 运行 pytest、生产构建、集成测试。源码/manifest/配置 hash 自动使模块缓存失效；公式或分母变化仍必须提高模块版本。新增普通模块只需添加目录，不改核心调度器。

前端从 manifest 发现模块、从参数 schema 生成表单、从 MetricResult 渲染卡片/表格和 Evidence 渲染原始值。`views` 声明支持的通用视图，不自动执行插件代码。指标 title 优先来自 metrics.json；旧结果缺此目录时退回 ID。通用曲线显示数值系列，NULL 不补零。特殊证据面板可在 `customPanels` 按 evidence kind 注册；完整交互可使用独立组件并明确接入主页面，现有交战/闪光复盘即采用此方式。没有专用组件仍能读取完整证据 JSON。

## 当前扩展示例

- `combat_review`：标准分析模块负责片段、指标与证据；`backend/routers/combat.py` 独立保存人工判定、备注和收藏。标注按 demo、算法/参数及 evidence ID 隔离，不把人工评价写回事实或缓存分析结果。
- `utility_analysis`：原生闪光事件身份匹配，缺失时保守使用状态变化；`event_inventory` 区分事件未抽取、流缺失与可确认的零。`flash_duration` 不是剩余致盲时间，不按每 tick 累加。`FlashReview.tsx` 显式遵循任务玩家范围、当前玩家和回合筛选。
- `Replay.tsx` / `backend/routers/replay.py`：限量读取回放帧，暂停时请求准确 tick；书签按 demo hash 保存，重跑共享。雷达图和坐标变换不等同可见性几何，新增地图要保存资源来源、版本及校准说明。
- `Profiles.tsx` / `backend/routers/profiles.py`：同一存档允许多个 SteamID，但逐 ID 保存快照与趋势。相同 demo+ID 去重，重算再次保存生成历史版本；快照包含相应人工标注和书签。指标分组包含与 demo 无关的算法/实现身份，不能使用整个 facts hash 使每场成为独立组，也不能只凭指标名称混算。比率合并分子分母，分位数只展示逐场趋势，不平均。

专用视图里的 `details` 不会被通用证据筛选器自动过滤。开发者必须处理 `config.players`、当前玩家、回合及适用的其他筛选，同时确保回放按钮传递 `{tick, round_id, player_id}`。增加只适用于某模块的筛选时应限制其可见范围，避免用户以为它改变了无关模块的统计分母。

共享特征需要单独注册依赖 DAG 和 builder，再由多个模块复用。模块之间只能声明依赖与读取公共事实，禁止修改其他模块结果。新 schema 若不兼容 contract v1，应提升版本并提供显式迁移或保留旧结果重新计算，不能静默覆盖历史含义。

执行 `pytest tests` 与前端生产构建后，再针对真实 demo 验证。当前闪光边界用例在 `tests/test_flash_analysis.py`，交战/瞄准扩展在 `tests/test_combat_review.py`，个人存档在 `tests/test_profiles.py` 和 `tests/test_profiles_independent_review.py`。早期 `scripts/finalize_validation.py` 含旧模块数量与样例断言，使用前需更新，不能用它覆盖本版交付说明。
