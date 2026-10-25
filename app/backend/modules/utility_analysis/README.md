# 闪光弹分析 v2.0.0

模块 ID 保持 `utility_analysis`，仅实现闪光弹；烟、火、雷不进入本版。

## 输入与分母

只读取完整正式回合中 `in_live_round=true` 的事件。逐颗样本采用 `flashbang_detonate`，不是 `grenade_thrown`，所以回合结束后才引爆的闪不进入样本。每颗记录保留 round_id、tick、投掷者、entityid、爆点和原始事件引用。

事实元数据 `event_inventory` 必须保存 requested、available、returned、counts、extraction_complete。没有该元数据的旧缓存，不把缺少爆炸事件解释成零投掷。

## 影响匹配与降级

1. 原生 `player_blind` 优先：要求 `entityid`、同 tick、可用时的 attacker 身份唯一匹配。没有 ID、多个候选、字段缺失或队伍关系未知，保留未知。绝不按最近位置或最近时刻强行分配。
2. 某些 CS2 demo 没有 `player_blind`。此时仅检查引爆 tick 和前一 tick：同存活 pawn、同队伍、连续 game_time，`flash_duration` 出现新的正值且该 tick 只有一颗闪爆炸，才产生 `estimated` 状态推导记录。
3. `flash_duration` 是持续保留的记录值，不是逐 tick 剩余致盲时间。相同值不产生新记录；不积分累计，不据此认定死亡时仍在盲。相同值刷新、延迟更新、同时爆炸无法在本版完整恢复，因此没有检测到变化的闪仍为未知。
4. 敌方、队友和自己分开统计。每颗闪的人数按 target_id 去重；同一玩家被不同闪影响可重复计数。指标是“已记录的次数”，不是完整命中率；未知样本不作为零。
5. 原生事件完整且该 tick 没有未匹配事件时，可以报告 0 个受影响玩家；字段/流缺失不能报告这样的零。

## 闪助和击杀关联

`flash_assists_recorded` 仅使用 `player_death.assistedflash=true`，并校验 assister 与击杀者同队、与受害者敌对。它独立于逐颗闪匹配，不能唯一归属时仍保留为单独游戏助攻证据。

对已记录受影响的敌人，展示引爆后 `kill_window_seconds` 内被投掷者一方击杀的事件。同 tick 不建立先后关系。这是时间关联，不是因果判断、不等同闪光助攻、不宣称击杀时目标仍处于致盲。默认窗口 5 秒，可配置 0.1—15 秒。

## 界面与扩展

`FlashReview.tsx` 使用通用模块结果 `details.flash_review` 和 `details.flash_assists`。Props 为 `module/result/player/onReplay`；回放回调参数 `{tick, round_id, player_id}`。提供敌方、队友/自己、击杀关联、未知筛选，每页 12 颗。全部证据仍可通过通用 evidence API、JSON/CSV 导出读取。

## 验证

`app/.venv/Scripts/python.exe -X utf8 -m pytest app/tests/test_flash_analysis.py -q`：17 项测试覆盖唯一匹配、实体复用、同 tick 歧义、缺失事件流、队伍缺失、状态持续值、pawn/生命/时间中断、闪助与关联差异、同 tick 击杀、取消。

真实 demo `e454e16b…de2f43` 的只读探针：91 次引爆、71 颗检测到状态变化、20 颗未检测到可唯一归属的变化；73 条敌方、51 条队友、28 条自己记录，7 次游戏闪助，13 颗存在窗口内击杀关联。无原生 `player_blind`，因此结果为 partial。探针使用原始事实状态和直接解析的新增引爆事件，未改写旧事实缓存；模块耗时 7.91 秒，不是完整冷解析耗时。详见 `app/docs/flash-validation.json`。
