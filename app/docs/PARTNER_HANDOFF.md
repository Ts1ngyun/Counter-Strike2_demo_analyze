# 合作伙伴交接与模块接入规范

## 收到压缩包后

这是可继续开发的 Windows 本地应用源码包，不是免安装 EXE。解压后使用其中的 `app/` 即可，不依赖原作者工作区的 `.deps/`、`demo_output/` 或 Codex。以下命令均在解压后的 `app/` 目录执行。

1. 安装 **Python 3.12 64 位**（本次验证版本）和 **Node.js 24**，确保 `python`、`npm.cmd` 可运行。
2. 首次双击 `setup.cmd`：创建本机 `.venv`，根据 `requirements.lock` 和 `frontend/package-lock.json` 安装依赖并构建前端。首次需要网络；已附带 `frontend/dist/`，但仍需要 Python 依赖。
3. 双击 `start.cmd`，浏览器访问 `http://127.0.0.1:8765`；双击 `stop.cmd` 停止。
4. 自行导入原始 CS2 `.dem`。包中不含录像、历史任务或原作者的分析数据。运行时自动创建 `data/`，其内容只属于当前安装。

若 `python` 命令没有指向正确解释器，明确传入路径：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Python 'C:\Python312\python.exe'
```

首次安装失败时查看控制台错误，修复后重跑 setup。不要复制其他电脑的 `.venv`。安装完之后，分析和导出不需要网络、账号或 API Key。当前包在原开发环境验证过测试和构建，未声称已在另一台全新 Windows 机器完成安装验收。

## 当前交付范围与两个预留模块

当前有六个 active 分析模块：基础统计 `basic_stats`、交战与死亡复盘 `combat_review`、急停 `stop_shooting`、交战瞄准变化 `head_line`、连续射击与压枪 `recoil_control`、闪光弹 `utility_analysis`。2D 回放和个人存档是独立工作区，不属于 planned 分析模块。

- `utility_analysis` 已实现 **2.0.0 闪光弹分析**，沿用原道具模块 ID。展示逐颗闪的敌我/自身影响、游戏记录闪助、闪后击杀时间关联及回放入口。本期没有烟、火、手雷评价。没有原生 `player_blind` 时仅保守展示状态变化推导，缺失记录不当作零效果。算法和真实验证见该模块 README 与 `docs/flash-validation.json`。
- `combat_review` 提供死亡与射击片段、事件时间线、可解释的优先复查排序，以及人工判断、备注、收藏。标签表示复盘情形，不是自动失误判决。`head_line` 分开展示击杀、死亡、非击杀首枪窗口；`recoil_control` 新增逐弹伤害关联和目标移动对照，不提供未验证的压枪准度分。见 `docs/COMBAT_REVIEW.md`。
- 2D 回放提供离线雷达/世界坐标显示、时间轴、倍速、暂停逐 tick、证据定位、楼层筛选与画线书签。雷达资源版本不保证匹配每份 demo；不据此计算遮挡或真实视野。见 `docs/REPLAY.md`。
- 个人存档允许同一档案收录多个 SteamID。用户手动选择当前比赛中的 ID 与目标存档；同场同 ID 去重，重算后再次保存保留历史版本。保存所选玩家指标、证据、人工复盘标注、个人书签与单列的全场书签。不同 ID、算法/实现身份及参数分开统计；趋势按保存时间排列。原任务清理后快照仍可读，2D 回放仍需要原任务事实数据。

| 页面名称 | 固定目录 / 模块 ID | 当前状态 |
|---|---|---|
| 人物定位分析 | `backend/modules/role_analysis/` / `role_analysis` | planned，禁用，业务实现为空 |
| 选位分析 | `backend/modules/positioning_analysis/` / `positioning_analysis` | planned，禁用，业务实现为空 |

开发现有预留模块时沿用其 ID，不新建同义目录。完成实现、schema 和测试后将 manifest 的 `status` 改为 `active`、`enabled` 改为 `true`，填写真实描述。不要只修改状态：空实现不能产生分析结果。其他尚未开发的 planned 模块继续保留空接口。

## 合作伙伴提交的文件格式

交付代码优先使用 Git 分支/补丁，也可按原路径提交这些文件的 ZIP。不能只交一份结论、CSV 或 Notebook。统一 UTF-8，Python 实现算法，JSON Schema 描述参数和结果，YAML/JSON 描述 manifest；当前 `.yaml` 中使用的 JSON 也是有效 YAML。

```text
backend/modules/<module_id>/
  __init__.py
  analyzer.py                # analyze 的真实实现
  module.yaml                # 注册、依赖、版本、界面标题
  parameters.schema.json     # 参数类型/默认值/范围/说明
  defaults.yaml              # 默认参数，必须通过参数 schema
  result.schema.json         # 结果 schema
  metrics.json               # metric_id -> 指标定义
  README.md                  # 公式、输入字段、证据、降级、局限
tests/test_<module_id>.py     # 默认 pytest tests 能发现
docs/<module_id>_validation.md # 真实 demo 验证记录、性能及边界
```

`module_template/` 可用于新模块，里面的 analyzer 是故意抛出 NotImplementedError 的骨架。若把测试放在模块内部，需另外执行该测试路径；默认 `pytest tests` 不会自动跑模块目录的测试。

manifest 格式示例（仅演示结构；业务定义、依赖和指标须由开发者替换，不能当作已实现算法）：

```yaml
id: role_analysis
version: 1.1.0
contract_version: 1
title: 人物定位分析
order: 4
status: active
enabled: true
description: 填写本次实际实现的业务范围与局限
requires:
  tables: [events, rounds]
  capabilities:
    all_of: [events]
optional_capabilities: []
feature_dependencies: []
module_dependencies: []
raw_fields: []
parameters_schema: parameters.schema.json
result_schema: result.schema.json
metric_ids: [your_metric_id]
views: [summary_cards, evidence_table]
```

能力名必须来自实际 `context.capabilities`；`all_of` / `any_of` 表达式由注册器检查。表名声明本身不替代业务字段校验。若使用 `shots`、`bursts`、`engagements`、`movement`，应在 `feature_dependencies` 中声明对应共享特征。`module_dependencies` 用于启用和排序，不提供任意读取其他模块私有结果的接口。

参数 schema 示例，以及对应 defaults（字段名同样只是示例）：

```json
{
  "type": "object",
  "properties": {
    "window_ms": {"type": "integer", "title": "窗口长度（毫秒）", "minimum": 50, "maximum": 5000, "default": 500}
  },
  "required": ["window_ms"],
  "additionalProperties": false
}
```

```yaml
window_ms: 500
```

## 算法接口和数据输入

```python
def analyze(context, parameters, cancellation, progress):
    # 返回普通 Python dict；不自行写 API、不自行创建线程/进程。
    # 实现时使用 check_cancel(cancellation)，并报告 progress(stage, detail)。
    ...
```

核心包装器负责 `describe / validate / plan`，模块实现 `analyze` 即可。导入公共 helper 的路径可参考现有模块：

```python
from ...core.common import metric, ratio, check_cancel

check_cancel(cancellation)
progress('人物定位分析', '正在分析指定回合')
frame = context.query('player_states', player=player_id,
                      start=start_tick, end=end_tick, round_id=round_id)
```

`query` 返回 Pandas DataFrame，`start/end` 是包含端点的 **tick**，不是秒；筛选字段必须实际存在于目标表。可用表：commands、players、rounds、events、player_states、weapon_states、shots、bursts、engagements、movement。先按玩家/回合/窗口缩小范围，避免读取全场高频表。`context.meta`、`fields`、`capabilities` 和 `providers` 提供来源、能力与公共模型；实际表列与时间语义见 `CONTRACTS.md` 和运行后的原始字段检查器。

模块不得重新解析 demo。新增原始字段需要同步修改 `backend/adapters/demo/parser.py` 与 `backend/core/field_catalog.py` 中的登记/探针；只在 manifest 写 raw_fields 不会自动生成适配逻辑。新增共享特征需修改 `backend/features/build.py`、注册器依赖图及 Context 表白名单等相关位置，并验证缓存和依赖关系。

## 返回结果格式

最外层必须符合下面的 schema，可直接从 `module_template/result.schema.json` 起步：

```json
{
  "type": "object",
  "required": ["status", "metrics", "evidence"],
  "properties": {
    "status": {"enum": ["succeeded", "partial", "unsupported"]},
    "metrics": {"type": "array"},
    "evidence": {"type": "array"}
  }
}
```

返回对象为 `{"status": "partial", "metrics": [...], "evidence": [...], "details": {...}}`。status：完整成功 succeeded；部分可判定 partial；必要能力不具备 unsupported。异常由调度器记录 failed。details 是可选扩展，不代替标准指标与证据。

指标推荐通过 `metric(...)` 创建，下面是变量形式的接口示例，不包含伪造统计：

```python
item = metric(
    'role_analysis', 'your_metric_id', ratio(numerator, denominator),
    scope={'player_id': str(player_id)}, unit='ratio',
    n=numerator, d=denominator, eligible=eligible_count,
    evaluated_count=evaluated_count, unknown=unknown_count,
    excluded=excluded_count, sample_unit='round', quality='derived',
    method='实际公式及样本定义', limitations=['实际局限'],
    evidence=evidence_ids,
)
```

每条指标包含 module_id、metric_id、scope、value、unit、aggregation、numerator、denominator、sample_unit、eligible/evaluated/unknown/excluded_count、coverage、method、quality、limitations、evidence_refs。核心自动补齐 parameter_snapshot、algorithm_version、identities、config_hash 和指标目录 definition。

- metric_id 必须在 manifest 的 metric_ids 中注册，并在 metrics.json 下有同名定义。
- SteamID 全程用十进制字符串。未知值用 `None`（JSON null），不填 0；分母为 0 时 value 为 null。
- quality 为 observed / derived / estimated / unknown。实验阈值与几何代理必须明确标注。
- coverage 表示 evaluated / eligible，unknown 仍属 eligible；excluded 属排除样本。统计分母与覆盖率样本数可能不同，须明确填写 evaluated_count。
- 比率以 ratio_of_sums 汇总，必须保留真实分子分母；不能把跨场百分比简单平均。helper 对非比率默认 sum，均值/分位数等不能直接沿用默认跨场求和，须另定义正确聚合并扩展汇总实现。

证据最小形式（变量名代表真实计算值）：

```python
evidence = {
    'evidence_id': evidence_id,       # 稳定、模块内唯一；与 evidence_refs 对应
    'metric_id': 'your_metric_id',   # 供页面按指标筛选
    'round_id': round_id,
    'player_id': str(player_id),
    'tick': start_tick,
    'end_tick': end_tick,
    'raw_field_paths': ['实际原始字段路径'],
    'reason': '本次判断依据，或无法判定的原因',
    'kind': 'your_evidence_kind',
    'values': actual_values,
}
```

核心补入 demo_hash、参数快照、算法版本、原生 tick 分辨率、时间范围（未提供时由 tick 换算）。当前核心把 subtick/source_sequence/command_offset 置 null，不支持模块伪称更精细时序；若后续提供真实来源定位，必须同时修改该注入逻辑和契约。指标/证据最终由 `backend/core/contracts.py` 校验。

metrics.json 是以指标 ID 为键的对象，至少完整填写这些说明：

```json
{
  "your_metric_id": {
    "title": "指标中文名",
    "definition": "业务含义",
    "formula": "可复算的计算式",
    "unit": "ratio",
    "sample_unit": "round",
    "numerator_denominator": "分子和分母的精确定义",
    "inclusion": "纳入规则",
    "exclusion": "排除规则",
    "field_dependencies": ["实际字段/表"],
    "time_requirements": "时间窗口、采样分辨率和边界",
    "parameters": {},
    "source": "公式/模型/标定来源",
    "limitations": "无法证明的内容及降级行为",
    "algorithm_version": "1.1.0",
    "evidence_entry": "GET /api/jobs/{job_id}/evidence/role_analysis?metric_id=your_metric_id"
  }
}
```

## 页面接入和缓存

普通模块通过 manifest 自动发现；参数表单、指标表和证据 JSON 使用通用渲染。复杂嵌套参数、地图覆盖层或新类型曲线不保证自动适配，需检查 `frontend/src/main.tsx`，必要时增加组件或按 evidence kind 注册 `customPanels`。当前已有 `CombatReview.tsx`、`FlashReview.tsx`、`Replay.tsx`、`Profiles.tsx` 专用组件。views 是声明，不是可自动执行任意组件的插件语言。

专用组件中的 `details` 列表不由通用指标/证据筛选自动处理，必须主动遵循任务 `config.players`、当前玩家和适用的回合筛选。回放定位统一用 `{tick, round_id, player_id}`，跨任务定位另传 job ID。新增人工标注应按 demo、算法/参数与稳定 evidence ID 隔离；新增统计聚合必须保留 SteamID 范围，不能混合多个 ID 的个人趋势。

更新后停止并重启服务，前端代码变化时重新构建，再新建任务/重算；旧任务不会自动出现新模块结果。模块 manifest、analyzer.py、配置和依赖参与缓存键。模块目录内全部 Python 文件现在均进入模块代码 hash；修改辅助算法或公式/分母仍应提升 module.yaml 的版本；共享特征/Provider 修改需同步版本及缓存依赖。不要用删除全部 data 的办法掩盖缓存失效问题。

## 验收和回交

在 `app/` 下执行：

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests -q
Push-Location frontend
npm.cmd run build
Pop-Location
```

再用真实 demo 验证：模块可选择、参数合法/非法、取消、字段缺失、空样本、零分母、原始证据可追溯、CSV/JSON/HTML 导出、重算和缓存失效。记录 parser/模块版本、demo 哈希、地图/补丁、样本分母、unknown、运行时间、峰值内存及尚未支持的场景。未验证可见性不能宣称“看到敌人”；没有角色标注/地图模型/道具影响证据不能直接给综合能力分。

当前通用测试保证 `role_analysis` 和 `positioning_analysis` 两个 planned 模块为空。后续实现它们时需同步更新 `tests/test_algorithms.py` 的 `test_registry_planned_empty`、`test_planned_never_queued` 及适用的 `tests/test_api.py` 断言：已实现模块改为验证 active 合同和真实运行，尚未实现的继续验证空接口。不要把这些保护全部删除。

`scripts/integration.py`、`audit_real.py`、`finalize_validation.py` 是原验收样例专用脚本，包含该比赛的事件数/比分等断言。尤其 `finalize_validation.py` 仍保存早期“三个预留模块”的断言与报告模板，不能直接作为本版验收或重生成当前报告；需按目标版本更新后再使用。使用任意新 demo 时要建立相应验收用例，不能把样例不匹配解释为算法故障。原录像未打包，`docs/VALIDATION.md` 是历史验收记录，不是伙伴新版本的验收结果。当前增量验证另见 `docs/COMBAT_REVIEW.md`、`docs/REPLAY.md`、`docs/review-v3-validation.json` 和 `docs/flash-validation.json`。

回交：代码 + 配置/schema + 指标说明 + 自动测试 + 真实验证记录 + 变更/兼容说明。可直接填写 [MODULE_HANDOFF_TEMPLATE.md](MODULE_HANDOFF_TEMPLATE.md)。本包没有添加新的开源授权；项目使用/分发约定由双方确认，第三方依赖沿用各自许可证。

## 如何再次打包

```powershell
python scripts\package_source.py
```

默认生成在 `app/` 的上级 `deliverables/`，包括源码、锁文件、文档、测试和构建好的前端；排除 `.venv`、node_modules、data、缓存、原始 demo、开发探针输出与历史完整报告。包内 SOURCE_MANIFEST.json 记录逐文件 SHA256，旁边 `.zip.sha256` 校验整个包。需要交付比赛录像或历史分析时单独传递，不混入源码版本。

个人存档可从页面导出 JSON（包含历史快照）；当前没有存档 JSON 导入/合并功能。迁移整个本地使用环境时，先停止服务，再单独备份完整 `data/`，不要在数据库写入期间只复制单个 SQLite 文件。浏览器中的主题偏好与自定义底图校准保存在 localStorage，不包含在源码包或存档 JSON 中；内置离线雷达资源及来源清单随前端交付。
