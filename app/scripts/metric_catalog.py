from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]/'backend/modules'
definitions={
'kills':('对敌击杀','正式阶段内击杀不同阵营且非自己的玩家次数','count'),
'deaths':('死亡','正式阶段内参与玩家死亡次数；队杀/自杀不计入对敌击杀但计死亡','count'),
'assists':('游戏内助攻','player_death.assister_steamid 的游戏事件事实','count'),
'flash_assists':('闪光助攻','游戏内助攻且 assistedflash=true','count'),
'kd':('K/D','对敌击杀 / 死亡；死亡为零时 NULL','kills/death'),
'kpr':('每回合击杀','对敌击杀 / 参与完整正式回合数','per_round'),
'dpr':('每回合死亡','死亡 / 参与完整正式回合数','per_round'),
'hs_kills':('爆头击杀','对敌 player_death.headshot=true 次数','count'),
'hs_kill_pct':('HS-kill%','对敌爆头击杀 / 对敌总击杀；显示时乘 100%','ratio'),
'adr_effective':('已验证有效 ADR','验证封顶生命伤害之和 / 参与回合；任一伤害事件未知则 NULL','hp/round'),
'adr_raw':('原始生命伤害 / 回合','对敌 dmg_health 之和 / 参与回合；未保证过量伤害封顶','hp/round'),
'participated_rounds':('参与回合','在 freeze_end 存活、T/CT、非零 SteamID 的完整正式回合','count'),
'survival_rate':('存活回合占比','回合末存活且该回合没有死亡事件 / 参与回合','ratio'),
'kast_local':('KAST_local','有击杀 OR 游戏助攻 OR 存活 OR 死后配置窗内队友击杀原击杀者的回合 / 参与回合','ratio'),
'opening_kills':('首杀','回合第一笔对敌击杀；同 tick 多笔时不认定唯一首杀','count'),
'opening_deaths':('首死','回合第一笔对敌死亡；同 tick 多笔时不认定唯一首死','count'),
'opening_difference':('开局击杀差','首杀数 - 首死数','count'),
'head_hurt_event_share':('头部受伤事件占比','对敌 hitgroup=head 受伤事件 / 对敌受伤事件数；不是命中子弹占比','ratio'),
'head_hurt_events_per_fire':('头部受伤事件 / 开火','对敌头部 hurt 事件数 / 开火事件数；可有多弹丸、多目标，不是精确命中率','events/fire'),
'grenade_damage_raw':('投掷物原始对敌伤害','hegrenade/inferno/molotov/incgrenade 对敌原始生命伤害之和；不构成道具评价模块','hp'),
'raw_damage':('原始生命伤害','武器分组下对敌原始 dmg_health 之和','hp'),
'head_in_band_time':('估计头线范围内时间','sum(dt where abs(e_vertical)<=atan2(radius,distance)) / sum(可评价 dt)','ratio'),
'head_high_time':('估计偏高时间占比','sum(dt where e_vertical>容差) / sum(可评价 dt)','ratio'),
'head_low_time':('估计偏低时间占比','sum(dt where e_vertical<-容差) / sum(可评价 dt)','ratio'),
'head_abs_error_p50':('绝对高度角误差 P50','按 dt 加权的 abs(-pitch-atan2(H.z-E.z,distance)) 中位数','degrees'),
'head_abs_error_p90':('绝对高度角误差 P90','按 dt 加权的绝对高度角误差 90 分位','degrees'),
'verified_head_in_band_time':('验证头线时间占比','只有验证可见性和头部几何时才计算；当前 NULL','ratio'),
'unconditional_preaim':('无目标通用预瞄','需要地图预期交战点锚点；当前 NULL','ratio'),
'shot_stationary_ready_rate':('开枪低速就绪代理','两个相邻位置区间平均地速均低于武器实验阈值-模糊带的枪 / 全部可判定枪','ratio'),
'movement_to_first_shot_ready_rate':('移动后首枪就绪代理','合格运动段后第一枪中低速就绪的枪 / 可判定的合格移动后首枪','ratio'),
'reverse_input_evidence':('反向输入证据','无验证网络输入语义；当前 NULL，不从速度方向反推按键','count'),
'descriptive_sequences':('可描述射击序列','满足最小弹数且未受伤/姿态大变/状态缺失的射击序列数','count'),
'view_pitch_delta_p50':('视角 pitch 变化 P50','按序列统计 wrap(pitch_last-pitch_first) 中位数；不是压枪得分','degrees'),
'compensation_residual_rms':('后坐力补偿残差 RMS','只有有效 P、验证 V 与跟枪 T 语义后用 wrap(ΔV+ΔP-ΔT)；当前 NULL','degrees'),
'actual_impact_dispersion':('真实落点散布','需要验证射线/落点事件；当前 NULL','degrees')}
for folder in ROOT.iterdir():
 if not (folder/'module.yaml').exists():continue
 m=json.loads((folder/'module.yaml').read_text(encoding='utf-8'))
 if not m['enabled']:continue
 catalog={}
 for mid in set(m['metric_ids']+(['raw_damage'] if m['id']=='basic_stats' else [])):
  title,formula,unit=definitions[mid]
  catalog[mid]={'title':title,'definition':formula,'formula':formula,'unit':unit,'sample_unit':'round/event' if m['id']=='basic_stats' else 'second' if m['id']=='head_line' else 'shot' if m['id']=='stop_shooting' else 'sequence','numerator_denominator':'每个结果携带 numerator/denominator；非比率则为 null；ADR 伤害覆盖率以事件为分母，ADR 数值以回合为分母','inclusion':'完整正式回合 + 模块对应已知能力；见 ALGORITHMS.md','exclusion':'热身、重开、回合结束后、不完整回合；另见证据 reason','field_dependencies':m['requires']['tables'],'time_requirements':'事件 tick 与相邻高频状态分离；无 subtick，原生分辨率在结果中保存','parameters':json.loads((folder/'defaults.yaml').read_text(encoding='utf-8')),'source':'本产品实验定义 v1；HS-kill% 参考 HLTV 2015-08-15' if mid=='hs_kill_pct' else '本产品公开计算规则 v1','limitations':'NULL 不等于零；代理量不等于技能/精准；无官方综合分或职业基线','algorithm_version':m['version'],'evidence_entry':'GET /api/jobs/{job_id}/evidence/'+m['id']+'?metric_id='+mid}
 (folder/'metrics.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
