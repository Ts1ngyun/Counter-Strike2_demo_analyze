/* Single source of truth for beginner-facing metric wording.
   Every metric gets: a plain name, one sentence, an example, and what it
   cannot tell you. Calculation details come from the backend metric
   definition so formulas never drift between pages. */

export type MetricCopy = {
  name: string;
  oneLine: string;
  example?: string;
  cannot?: string;
  detail?: string;
};

export const METRICS: Record<string, MetricCopy> = {
  kills: {
    name: '对敌击杀',
    oneLine: '击杀敌人的次数。',
    example: '一场里显示 13，表示你有 13 次对敌人的最后一击；同一敌人被队友补掉不会重复算给你。',
    cannot: '击杀多不代表赢下的回合多，也不能单独说明枪法或决策水平。',
  },
  deaths: {
    name: '死亡次数',
    oneLine: '阵亡次数。',
    example: '显示 11，表示 11 个计入统计的回合里你被击杀；回合结束后才阵亡通常不算。',
    cannot: '死亡少不一定是打得好，也可能是一直没有参与交火。',
  },
  assists: {
    name: '助攻',
    oneLine: '你打伤了敌人，但最后一击由队友完成。',
    example: '你对敌人造成伤害，随后队友击杀了他，这一回合记为一次助攻。',
    cannot: '助攻依赖游戏事件的判定，不能还原你实际提供了多少信息或压力。',
  },
  flash_assists: {
    name: '闪光助攻',
    oneLine: '你投出的闪光让队友完成击杀，并被游戏记录为闪助。',
    example: '你扔出闪光致盲敌人，队友在致盲期间完成击杀，记 1 次。',
    cannot: '没有记录闪助不代表闪光没起作用；它只统计游戏明确写下的关系。',
  },
  hs_kills: {
    name: '爆头击杀',
    oneLine: '以爆头完成的击杀次数。',
    example: '一次击杀的致死伤害来自头部，就计入这里；先打身体再补头也只算一次爆头击杀。',
    cannot: '爆头多不等于枪法好，也可能与武器、距离和对手站位有关。',
  },
  hs_kill_pct: {
    name: '爆头率',
    oneLine: '爆头击杀 ÷ 总击杀。',
    example: '10 次击杀、4 次爆头，爆头率为 40%。无击杀时不计算。',
    cannot: '只统计致死一击，不是子弹命中率。',
  },
  participated_rounds: {
    name: '参与计算的回合',
    oneLine: '这一场有多少个完整正式回合进入了你的统计。',
    example: '显示 20，表示 20 个计入比分且数据完整的回合参与了计算。',
    cannot: '它不是服务器总回合数；热身、重开、不完整或未计分回合会被排除。',
  },
  opening_kills: {
    name: '首杀',
    oneLine: '每回合第一个击杀由你完成的次数。',
    example: '一个回合里你最先击杀敌人，记 1 次首杀；之后你再击杀多人也不会重复计入首杀。',
    cannot: '首杀多不等于开局一定占优，还要看是否被换掉、队伍是否利用了这个优势。',
  },
  opening_deaths: {
    name: '首死',
    oneLine: '每回合第一个阵亡的人是你，记一次首死。',
    example: '双方交火时你最先被击杀，这一回合记 1 次首死。',
    cannot: '首死不等于失误；你可能是在为队友拿信息或掩护下包。',
  },
  opening_difference: {
    name: '开局击杀差',
    oneLine: '首杀数减去首死数，用来粗略看开局的人数交换。',
    example: '首杀 5、首死 2，差值为 +3；负值表示首死多于首杀。',
    cannot: '这是本工具定义的简单差值，不是官方 Rating，也不衡量首杀质量。',
  },
  grenade_damage_raw: {
    name: '投掷物原始伤害',
    oneLine: '手雷、燃烧瓶等投掷物对敌人造成的记录伤害总和。',
    example: '一颗手雷对两名敌人合计记录 60 点伤害，就累加 60。',
    cannot: '原始伤害可能超过敌人剩余生命，也不等于实际削掉的有效生命。',
  },
  kd: {
    name: 'K/D',
    oneLine: '击杀数除以死亡数。',
    example: '击杀 12、死亡 6，K/D 就是 2.0；死亡为 0 时显示“无法计算”，不会显示无穷大。',
    cannot: 'K/D 不反映助攻、伤害、首杀或回合胜负，不能单独评价整体表现。',
  },
  kpr: {
    name: 'KPR',
    oneLine: '平均每回合击杀数。',
    example: '20 个回合共击杀 16 人，每回合击杀为 0.8。',
    cannot: '它是平均值，不能说明击杀发生在关键回合还是垃圾时间。',
  },
  dpr: {
    name: 'DPR',
    oneLine: '平均每回合死亡数。',
    example: '20 个回合计阵亡 11 次，每回合死亡为 0.55。',
    cannot: '死亡少也可能意味着回避交火，需要和参与度一起看。',
  },
  survival_rate: {
    name: '存活回合占比',
    oneLine: '计入统计的回合里，你活到回合结束的比例。',
    example: '20 个回合里活下来 7 次，占比 35%。',
    cannot: '存活不等于贡献；无意义地保枪也可能让队伍少一个人。',
  },
  kast_local: {
    name: 'KAST',
    oneLine: '击杀、助攻、存活或被补枪的回合占比。',
    example: '20 个回合中，有 15 个回合满足以上任意一条，占比 75%；补枪时限使用当前分析参数。',
    cannot: '它是本工具自己的规则，不保证与 HLTV 的 KAST 完全一致；也不衡量贡献大小。',
  },
  adr_raw: {
    name: '每回合原始伤害',
    oneLine: '平均每回合造成多少记录伤害。',
    example: '整场记录伤害 1600、20 个回合，原始 ADR 为 80。',
    cannot: '可能包含超出敌人剩余生命的溢出伤害，不等于 HLTV ADR，也不能说明伤害是否有效。',
  },
  adr_effective: {
    name: '每回合有效伤害',
    oneLine: '只统计能由生命值变化核实的伤害，再看每回合平均。',
    example: '某回合记录 90 点伤害，但只有 70 点能由生命变化核实，就按 70 计入。',
    cannot: '当部分伤害无法核实时，这一项会暂不计算而不是按 0 处理；它仍不等于 HLTV ADR。',
  },
  raw_damage: {
    name: '原始伤害总量',
    oneLine: '整场记录到的原始伤害总和。',
    example: '整场对敌人记录 1600 点伤害，就显示 1600。',
    cannot: '总量受回合数影响，不能直接跨场比较；也可能包含溢出伤害。',
  },
  head_hurt_event_share: {
    name: '头部受伤事件占比',
    oneLine: '你造成的伤害事件里，落在头部的比例。',
    example: '你造成 10 次伤害事件，其中 3 次命中头部，占比 30%。',
    cannot: '这是事件比例，不是爆头率，也不代表每一枪的命中质量。',
  },
  head_hurt_events_per_fire: {
    name: '每次开火的头部受伤事件',
    oneLine: '平均每次开火对应多少次头部受伤事件。',
    example: '开火 100 次，记录到 12 次头部受伤事件，平均 0.12。',
    cannot: '它不是爆头率；一次开火可能对应多次伤害事件或没有伤害。',
  },
  kill_pitch_span_p50: {
    name: '击杀前上下调整幅度（中位数）',
    oneLine: '击杀前一小段时间里，视角上下移动了多少。',
    example: '一次击杀前视角从 -3° 移到 +2°，上下幅度约 5°；所有可计算窗口取中位数。',
    cannot: '数值小不代表瞄得准：敌人可能在移动、在高处或低处，也可能你根本没看到人。',
  },
  kill_pitch_range_p50: {
    name: '击杀前上下活动范围（中位数）',
    oneLine: '击杀前窗口内视角上下活动范围的中位数。',
    example: '窗口内最高 4°、最低 -2°，范围是 6°。',
    cannot: '它只描述视角移动，不判断移动是否合理，也不等于预瞄正确。',
  },
  eligible_kill_windows: {
    name: '可用击杀窗口数',
    oneLine: '有多少次击杀拥有足够采样，能进入瞄准变化计算。',
    example: '一场 15 次击杀，其中 9 次采样足够，这里显示 9。',
    cannot: '数量少时中位数不稳定；不能用它评价没被计入的击杀。',
  },
  death_pitch_span_p50: {
    name: '死亡前上下调整幅度（中位数）',
    oneLine: '阵亡前一小段时间里，视角上下移动幅度的中位数。',
    example: '死亡前 300 毫秒内视角上下移动约 8°，就计入这个窗口。',
    cannot: '死亡前的视角变化可能是找人、被闪光影响或正常架枪，不能直接判为失误。',
  },
  death_pitch_range_p50: {
    name: '死亡前上下活动范围（中位数）',
    oneLine: '阵亡前窗口内视角上下活动范围的中位数。',
    example: '窗口内最高 10°、最低 2°，范围 8°。',
    cannot: '只说明上下移动了多少，不说明你是否看到了威胁。',
  },
  death_windows: {
    name: '可用死亡窗口数',
    oneLine: '有多少次死亡拥有足够采样进入计算。',
    example: '一场死亡 11 次，其中 7 次窗口可用，这里显示 7。',
    cannot: '窗口少时指标波动大，不能据此评价全部死亡。',
  },
  nonkill_pitch_span_p50: {
    name: '未击杀交战上下调整幅度（中位数）',
    oneLine: '没有产生击杀的交战窗口里，视角上下移动幅度的中位数。',
    example: '一次对枪后双方都没死，窗口内上下移动 4°，计入这个指标。',
    cannot: '它不区分主动拉枪、架点还是被动挨打，也不能说明是否应该开枪。',
  },
  nonkill_pitch_range_p50: {
    name: '未击杀交战上下活动范围（中位数）',
    oneLine: '没有产生击杀的交战窗口内，视角上下活动范围的中位数。',
    example: '窗口内最高 6°、最低 -1°，范围 7°。',
    cannot: '数值小不等于瞄得稳，敌人在不同高度也会造成变化。',
  },
  nonkill_windows: {
    name: '可用未击杀窗口数',
    oneLine: '有多少次未产生击杀的交战拥有足够采样。',
    example: '一场记录 12 次这类交战，其中 8 次可计算，这里显示 8。',
    cannot: '数量少时中位数不稳定；不代表所有交战都被识别。',
  },
  head_in_band_time: {
    name: '估计头线范围内时间',
    oneLine: '实验估计：准星停留在“推测头部高度带”内的时间比例。',
    example: '一个窗口 1 秒里有 0.4 秒落在估计高度带内，比例是 40%。',
    cannot: '这是几何估计，不是命中率；头位由身体姿态和参数估算，敌人移动、蹲起都会影响。',
  },
  head_high_time: {
    name: '估计偏高时间',
    oneLine: '实验估计：准星高于推测头部高度带的时间比例。',
    example: '一个窗口里 30% 的采样高于估计头带，就记 30%。',
    cannot: '偏高不等于瞄错，也可能敌人在低处或你正在转移目标。',
  },
  head_low_time: {
    name: '估计偏低时间',
    oneLine: '实验估计：准星低于推测头部高度带的时间比例。',
    example: '一个窗口里 20% 的采样低于估计头带，就记 20%。',
    cannot: '偏低不等于失误，蹲伏敌人、地形高度和估计误差都会影响。',
  },
  head_abs_error_p50: {
    name: '头部高度估计误差（中位数）',
    oneLine: '实验估计：准星与推测头位之间的高度角误差中位数。',
    example: '多个采样误差为 1.2°、2.0°、3.1°，中位数是 2.0°。',
    cannot: '它是估计误差，不是实际弹着点误差；不能据此断言命中或未命中。',
  },
  head_abs_error_p90: {
    name: '头部高度估计误差（90% 分位）',
    oneLine: '实验估计：90% 的采样误差低于这个角度。',
    example: 'P90 为 5°，表示大多数采样误差在 5° 以内，但仍有更大的误差。',
    cannot: 'P90 不能说明误差方向，也不等于最差情况或命中率。',
  },
  verified_head_in_band_time: {
    name: '已验证头线时间占比',
    oneLine: '只保留能由更可靠几何条件验证的采样后，准星在头带内的时间比例。',
    example: '100 个采样中 55 个通过验证，其中 30 个落在头带内，占比约 55%。',
    cannot: '验证只针对几何条件，不代表对手真实屏幕或命中判定。',
  },
  unconditional_preaim: {
    name: '无目标通用预瞄',
    oneLine: '没有明确目标时，准星高度是否落在常见头线附近。',
    example: '在无人可见的采样里，多数时间准星处于设定的头线高度带。',
    cannot: '这是实验性描述，不了解你的意图；也可能只是站在默认架点。',
  },
  movement_to_first_shot_ready_rate: {
    name: '移动后首枪达标率',
    oneLine: '移动后第一次开枪时，有多少次速度已经降到所持武器的参考范围。',
    example: '20 次移动后首枪，其中 15 次开枪时速度足够低，达标率 75%。',
    cannot: '不能据此断言你按了反向键，也不保证子弹一定命中；只描述开枪瞬间的速度状态。',
  },
  shot_stationary_ready_rate: {
    name: '开枪低速达标率',
    oneLine: '统计到的所有开枪里，有多少次移动速度已经足够低。',
    example: '100 次开枪里 84 次速度低于参考阈值，达标率 84%。',
    cannot: '和“移动后首枪”口径不同；它不评价是否该停、是否该开枪。',
  },
  reverse_input_evidence: {
    name: '反向输入证据',
    oneLine: '录像中观察到的反向按键与减速关系；多数演示录像无法可靠提供。',
    example: '只有按键序列与速度变化能相互印证时才给出，否则保持未知。',
    cannot: '显示不可用不代表没有急停；不能把缺失当成“没有操作”。',
  },
  descriptive_sequences: {
    name: '可描述射击序列',
    oneLine: '满足最少弹数、可用于描述连续射击的片段数量。',
    example: '一场里有 11 段连开至少 4 发的射击，显示 11。',
    cannot: '片段数量不等于压枪水平；短点射可能因为弹数不足而不计入。',
  },
  view_pitch_delta_p50: {
    name: '连续射击视角上下变化（中位数）',
    oneLine: '连续射击期间，视角上下移动幅度的中位数。',
    example: '多段连射的上下变化为 3°、5°、6°，中位数为 5°。',
    cannot: '这是视角移动，不是后坐力补偿好坏，也不代表子弹落点。',
  },
  compensation_residual_rms: {
    name: '后坐力补偿残差（均方根）',
    oneLine: '视角移动与理论后坐力轨迹之间的偏差，数值越小表示越接近。',
    example: '仅在原始后坐力数据可验证时计算，残差按均方根汇总。',
    cannot: '当前许多录像无法验证原始后坐力，显示不可用；不要理解成“零误差”。',
  },
  actual_impact_dispersion: {
    name: '实际落点散布',
    oneLine: '连续射击时子弹实际落点的分散程度。',
    example: '需要可靠弹着点才能计算；不同距离不能直接比较。',
    cannot: '数据不足时显示不可用，不会用 0 代替；也不等于压枪评分。',
  },
  flash_detonations: {
    name: '闪光引爆次数',
    oneLine: '你投出的闪光在回合内引爆的次数。',
    example: '一场里你扔出并引爆了 14 颗闪光，显示 14。',
    cannot: '引爆不等于有效；可能没影响任何人，也可能被队友挡住。',
  },
  enemy_affected_flashes: {
    name: '影响敌人的闪光次数',
    oneLine: '至少记录到一名敌人被致盲的闪光次数。',
    example: '14 颗闪光里有 5 颗记录到敌人致盲，显示 5。',
    cannot: '只统计被记录到的影响；记录缺失不代表没有效果，也不代表致盲时长。',
  },
  enemy_blind_records: {
    name: '敌方致盲记录',
    oneLine: '你的闪光造成的敌方致盲事件条数。',
    example: '一颗闪同时致盲两名敌人，会记 2 条。',
    cannot: '条数不等于人数或时长；同一颗闪可能影响多人。',
  },
  teammate_blind_records: {
    name: '队友致盲记录',
    oneLine: '你的闪光造成队友致盲的事件条数。',
    example: '一颗闪让两名队友被闪，记 2 条。',
    cannot: '记录可能不完整；它不代表队友实际屏幕完全变白。',
  },
  self_blind_records: {
    name: '自己致盲记录',
    oneLine: '你自己的闪光让自己致盲的事件条数。',
    example: '闪光反弹回来闪到自己，记 1 条。',
    cannot: '被自己闪到不一定导致失败，也不能单独说明投掷失误。',
  },
  flash_assists_recorded: {
    name: '游戏记录闪光助攻',
    oneLine: '游戏明确记录的、由你闪光帮助完成的击杀数。',
    example: '队友在致盲期间完成击杀，且游戏写明闪助，记 1 次。',
    cannot: '没有记录不代表闪光没用；只统计明确写下的关系。',
  },
  review_clips: {
    name: '可复盘片段',
    oneLine: '这一场为你筛出的、值得回看的交战片段数量。',
    example: '显示 34，表示有 34 段死亡或交火片段可供逐条复查。',
    cannot: '片段多不代表问题多；它只是方便复盘的入口。',
  },
  death_clips: {
    name: '死亡复盘片段',
    oneLine: '以你的死亡为中心整理出的片段数量。',
    example: '一场死亡 15 次，整理出 15 段死亡前回顾。',
    cannot: '片段里的标签只是情形描述，不是“你错了”的判决。',
  },
  flagged_clips: {
    name: '带情形标签的片段',
    oneLine: '带有换弹、道具、多人伤害等可解释标签的片段数。',
    example: '34 段里有 11 段出现至少一个情形标签。',
    cannot: '标签安排复盘顺序，不是失误次数，也不证明因果关系。',
  },
};

export const GLOSSARY: Record<string, MetricCopy> = {
  coverage: {
    name: '覆盖率',
    oneLine: '这次分析里，有多少符合条件的样本能可靠算出结果。',
    example: '20 个回合里有 15 个能可靠计算，覆盖率是 75%。',
    cannot: '覆盖率不是成功率，也不是表现好坏；它只说明数据够不够。',
  },
  partial: {
    name: '部分可用',
    oneLine: '已经算出的项目可以查看，另一些项目因缺少数据暂时无法判断。',
    example: '击杀和死亡可以看，有效伤害因部分伤害无法核实而暂不显示。',
    cannot: '“部分可用”不代表模块失败，也不代表未显示的项目是 0。',
  },
  excluded_round: {
    name: '未计入回合',
    oneLine: '这一回合没有让最终结算比分增加，所以不计入比赛表现。',
    example: '赛点后的练习回合、重开回合或没有改变比分的回合会被排除。',
    cannot: '被排除不等于这一回合没有发生战斗，只是不进入统计分母。',
  },
  score_unknown: {
    name: '比分未知回合',
    oneLine: '比分记录缺失或冲突，无法确认这回合算不算。',
    example: '回合结束后没有读到可靠的比分变化，就保持未知。',
    cannot: '未知不等于未计分；不能用猜测补一个结果。',
  },
  raw_score: {
    name: '录像记录的比分',
    oneLine: '录像里记录的最终队伍比分，是原始事实。',
    example: 'Team Falcons 13 : 7 TYLOO。',
    cannot: '它可能包含未计入分析的回合，不能直接和“纳入回合数”互相换算。',
  },
  evidence: {
    name: '证据',
    oneLine: '每一条结论背后的一条可复查记录：回合、玩家、时间和判定原因。',
    example: '一条证据可能写着“r004 · 时间步 8123 · 速度低于阈值”。',
    cannot: '证据能帮你复查，但单条证据不能代表整场结论。',
  },
  kast: {
    name: 'KAST',
    oneLine: '有击杀、助攻、存活或被及时补枪的回合占比。',
    example: '20 回合中有 15 回合至少满足一项，就是 75%。',
    cannot: '本工具使用自己的补枪规则，不保证与 HLTV 完全一致。',
  },
  adr: {
    name: 'ADR',
    oneLine: '平均每回合造成的伤害。',
    example: '整场 1600 伤害、20 回合，ADR 为 80。',
    cannot: '原始 ADR 可能含溢出伤害；本工具另提供“有效伤害”口径。',
  },
  unit: {
    name: '游戏距离单位',
    oneLine: 'CS2 世界坐标距离，约 1 单位等于 1.9 厘米。',
    example: '500 距离单位大约相当于 9.5 米。',
    cannot: '水平距离不包含高低差，也不等于视线可见距离。',
  },
  tick: {
    name: '时间步（tick）',
    oneLine: '游戏模拟的一小段时间步，本 demo 按实际时间换算。',
    example: '时间步相差 64 通常约等于 1 秒，但本工具使用录像实际时间步长。',
    cannot: '时间步不是玩家看到画面的精确时间，也不包含鼠标亚帧输入。',
  },
  planned: {
    name: '规划中',
    oneLine: '这个能力还没有实现，不会产生结果。',
    example: '人物定位、选位分析目前只在开发计划中。',
    cannot: '不要在复盘时把这些项目当成已完成能力。',
  },
  aim_change: {
    name: '交战瞄准变化',
    oneLine: '交战前后视角上下移动了多少，只描述移动，不判断对错。',
    example: '击杀前视角上下移动 5°，记为一次瞄准变化。',
    cannot: '敌人在高处、低处或移动都会影响它；数值小不代表一定瞄得好。',
  },
};

METRICS.round_swing = {name:'Round Swing', oneLine:'下包前击杀加分、死亡减分，按人数优势估算。', cannot:'仅人数模型：每次对枪按五五开，不含装备、地图和下包后的交战。不是 HLTV 或真实回合胜率。', example:'单位 pp 为百分点；全场值是可计算回合的平均变化。'};

export function metricName(metricId: string, definition?: any): string {
  return METRICS[metricId]?.name || definition?.title || metricId;
}

export function metricCopy(metricId: string, definition?: any): MetricCopy {
  const base = METRICS[metricId] || {
    name: definition?.title || metricId,
    oneLine: definition?.definition || '这项指标还没有面向普通用户的说明。',
    cannot: '缺少解释时不应当作结论使用。',
  };
  return {
    ...base,
    detail: base.detail || definition?.limitations || undefined,
  };
}

export function glossaryCopy(key: string): MetricCopy {
  return GLOSSARY[key] || {name: key, oneLine: '暂无说明。'};
}
