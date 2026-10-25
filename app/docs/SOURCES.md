# 来源核对 · 2026-10-23（Asia/Shanghai）

实际安装并测试 `demoparser2==0.42.0`。当天 PyPI JSON `info.version` 返回 0.42.0；版本锁与真实样例探针优先于动态 README。以下远端 main/latest 来源会变化，不能把其文档声明等同每个 demo 的实际能力。

| 来源 | 核对内容与用途 |
|---|---|
| [demoparser 仓库](https://github.com/LaihoE/demoparser) / [Python API](https://github.com/LaihoE/demoparser/tree/main/documentation/python) | parse_ticks 的字段/tick 请求及返回 DataFrame；parse_events 的附加字段。本项目自行探针验证列、值、覆盖率、类型与时间。 |
| [collect_data.rs](https://github.com/LaihoE/demoparser/blob/main/src/parser/src/second_pass/collect_data.rs) / [maps.rs](https://github.com/LaihoE/demoparser/blob/main/src/parser/src/maps.rs) | 检查 game_time 派生方式、位置/角度和 velocity 行对齐；源码与真实相邻窗口的数值验证分开记录。 |
| [Source 2 demo.proto](https://github.com/SteamDatabase/Protobufs/blob/master/csgo/demo.proto) | 仓库重定向至 SteamTracking/Protobufs；命令枚举和 FileInfo 字段参考。 |
| [pbdems2 file structure](https://docs.rs/pbdems2/latest/pbdems2/guide/file_structure/index.html) / [entities](https://docs.rs/pbdems2/latest/pbdems2/guide/entities/index.html) | 当前页面标示 pbdems2 0.4.1；16字节固定头、varint 命令 framing、Snappy 位与实体增量概念。自建扫描器只做容器索引/完整性，不重写实体协议。 |
| [HLTV HS%](https://www.hltv.org/news/15686/pickem-hs-who-to-choose) | 2015-08-15 文中以爆头击杀占总击杀解释 HS%。本产品对敌口径公开，不能与 hurt/fire 混为命中率。 |
| [HLTV Rating 3.0](https://www.hltv.org/news/42485/introducing-rating-30) / [2026-10-01 更新](https://www.hltv.org/news/45596/rating-30-receives-small-accuracy-improvements) | 核对公开页面存在及模型持续更新；不复刻未公开实现，不输出虚构官方评分。 |
| [Valve TrueView 官方公告](https://store.steampowered.com/news/posts/?appgroupname=Counter-Strike%3A+Global+Offensive&appids=730&enddate=1765670125&feed=steam_community_announcements) | 2025-11-04：重跑客户端预测以改善回放，版本不匹配及渲染/效果时序仍有限制。本产品只解析观测状态，没有执行这套预测重建。 |

产品实验参数：头线窗口、近似眼/头高、头半径、锥角、速度阈值、移动滞回、最小运动持续时间、连发间隔和最低弹数，均由本产品提出，未归因于 HLTV 或 Valve。公开资料不提供本产品的技能及格线。

## 本次交互与指标更新

- [GameTracking-CS2 weapons.vdata](https://github.com/SteamTracking/GameTracking-CS2/blob/master/game/csgo/pak01_dir/scripts/weapons.vdata)：直接提取 34 种枪械的最大移动速度/武器类别/自动射击标志；读取 blob SHA `a7d1de2127d11aa51d5ac4052a96a7ad99b26dba`，来源随配置打包。该快照未证明匹配 demo 补丁 14188。
- [Leetify Stats Glossary](https://leetify.com/blog/leetify-stats-glossary/amp/)：34% 作为参考统计规则；本产品的武器范围、是否可见与姿态条件不同，不宣称复刻 Leetify。
- [demoparser README](https://github.com/LaihoE/demoparser)：FIRE / usercmd_buttonstate_1 字段参考；先对本 demo 探针，再抽取实际数据。不把字段存在等同语义/时序完全验证。
- [解析器 issue #340](https://github.com/LaihoE/demoparser/issues/340)：不同来源 demo 的命令编码曾产生缺失/陈旧字段问题，因此保留 unknown 和双字段一致性检查；它不是当前每个 demo 都出错的证据。
