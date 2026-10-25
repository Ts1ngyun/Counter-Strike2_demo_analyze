"""Fact-based review candidates. Priority is a queue heuristic, never a skill score."""
import json
import math
from collections import defaultdict
from ...core.common import check_cancel, clean, metric
from ..stop_shooting.analyzer import classify_speed
from ..basic_stats.analyzer import enemy

MID = 'combat_review'
UTILITY = {'flashbang', 'smokegrenade', 'hegrenade', 'molotov', 'incgrenade', 'decoy'}


def snapshot(row):
    if not row: return None
    return {k: row.get(k) for k in ('tick', 'player_id', 'health', 'armor_value', 'active_weapon_name',
             'active_weapon_ammo', 'is_reloading', 'is_alive', 'team_num', 'X', 'Y', 'Z', 'pitch', 'yaw', 'flash_duration')}


def distance(a, b):
    if not a or not b or any(not isinstance(s.get(k), (int, float)) for s in (a, b) for k in ('X', 'Y', 'Z')): return None
    return math.sqrt(sum((a[k]-b[k])**2 for k in ('X', 'Y', 'Z')))


def first_shot_status(shot, margin=5):
    if not shot: return {'status': 'no_shot'}
    a, b = json.loads(shot['pre_json']), json.loads(shot['end_json'])
    profile = json.loads(shot['profile_json'])
    threshold = profile.get('threshold') if profile else None
    if not a or not b or json.loads(shot.get('unknown_reasons') or '[]'):
        status = 'unknown'
    elif a.get('is_airborne') is not False or b.get('is_airborne') is not False:
        status = 'airborne_or_unknown'
    else: status = classify_speed(a.get('speed_xy'), b.get('speed_xy'), threshold, margin)
    return {'status': status, 'tick': shot['tick'], 'shot_id': shot['shot_id'], 'threshold': threshold,
            'pre_speed': a.get('speed_xy') if a else None, 'end_speed': b.get('speed_xy') if b else None,
            'limitation': '本片段首枪的相邻区间地速；不是移动后首枪资格，也不是准确率'}


def trade_after(death, events, dt, seconds):
    """Strictly later enemy kill; equal-tick order is unavailable."""
    candidates = [e for e in events if e.get('event_name') == 'player_death' and enemy(e)
        and death['tick'] < e['tick'] <= death['tick'] + seconds/dt
        and e.get('user_steamid') == death.get('attacker_steamid')
        and e.get('attacker_team_num') == death.get('user_team_num')]
    if not candidates: return None
    e = min(candidates, key=lambda x: (x['tick'], x['event_id']))
    return {'event_id': e['event_id'], 'tick': e['tick'], 'player_id': e['attacker_steamid'],
            'seconds': (e['tick']-death['tick'])*dt, 'rule_window_seconds': seconds}


def build_card(pid, start, end, anchor, death, events, shots, state_at, dt, provider, rid, params):
    ownshots = [s for s in shots if s['player_id'] == pid and start <= s['tick'] <= anchor and s.get('is_gun')]
    relevant = [e for e in events if start <= e['tick'] <= end and
        (e.get('user_steamid') == pid or e.get('attacker_steamid') == pid or e.get('player_id') == pid)
        and e.get('event_name') in ('weapon_fire', 'player_hurt', 'player_death', 'player_blind', 'weapon_reload')]
    hurts = [e for e in relevant if e['event_name'] == 'player_hurt']
    attackers = sorted({e['attacker_steamid'] for e in hurts if e.get('user_steamid') == pid and enemy(e)})
    targets = sorted({e['user_steamid'] for e in hurts if e.get('attacker_steamid') == pid and enemy(e)})
    target = death.get('attacker_steamid') if death else (targets[0] if len(targets) == 1 else None)
    before = state_at.get((pid, anchor-1))
    other = state_at.get((target, anchor-1)) if target else None
    tags = []; unknown = []
    if death:
        if before and before.get('is_alive') is True:
            if before.get('is_reloading') is True: tags.append({'code': 'reload_death', 'label': '死亡前相邻采样正在换弹', 'weight': 3})
            if provider.normalize(before.get('active_weapon_name')) in UTILITY:
                tags.append({'code': 'utility_death', 'label': '死亡前相邻采样手持道具', 'weight': 3})
        else: unknown.append('缺少死亡前一 tick 存活状态；持有物/换弹不判定')
    if len(attackers) >= 2: tags.append({'code': 'multiple_attackers', 'label': f'片段内受到 {len(attackers)} 名敌人伤害', 'weight': 2})
    first = first_shot_status(ownshots[0] if ownshots else None, params['speed_margin'])
    if first['status'] == 'moving': tags.append({'code': 'moving_first_shot', 'label': '片段首枪两侧区间地速高于参考阈值', 'weight': 2})
    # Flash duration entity fields alone do not establish an active visual blind.
    blinds = [e for e in events if e.get('event_name') == 'player_blind' and e.get('user_steamid') == pid
              and start <= e['tick'] <= anchor]
    if blinds: tags.append({'code': 'blind_event', 'label': '片段内有致盲事件（不推断持续至死亡）', 'weight': 1})
    trade = trade_after(death, events, dt, params['trade_seconds']) if death and enemy(death) else None
    if trade: tags.append({'code': 'traded', 'label': f"队友在 {trade['seconds']:.2f} 秒后击杀原击杀者", 'weight': 1})
    for tag in tags: tag['quality']='estimated' if tag['code']=='moving_first_shot' else 'observed'
    timeline = [{k: e.get(k) for k in ('event_id', 'event_name', 'tick', 'player_id', 'user_steamid',
        'attacker_steamid', 'user_name', 'attacker_name', 'weapon', 'dmg_health', 'health', 'hitgroup', 'headshot', 'assistedflash')}
        for e in sorted(relevant, key=lambda e: (e['tick'], e['event_id']))]
    suffix = death['event_id'] if death else f'{pid}:{start}:{anchor}'
    return {'evidence_id': 'combat:'+suffix, 'kind': 'combat_review', 'round_id': rid, 'player_id': pid,
        'tick': start, 'end_tick': end, 'anchor_tick': anchor, 'start_time': start*dt, 'end_time': end*dt,
        'review_type': 'death' if death else 'engagement', 'judgement': 'review_candidate', 'quality': 'derived',
        'weapon': provider.normalize(before.get('active_weapon_name')) if before else None,
        'target_id': target, 'target_selection': 'killer' if death else 'unique damaged opponent' if target else 'unknown/multiple',
        'distance_units': distance(before, other), 'self_snapshot': snapshot(before), 'opponent_snapshot': snapshot(other),
        'position_start': snapshot(state_at.get((pid, start))), 'position_end': snapshot(state_at.get((pid, min(anchor-1,end)))),
        'enemy_attacker_ids': attackers, 'enemy_target_ids': targets, 'first_shot': first, 'trade': trade,
        'tags': tags, 'priority': sum(t['weight'] for t in tags), 'timeline': timeline,
        'raw_damage_dealt': sum(e.get('dmg_health') or 0 for e in hurts if e.get('attacker_steamid') == pid and enemy(e)),
        'raw_damage_taken': sum(e.get('dmg_health') or 0 for e in hurts if e.get('user_steamid') == pid),
        'reason': '；'.join(t['label'] for t in tags) or '按事件构建的复盘片段；没有自动判错',
        'unknown_reasons': unknown, 'raw_field_paths': ['player_death', 'player_hurt', 'weapon_fire', 'player_states', 'shots'],
        'limitations': ['优先级仅安排复盘顺序，不是失误或能力评分', '同 tick 的跨类型事件顺序未知',
            '未验证视线，开火片段不等于首次看到敌人', '伤害为事件原始值，可能包含溢出', '死亡前相邻状态不是精确死亡瞬间状态']}


def analyze(ctx, p, cancel, progress):
    dt = ctx.meta['tick_seconds']; evidence = []
    for r in ctx.rounds():
        if not r['complete']: continue
        check_cancel(cancel); rid = r['round_id']; progress('交战与死亡复盘', rid)
        events = clean(ctx.query('events', round_id=rid).to_dict('records'))
        events = [e for e in events if e.get('in_live_round')]
        if not events: continue
        shots = sorted(clean(ctx.query('shots', round_id=rid).to_dict('records')), key=lambda s:s['tick'])
        deaths = [e for e in events if e['event_name'] == 'player_death' and e.get('user_steamid') not in (None, '0')]
        bounds = defaultdict(list); windows=[]
        for e in deaths:
            check_cancel(cancel); pid = e['user_steamid']; t = e['tick']
            start = max(r['live_tick'], t-math.ceil(p['before_death_seconds']/dt))
            end = min(r['end_tick'], t+math.ceil(p['after_death_seconds']/dt))
            windows.append((pid,start,end,t,e))
            bounds[pid].append((start, end))
        # Separate shooting/damage episodes outside death windows; targets remain unknown without hurt events.
        anchors = defaultdict(set)
        for s in shots:
            if s.get('is_gun') and r['live_tick'] <= s['tick'] <= r['end_tick']: anchors[s['player_id']].add(s['tick'])
        for e in events:
            if e['event_name'] == 'player_hurt' and enemy(e):
                for pid in (e['user_steamid'], e['attacker_steamid']): anchors[pid].add(e['tick'])
        for pid, ticks in anchors.items():
            groups=[]
            for t in sorted(ticks):
                if any(a <= t <= b for a,b in bounds[pid]): continue
                if not groups or t-groups[-1][-1] > p['engagement_gap_seconds']/dt or t-groups[-1][0] > 10/dt: groups.append([])
                groups[-1].append(t)
            for ts in groups:
                check_cancel(cancel)
                start=max(r['live_tick'],ts[0]-math.ceil(.5/dt)); end=min(r['end_tick'],ts[-1]+math.ceil(.5/dt))
                windows.append((pid,start,end,ts[-1],None))
        # Only materialize snapshots actually referenced by a card, not every round tick into Python dictionaries.
        ticks={t for _,start,_,anchor,_ in windows for t in (start,anchor-1)}
        frame=ctx.query('player_states',round_id=rid)
        states=clean(frame[frame.tick.isin(ticks)].to_dict('records')) if not frame.empty else []
        state_at={(s['player_id'],s['tick']):s for s in states}
        for pid,start,end,anchor,death in windows:
            check_cancel(cancel)
            evidence.append(build_card(pid,start,end,anchor,death,events,shots,state_at,dt,ctx.providers.weapons,rid,p))
    evidence.sort(key=lambda e: (-e['priority'], e['round_id'], e['anchor_tick'], e['player_id']))
    groups=defaultdict(list)
    for e in evidence: groups[e['player_id']].append(e)
    metrics=[]
    for pid, rows in groups.items():
        for mid, predicate in [('review_clips',lambda e:True),('death_clips',lambda e:e['review_type']=='death'),
                ('flagged_clips',lambda e:bool(e['tags']))]:
            chosen=[e for e in rows if predicate(e)]
            metrics.append(metric(MID,mid,len(chosen),{'player_id':pid},eligible=len(rows),evidence=[e['evidence_id'] for e in chosen],sample_unit='clip',
                method='完整回合中的事件复盘片段；标签不是失误判定',limitations=['片段可能重叠，不能把数量解释为独立交战次数']))
    return {'status':'succeeded','metrics':metrics,'evidence':evidence,'details':{'notes':['默认按可解释的复盘优先级排序。','换弹、手持道具、多名伤害来源等均是情形标签，不自动判错。','前 10 条为本场优先复盘建议；可以人工标注问题、合理选择或不确定。'],
        'recommended_evidence_ids':[e['evidence_id'] for e in evidence[:10]], 'priority_rule':'reload=3, utility=3, multiple attackers=2, moving first shot=2, blind event=1, trade=1'}}
