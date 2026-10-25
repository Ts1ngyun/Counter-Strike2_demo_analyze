"""Separate death and non-killing firing anchors; do not mix with kill denominator."""
import json
import math
from collections import defaultdict
import numpy as np
from ...core.common import clean, metric, check_cancel
from ..basic_stats.analyzer import enemy
from .legacy import distance_bucket


def phases(rows, start, end, shot_ticks, dt, provider, measure):
    shots=sorted(t for t in shot_ticks if start <= t <= end)
    first=shots[0] if shots else None
    result={}
    for name,a,b in [('before_first_shot',start,min(end,first-1) if first is not None else end),
                      ('shooting_phase',first,end)]:
        m=measure(rows,a,b,dt,provider) if a is not None and b>a else {'valid_seconds':0,'sample_count':0,'pitch_p95_p5':None,'pitch_range':None}
        result[name]={k:m[k] for k in ('valid_seconds','sample_count','pitch_p95_p5','pitch_range')}
        result[name].update(start_tick=a,end_tick=b)
    return result


def analyze_context_windows(ctx,p,cancel,progress,measure):
    dt=ctx.meta['tick_seconds']; evidence=[]; groups=defaultdict(list)
    for r in ctx.rounds():
        if not r['complete']:continue
        check_cancel(cancel);rid=r['round_id'];progress('死亡与未击杀射击瞄准窗口',rid)
        events=clean(ctx.query('events',round_id=rid).to_dict('records'))
        events=[e for e in events if e.get('in_live_round')]
        deaths=[e for e in events if e.get('event_name')=='player_death' and enemy(e)]
        bursts=clean(ctx.query('bursts',round_id=rid).to_dict('records'))
        if not deaths and not bursts:continue
        frame=ctx.query('player_states',round_id=rid)
        byplayer={pid:f for pid,f in frame.groupby('player_id')} if not frame.empty else {}
        anchors=[dict(mode='death_window',pid=e['user_steamid'],tick=e['tick'],ref=e['event_id'],target=e['attacker_steamid']) for e in deaths]
        for b in bursts:
            # Keep burst selection semantics explicit: a sequence with no recorded enemy kill inside its firing ticks.
            if any(e['attacker_steamid']==b['player_id'] and b['tick']<=e['tick']<=b['end_tick'] for e in deaths):continue
            targets={e['user_steamid'] for e in events if e.get('event_name')=='player_hurt' and enemy(e)
                and e['attacker_steamid']==b['player_id'] and b['tick']<=e['tick']<=b['end_tick']}
            anchors.append(dict(mode='engagement_window',pid=b['player_id'],tick=b['tick'],ref=b['burst_id'],
                target=next(iter(targets)) if len(targets)==1 else None,sequence_end_tick=b['end_tick']))
        state_ticks={a['tick']-1 for a in anchors}
        states=clean(frame[frame.tick.isin(state_ticks)].to_dict('records')) if not frame.empty else []
        at={(s['player_id'],s['tick']):s for s in states}
        for a in anchors:
            check_cancel(cancel);pid=a['pid'];t=a['tick'];start=max(r['live_tick'],t-math.ceil(1/dt));end=t-1
            before=at.get((pid,t-1),{});weapon=ctx.providers.weapons.normalize(before.get('active_weapon_name'))
            profile=ctx.providers.weapons.get(weapon);code=None;judgement=None
            if weapon in ('awp','taser'):judgement='excluded';code='excluded_'+weapon
            elif not before:judgement='unknown';code='missing_pre_state'
            elif not profile:judgement='excluded';code='non_gun_window'
            elif profile['group']=='shotgun':judgement='unknown';code='shotgun_lethal_distance_unverified'
            f=byplayer.get(pid)
            rows=clean(f[f.tick.between(start,end)].to_dict('records')) if f is not None else []
            m=measure(rows,start,end,dt,ctx.providers.weapons)
            valid=m['pitch_p95_p5'] is not None and m['valid_seconds']>=p['kill_min_coverage']
            judgement=judgement or ('descriptive' if valid else 'unknown')
            shot_ticks=[e['tick'] for e in events if e.get('event_name')=='weapon_fire' and e.get('player_id')==pid and start<=e['tick']<=end]
            other=at.get((a['target'],t-1),{}) if a['target'] else {}
            distance=None
            if all(isinstance(s.get(k),(int,float)) for s in (before,other) for k in ('X','Y','Z')):distance=math.sqrt(sum((before[k]-other[k])**2 for k in ('X','Y','Z')))
            row={'evidence_id':'context-aim:'+a['mode']+':'+a['ref'],'round_id':rid,'player_id':pid,'target_id':a['target'],
                'tick':start,'end_tick':end,'anchor_tick':t,'analysis_mode':a['mode'],'kind':'context_aim',
                'judgement':judgement,'exclusion_code':code,'quality':'derived','weapon':weapon,'distance_units':distance,
                'distance_bucket':None if distance is None else distance_bucket(distance),
                'self_airborne':before.get('is_airborne'),'target_airborne':other.get('is_airborne'),
                'shot_ticks':shot_ticks,'hurt_ticks':[e['tick'] for e in events if e.get('event_name')=='player_hurt' and e.get('user_steamid')==pid and start<=e['tick']<=end],
                'phase_summaries':phases(rows,start,end,shot_ticks,dt,ctx.providers.weapons,measure),
                'raw_field_paths':['pitch','yaw','weapon_handle','pawn_handle','player_death','weapon_fire','player_hurt'],
                'reason':('死亡前窗口' if a['mode']=='death_window' else '序列内无击杀的射击序列首枪前窗口')+'；独立样本口径，不与击杀样本合并；'+(code or '描述垂直转角，不评价预瞄正确性'),
                'sample_semantics':'end-of-tick samples before anchor; no visibility inference',**m}
            if judgement=='excluded' or code=='shotgun_lethal_distance_unverified':row.update(pitch_p95_p5=None,pitch_range=None,curve=[])
            if a.get('sequence_end_tick') is not None:
                firing_rows=clean(f[f.tick.between(t,a['sequence_end_tick'])].to_dict('records')) if f is not None else []
                firing=measure(firing_rows,t,a['sequence_end_tick'],dt,ctx.providers.weapons)
                row['phase_summaries']['shooting_phase']={k:firing[k] for k in ('valid_seconds','sample_count','pitch_p95_p5','pitch_range')}
                row['phase_summaries']['shooting_phase'].update(start_tick=t,end_tick=a['sequence_end_tick'])
            evidence.append(row);groups[(pid,a['mode'])].append(row)
    metrics=[]
    for (pid,mode),rows in groups.items():
        for weapon in [None]+sorted({r['weapon'] for r in rows if r['weapon']}):
            chosen=[r for r in rows if weapon is None or r['weapon']==weapon]
            eligible=[r for r in chosen if r['judgement']!='excluded'];known=[r for r in eligible if r['judgement']=='descriptive']
            scope={'player_id':pid,'analysis_mode':mode}
            if weapon:scope['weapon']=weapon
            common=dict(scope=scope,eligible=len(eligible),evaluated_count=len(known),unknown=len(eligible)-len(known),excluded=len(chosen)-len(eligible),
                sample_unit=mode,quality='derived',evidence=[r['evidence_id'] for r in chosen],limitations=['锚点选择不是首次看到敌人','各分析视图分母独立','没有击杀不等于失误'])
            prefix='death' if mode=='death_window' else 'nonkill'
            for suffix,field in [('pitch_span_p50','pitch_p95_p5'),('pitch_range_p50','pitch_range')]:
                m=metric('head_line',prefix+'_'+suffix,float(np.median([r[field] for r in known])) if known else None,unit='degrees',method='每个锚点前1秒有效垂直幅度的中位数',**common)
                m['aggregation']='context_window_quantile';metrics.append(m)
            metrics.append(metric('head_line',prefix+'_windows',len(known),method='有效描述窗口数',**common))
    return metrics,evidence
