"""Kill-window vertical aim description. No head placement score is inferred."""
import math
from collections import Counter, defaultdict
import numpy as np
from ...core.common import check_cancel, clean, metric
from ..basic_stats.analyzer import enemy
from .legacy import geometry, weighted_quantile, analyze as legacy_analyze
from .context_windows import phases, analyze_context_windows

MID = 'head_line'


def finite(value):
    return isinstance(value, (float, int)) and math.isfinite(value)


def kill_exclusion(event, provider, states, events):
    """No universal shotgun lethal radius is invented from pellet count."""
    weapon = provider.normalize(event.get('weapon'))
    info = {'weapon': weapon, 'distance_units': None, 'target_pre_health': None,
            'target_pre_armor': None, 'body_one_shot_distance_units': None}
    if weapon in ('awp', 'taser'):
        return 'excluded', 'excluded_' + weapon, info
    profile = provider.get(weapon)
    if not profile:
        return 'excluded', 'non_gun_kill', info
    if profile['group'] != 'shotgun':
        return None, None, info
    tick = int(event['tick'])
    before = states[states.tick == tick - 1].to_dict('records') if not states.empty else []
    attacker = next((s for s in before if s['player_id'] == event['attacker_steamid']), {})
    victim = next((s for s in before if s['player_id'] == event['user_steamid']), {})
    info.update(target_pre_health=victim.get('health'), target_pre_armor=victim.get('armor_value'))
    if all(finite(s.get(k)) for s in (attacker, victim) for k in ('X', 'Y', 'Z')):
        info['distance_units'] = math.sqrt(sum((attacker[k]-victim[k])**2 for k in ('X','Y','Z')))
    hurts = [e for e in events if e.get('event_name') == 'player_hurt' and e.get('tick') == tick
             and e.get('user_steamid') == event['user_steamid']]
    fires = [e for e in events if e.get('event_name') == 'weapon_fire' and e.get('tick') == tick
             and e.get('player_id') == event['attacker_steamid'] and provider.normalize(e.get('weapon')) == weapon]
    # One unambiguous torso damage event with a verified pre-health transition is
    # evidence of a body kill at this observed distance, not a general lethal radius.
    if (event.get('headshot') is False and len(hurts) == 1 and len(fires) == 1):
        h = hurts[0]
        if (h.get('attacker_steamid') == event['attacker_steamid'] and provider.normalize(h.get('weapon')) == weapon
            and h.get('hitgroup') in (2,3) and h.get('health') == 0 and finite(victim.get('health'))
            and finite(h.get('dmg_health')) and h['dmg_health'] >= victim['health'] > 0):
            info['body_one_shot_observed'] = True
            return 'excluded', 'shotgun_body_one_shot_observed', info
    return 'unknown', 'shotgun_lethal_distance_unverified', info


REASONS = {
    'excluded_awp': 'AWP 击杀排除：不要求命中头部即可一枪致死',
    'excluded_taser': '电击枪击杀排除',
    'non_gun_kill': '非主副武器枪械击杀排除',
    'shotgun_body_one_shot_observed': '已验证该距离躯干单次射击致死，排除；不外推通用致死半径',
    'shotgun_lethal_distance_unverified': '霰弹枪躯干一枪致死距离尚未标定：保留距离/血甲证据，暂不进入主指标',
}


def window_measure(rows, start, end, dt, provider):
    by_tick = {int(s['tick']): clean(s) for s in rows}
    curve, values = [], []
    valid_seconds = 0.0
    segment = 0
    previous_valid = False
    last_handle = None
    for tick in range(start, end):
        a, b = by_tick.get(tick), by_tick.get(tick + 1)
        def usable(s):
            return (s is not None and s.get('is_alive') is True and finite(s.get('pitch'))
                    and provider.get(s.get('active_weapon_name')) is not None)
        valid = (usable(a) and usable(b) and a.get('weapon_handle') is not None
                 and a['weapon_handle'] == b.get('weapon_handle') and a.get('pawn_handle') is not None
                 and a['pawn_handle'] == b.get('pawn_handle') and a.get('team_num') == b.get('team_num'))
        if valid:
            if not previous_valid or last_handle != a['weapon_handle']: segment += 1
            values.append(a['pitch']); valid_seconds += dt
            curve.append({'tick': tick, 'view_pitch': a['pitch'], 'view_yaw': a.get('yaw'), 'segment_id': segment})
            last_handle = a['weapon_handle']
        else:
            curve.append({'tick': tick, 'view_pitch': None, 'view_yaw': None, 'segment_id': None})
        previous_valid = bool(valid)
    return {'curve': curve, 'valid_seconds': valid_seconds, 'sample_count': len(values),
            'pitch_p95_p5': float(np.percentile(values,95)-np.percentile(values,5)) if len(values)>=2 else None,
            'pitch_range': max(values)-min(values) if len(values)>=2 else None}


def analyze(ctx, p, cancel, progress):
    dt = ctx.meta['tick_seconds']; evidence = []; byplayer = defaultdict(list); reasons = Counter()
    for r in ctx.rounds():
        if not r['complete']: continue
        check_cancel(cancel); progress('击杀前瞄准变化', r['round_id'])
        frame = ctx.query('events', round_id=r['round_id'])
        if frame.empty: continue
        events = clean(frame.drop_duplicates('event_id').to_dict('records'))
        kills = [e for e in events if e.get('event_name')=='player_death' and e.get('in_live_round') and enemy(e)]
        if not kills: continue
        states = ctx.query('player_states', round_id=r['round_id'])
        players = {pid: f for pid,f in states.groupby('player_id')} if not states.empty else {}
        for e in kills:
            check_cancel(cancel)
            pid=e['attacker_steamid']; t=int(e['tick'])
            start=t-math.ceil(1/dt); end=t-1  # event-tick end can already include post-kill flicks
            excluded, code, info = kill_exclusion(e, ctx.providers.weapons, states, events)
            f=players.get(pid)
            rows=clean(f[f.tick.between(max(start,r['live_tick']),end)].to_dict('records')) if f is not None else []
            measured=window_measure(rows,start,end,dt,ctx.providers.weapons)
            # There are ceil(1/dt)-1 pre-event intervals; denominator is the requested 1 second.
            valid = measured['pitch_p95_p5'] is not None and measured['valid_seconds'] >= p['kill_min_coverage']
            judgement=excluded or ('descriptive' if valid else 'unknown')
            reason=REASONS.get(code) or ('记录上下视角变化；高低差转瞄、跟枪、压枪均会影响，不代表头线好坏' if valid else '击杀前主副武器连续有效片段不足')
            row={'evidence_id':'kill-aim:'+e['event_id'], 'event_id':e['event_id'], 'round_id':r['round_id'],
                 'player_id':pid,'target_id':e['user_steamid'],'tick':start,'end_tick':end,'kill_tick':t,
                 'start_time':start*dt,'end_time':end*dt,'weapon':info['weapon'],'kind':'kill_aim',
                 'analysis_mode':'kill_window','judgement':judgement,'exclusion_code':code,
                 'headshot':e.get('headshot'),'quality':'derived','raw_field_paths':['player_death','pitch','yaw','active_weapon_name','weapon_handle','pawn_handle'],
                 'reason':reason,'sample_semantics':'end-of-tick pitch; event tick excluded; continuous same-weapon intervals only',
                 'requested_seconds':1.0,'values':info, **measured}
            row['shot_ticks']=[x['tick'] for x in events if x.get('event_name')=='weapon_fire' and x.get('player_id')==pid and start<=x['tick']<=end]
            row['hurt_ticks']=[x['tick'] for x in events if x.get('event_name')=='player_hurt' and x.get('user_steamid')==pid and start<=x['tick']<=end]
            row['phase_summaries']=phases(rows,start,end,row['shot_ticks'],dt,ctx.providers.weapons,window_measure)
            if excluded:row['pitch_p95_p5']=row['pitch_range']=None;row['curve']=[]
            reasons[code or judgement]+=1;evidence.append(row);byplayer[pid].append(row)
    metrics=[]
    for pid,rows in byplayer.items():
        for i,row in enumerate(rows):
            row['overlapping_window_ids']=[x['evidence_id'] for j,x in enumerate(rows) if i!=j and row['round_id']==x['round_id'] and max(row['tick'],x['tick'])<=min(row['end_tick'],x['end_tick'])]
        for weapon in [None]+sorted({x['weapon'] for x in rows}):
            chosen=[x for x in rows if weapon is None or x['weapon']==weapon]
            eligible=[x for x in chosen if x['judgement']!='excluded']; known=[x for x in eligible if x['judgement']=='descriptive']
            scope={'player_id':pid,'analysis_mode':'kill_window'}
            if weapon:scope['weapon']=weapon
            common=dict(scope=scope,eligible=len(eligible),evaluated_count=len(known),unknown=len(eligible)-len(known),excluded=len(chosen)-len(eligible),sample_unit='kill_window',evidence=[x['evidence_id'] for x in chosen],quality='derived',limitations=['只代表成功击杀窗口，不能代表全场预瞄','视角不等于渲染准星或压枪残差','重叠击杀窗口按击杀分别计数'])
            for mid,field in [('kill_pitch_span_p50','pitch_p95_p5'),('kill_pitch_range_p50','pitch_range')]:
                m=metric(MID,mid,float(np.median([x[field] for x in known])) if known else None,unit='degrees',method='每次有效击杀前 1 秒的角度幅度，再取击杀窗口中位数',**common)
                m['aggregation']='kill_window_quantile';metrics.append(m)
            metrics.append(metric(MID,'eligible_kill_windows',len(known),unit='count',method='通过武器排除与有效时长检查的击杀窗口数',**common))
    # The old geometric method is retained as an explicitly experimental view.
    legacy=legacy_analyze(ctx,p,cancel,progress)
    for m in legacy['metrics']:m['scope']['analysis_mode']='experimental_geometry'
    for e in legacy['evidence']:e['analysis_mode']='experimental_geometry'
    metrics.extend(legacy['metrics']);evidence.extend(legacy['evidence'])
    context_metrics,context_evidence=analyze_context_windows(ctx,p,cancel,progress,window_measure)
    metrics.extend(context_metrics);evidence.extend(context_evidence)
    return {'status':'partial' if any(x['judgement']=='unknown' for x in evidence) or legacy['status']!='succeeded' else 'succeeded',
            'metrics':metrics,'evidence':evidence,'details':{'notes':['默认：击杀前垂直瞄准变化，非头线成功率。','AWP、电击枪排除；霰弹枪未验证致死距离的样本暂不进入主指标。','上下变化小不等于预瞄正确；射击和受伤时间标记帮助解释曲线。','实验几何视图保留旧方法，不应用击杀窗口筛选。'],
            'kill_window_reason_counts':dict(reasons),'shotgun_distance_calibrated':False,'context_window_count':len(context_evidence),'experimental_geometry':legacy['details']}}
