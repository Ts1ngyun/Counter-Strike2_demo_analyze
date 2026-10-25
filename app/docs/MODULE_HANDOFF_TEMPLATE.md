# 模块需求 / 开发回交模板

复制此文件，每个模块填一份。开发规范见 PARTNER_HANDOFF.md；下列占位项必须用实际方案和测试证据替换。

## 需求确认

- 模块 ID：role_analysis / positioning_analysis / utility_analysis / 新 ID
- 中文名称、目标版本：
- 用户要回答的问题：
- 本次实现范围、不覆盖的场景：
- 输出指标：逐项列 metric_id、名称、单位、公式、分子、分母、样本单位、纳入/排除、unknown、证据入口。
- 必需事实表/字段/能力与时间语义：
- 可选能力、缺失时如何降级：
- 是否需要新字段适配、共享特征或地图/可见性 Provider：
- 参数：名称、类型、默认值、合法范围；区分事实常量/实验标定/用户参数。
- 标注数据或阈值来源、验证方式：
- 界面：通用指标/证据即可，或描述新增组件需求。

## 实施与验证回交

- 变更文件清单：
- module.yaml / parameters.schema.json / defaults.yaml / result.schema.json / metrics.json 是否一致：
- 分析器接口：analyze(context, parameters, cancellation, progress)。
- 示例输出：从真实运行导出的标准 metrics/evidence，注明 demo 哈希和来源；不要手造“成功”结果。
- 单元测试命令、结果、边界覆盖：
- 真实 demo：哈希、地图、补丁、parser 版本、事件数核对、时序核对。
- 缺失字段/未知/零分母/取消/导出/缓存测试结果：
- 性能：机器配置、耗时、峰值内存、事实/结果大小。
- 支持和未验证的地图/补丁范围：
- 版本/缓存失效、历史结果兼容说明：
- 新增依赖与来源/许可证；同步锁文件：
- 已实现模块启用，未实现 planned 继续禁用；相应测试的调整：

## 可发给开发者或 AI 的任务说明

请在现有 CS2 Demo Evidence Lab 源码上实现上面填写的模块。先阅读 docs/PARTNER_HANDOFF.md、CONTRACTS.md、ALGORITHMS.md 及相邻模块源码。沿用固定模块 ID 和统一分析器接口，读取 AnalysisContext 的事实表，不重复解析 demo。提交完整模块目录、参数/结果 schema、指标目录、测试和真实验证记录；普通界面使用通用渲染，必要的特殊组件单独说明。未知值保留 null，明确估计量及缺失能力，不生成伪造数据或未经验证的综合评分。保持其他模块行为，更新版本及缓存依赖，在验证后启用该模块。
