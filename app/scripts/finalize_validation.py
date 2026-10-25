import sys,json,math
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.core.contracts import metric_validator,evidence_validator
from backend.core.registry import discover

jid=sys.argv[1];c=httpx.Client(base_url='http://127.0.0.1:8765',timeout=120,trust_env=False)
r=c.get(f'/api/jobs/{jid}/export/json');r.raise_for_status();result=r.json()
modules=discover();check={'job_id':jid,'all_modules_schema_valid':True,'metric_count':0,'evidence_count':0}
for mid,m in result['modules'].items():
 assert m['status'] in ('partial','succeeded')
 for x in m['metrics']:
  metric_validator.validate(x);assert x['metric_id'] in modules[mid]['metric_ids'];check['metric_count']+=1
 for e in m['evidence']:evidence_validator.validate(e);check['evidence_count']+=1
assert all(m['unit']=='kills/death' for m in result['modules']['basic_stats']['metrics'] if m['metric_id']=='kd')
for mid in ['role_analysis','positioning_analysis','utility_analysis']:
 folder=ROOT/'backend/modules'/mid
 assert (folder/'README.md').stat().st_size==0 and (folder/'analyzer.py').stat().st_size==0
 assert not modules[mid]['enabled'] and not modules[mid]['description'] and not modules[mid]['metric_ids']
assert not result['capabilities']['aim_punch_angle']['column_present']
assert result['capabilities']['native_velocity']['measured_alignment']['previous_interval_mean_L1_error']<.001
assert all(isinstance(p['player_id'],str) for p in result['players'])
check['performance']=result['performance'];check['capabilities']=result['capabilities']['native_velocity'];check['all_planned_business_files_empty']=True
(ROOT/'docs/final_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
integration=json.loads((ROOT/'docs/integration.json').read_text(encoding='utf-8'));integration['final_delivery_job_id']=jid
(ROOT/'docs/integration.json').write_text(json.dumps(integration,ensure_ascii=False,indent=2),encoding='utf-8')
html=c.get(f'/api/jobs/{jid}/export/html');html.raise_for_status();(ROOT/'docs/sample-report.html').write_bytes(html.content)
perf=integration['performance'];cached=integration['cached_performance'];recompute=integration['parameter_recompute_performance'];storage=c.get('/api/storage').json()
audit=json.loads((ROOT/'docs/event_audit.json').read_text(encoding='utf-8'))
text=f'''# 验收记录 · 2026-10-23

## 实物与运行

- 原文件：`2398717_8244_2.dem`，295,296,092 字节，PBDEMS2。
- SHA256：`{result['demo']['demo_hash']}`。
- 实际 parser：demoparser2 0.42.0；地图 de_anubis，patch 14188。
- FileInfo：2432.84375 秒 / 155702 播放 tick；实测相邻状态间隔 0.015625 秒，game_time 起点 901 秒。
- 1,557,020 条高频玩家状态；10 名玩家，20 个完整正式回合；Team Falcons 13 : 7 TYLOO。
- 原始事件：player_death 132，player_hurt 504，weapon_fire 2276。产品不含这些固定值，断言只在集成验收脚本。
- 最终结果任务：`{jid}`；[打开此结果](http://127.0.0.1:8765/?job={jid})。

## 自动化与实测

| 检查 | 结果 |
|---|---|
| 合成算法/边界/模块/API 测试 | 78 passed；1 条 Starlette 测试客户端 httpx 接口弃用提示，不影响运行 |
| TypeScript + Vite 生产构建 | 通过；静态入口与后端同一 8765 端口 |
| 所有真实 MetricResult / Evidence schema | {check['metric_count']} 个指标、{check['evidence_count']} 条证据逐项验证通过 |
| 原始文件首次完整冷计算 | {perf['wall_seconds']:.2f} 秒；工作进程峰值采样 RSS {perf['peak_sampled_worker_rss_bytes']/1024**2:.1f} MiB |
| 完整事实/特征磁盘占用 | {perf['facts_bytes']/1024**2:.2f} MiB（不含原始 281.62 MiB 副本和结果） |
| 相同配置重复任务 | {cached['wall_seconds']:.3f} 秒；事实与所有模块缓存命中 |
| 仅停步阈值倍率改变 | {recompute['wall_seconds']:.2f} 秒；事实及其他三个模块命中缓存 |
| 高频抽取阶段取消 | {integration['cancel_seconds']:.2f} 秒；合作式取消；未发布不完整缓存 |
| 多文件批次 | 人工截断容器失败；真实 demo 与重复文件继续完成 |
| 去重与汇总 | 上传复用相同哈希副本；批量汇总只计 1 个不同 demo |
| 导出 | JSON / CSV / 离线 HTML 均经 HTTP 实际下载验证 |
| 启停 | start.ps1、stop.ps1 实际执行；服务停止后可重新启动 |

RSS 每50ms采样，并非操作系统严格峰值；包含同一工作进程内 Rust parser/Pandas/Arrow，未包含浏览器和 API 主进程。任务计时不含浏览器上传。浏览器视图分页不影响算法输入。只实测默认并发1，配置并发2及同哈希文件锁已有实现但未做压力测试。

本地 data 当前总量（包含开发阶段历史缓存与多个结果）：{sum(storage['groups'].values())/1024**2:.1f} MiB。当前单次事实存储及原始副本大小如上；历史任务不是新的比赛样本。

## 独立复核

独立脚本直接调用 parser 重新取三个死亡窗口（tick 2909 / 4041 / 4407，具体以 event_audit.json 实值为准），不调用生产统计模块。首杀为 Jee 用 glock 爆头 TeSeS；事件附加 user_health=100，但结束状态 health=0/is_alive=false。事件附加状态不能当 tick 末或开枪前状态。

独立正式回合窗口过滤得到 **{audit['sum_kills']} 次对敌击杀**：132 条原始死亡中，{audit['out_of_live_deaths']} 条在正式回合窗口外，{audit['in_live_non_enemy_deaths']} 条是正式窗口内非对敌死亡。旧输出是原始事件计数，产品统计有公开过滤规则，不能强迫二者相同。

另对6个开枪区间重新用坐标和 dt 计算速度、6个头线窗口独立计算目标仰角；全部与保存证据一致。全部生产 recoil 曲线的 effective_recoil/residual 保持 NULL。速度 alias 对齐探针：当前区间平均 L1 误差约11.32 units/s，前一区间误差接近0；因此正式算法不使用它作为当前原生速度。该复核仍共享 demoparser2 底层，未宣称第二套独立协议解码器验证。

## 能力分类与剩余限制

| 分类 | 已交付范围 / 下一步 |
|---|---|
| 已实现且验证 | 原始上传/哈希去重/容器索引/高频分区/队列取消/缓存重算；20回合基础统计和证据链；真实事件窗口、数据检查器、导出；通用模块发现与契约 |
| 已实现但待校准 | 头眼高近似、头部半径、候选窗口；各武器速度阈值/恢复间隔/运动滞回。需要匹配补丁的受控实验数据校准 |
| 数据限制降级 | 无地图碰撞/烟雾可见性、动画头骨、原生 subtick 开枪前状态、已解释有效 recoil；头线只为估计，停步只为区间速度代理，压枪只描述弹序/视角。补齐对应地图/几何/预测或有效 punch 语义后才能提高层级 |
| 仅预留 | role_analysis / positioning_analysis / utility_analysis：禁用 manifest、空参数/业务 schema、空 README 和 analyzer；未实现任何业务评分 |

未完成：多地图/多补丁真实兼容性验证、机器人接管身份重建、可靠换目标检测、TrueView 客户端预测重跑、原始鼠标或反向键证据、实际弹道散布、职业/同段位基线、跨场分位数合并图。所有这些都没有用假数据填补。

回合/阵营/武器/姿态/距离/判定筛选在已有该范围的指标和证据上工作；证据筛选不会偷偷重算顶部全场分母。当前没有任意组合过滤后的实时重新聚合功能。参数编辑可发起明确版本的重算。

完整机器记录：`integration.json`、`event_audit.json`、`final_check.json`、`test-results.txt`；可离线打开 `sample-report.html`。算法说明和来源见 ALGORITHMS.md / SOURCES.md。
'''
# Avoid hardcoding the third event tick in the narrative.
ticks=' / '.join(str(x['tick']) for x in audit['death_windows'])
text=text.replace('2909 / 4041 / 4407',ticks)
(ROOT/'docs/VALIDATION.md').write_text(text,encoding='utf-8')
print(json.dumps(check,ensure_ascii=False))
