# 数据与扩展契约 v1

## 数据流及存储

原始文件 → PBDEMS2 命令 framing（真实偏移）→ demoparser2 网络/实体和事件 → Parquet 事实 → 共享特征 → 模块结果和证据 → 本地 Web。

`demos.json` 保存 SHA256、大小、header/patch/protocol、parser 身份、FileInfo、实际字段与最终队伍状态；`capabilities.json` 保存本文件探针和全量覆盖率；`fields.json` 为字段目录；`raw_fields.json` 是该文件实际更新字段列表。规范化缺失协议字段为 null，不能从 patch 猜协议。

事实表：`commands`（命令序号/偏移/tick）、`players`（字符串 SteamID/名称历史）、`rounds`（稳定 ID、原始回合、阶段、边界、结果、freeze-end 参与者与阵营映射）、`events`（原始 JSON、原始参与者、类型内序号）、`player_states`、`weapon_states`、`shots`、`bursts`、`engagements`、`movement`。每个状态分区最多请求 8192 tick。原生库仍会为每批扫描原始文件并返回 DataFrame，这不是流式协议解析。容器索引一次扫描；特征按回合读取，查询过滤在 DuckDB 执行，避免把全场复制给模块。

## 时间

- `commands.tick` 是容器命令 tick；state `tick` 来自 parser demo tick，不叫 server tick。
- FileInfo 的播放秒/播放 tick 给出录像 tick 尺度，再与相邻状态 `game_time` 增量校验。未预设 64 Hz；校验失败时高频机械计算不可用。
- 检查的 parser 源码 `game_time` 为 net_tick/64 的派生字段。此样例起点 901 秒，不是录像相对秒。源码、实际间隔校验及 raw 值分别记录。未暴露的 net tick 不反推伪装为原生字段。
- `demo_time=tick×FileInfo interval`。subtick 为 null。事件附带实体状态与 tick 末状态不能互换。
- shots 保存 `[tick-1 末, tick 末]` 两侧状态、采样分辨率和判定局限；速度来自位置区间，不保证区间内每一个瞬间都低于阈值。
- 同类型事件按导出行号建立 event_id，不宣称有跨类型消息顺序。伤害封顶遇同受害者同 tick 多事件降级。同 tick 多枪为 ambiguous。
- 状态差分要求相邻 tick、匹配实际 dt、同回合/队伍/玩家实体、双方存活，以及合理位移；死亡/重生、实体复用、传送、间隙和时间跳变不差分。

字段目录包含 canonical_name/raw_path、单位、坐标约定、类型、来源、转换版本、时间语义、分辨率、范围和空值规则。别名 X/Y/Z 明确记录 cell+offset 派生；旧 aim_punch_angle 无输出保持不支持。能力报告区分“有列、有值、覆盖率、类型/范围检查”和“语义已验证”，尤其 raw recoil 有值不代表 effective_recoil 可用。

## 模块接口与依赖

`Analyzer.describe/validate/plan/analyze(context,parameters,cancellation,progress)` 是统一入口。`AnalysisContext.query(table, player, start, end, round_id, limit, offset)` 只提供事实/特征读取，不能写其他模块的结果，也不暴露 parser 实例。

manifest 用 schema 校验。`requires.capabilities` 支持 `all_of/any_of`；`feature_dependencies` 和 `module_dependencies` 有拓扑/环检查，模块依赖自动纳入运行计划。现有共享特征由统一 builder 一次建立；新增共享特征要在 registry/feature builder 注册，新增普通指标模块无需改调度器或前端。

生命周期：planned / queued / running / succeeded / partial / unsupported / failed / cancelled。数据质量：observed / derived / estimated / unknown。二者独立。没有任意数值“置信度”。运行失败按模块隔离，文件失败不会停止后续文件。

MetricResult 与 Evidence 结构由 `core/contracts.py` 校验。每个指标在 `metrics.json` 定义中文名称、公式、单位/样本、纳入/排除、依赖、时间要求、参数、来源、局限、版本及证据 URL。比率有分子分母，零分母 null。覆盖率是 evaluated/eligible，排除数另计；ADR 的伤害可验证覆盖率按 hurt 事件计算，数值分母仍为回合。

证据定位：文件 hash + round_id + 字符串 player_id + tick/时间区间 + event index（可用时）+ raw paths + 数值/曲线 + 参数 + 规则/判定原因。只有 commands 表有真实字节偏移；事件不能精确映射到命令时 `command_offset=null`。

## 缓存和版本演进

事实 key：内容 hash、parser 身份/版本、规范化版本、adapter/container/字段目录代码 hash、请求字段集合。已存在完整字段超集可复用，包括已探明不支持的请求字段。特征 key 加 feature 版本/代码和 provider 配置/代码 hash；模块 key 再加模块代码/版本、参数、公共结果工具代码及 provider 身份。只在完整成功写入原子完成标记后可复用。

contract_version 固定为 1；metric ID 用 `lower_snake_case`。新增指标/可选字段可加版本；改公式、分母或语义须提升模块版本。破坏 schema 的变化须提升 contract_version，并另写旧结果迁移器；当前不会暗中重解释旧文件，旧结果保留其版本/参数。若没有迁移器，用原始事实重算新版本并保留旧结果。

批次同哈希只计一次、SteamID 合并。相同算法/参数/范围的比率用总分子/总分母。分位数不平均；需要合并时从导出的原生样本重算。该版本没有跨场分位数图和职业基线。
