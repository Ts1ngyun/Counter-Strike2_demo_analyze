import json,math
from collections import defaultdict
from ...core.common import metric,ratio,check_cancel,clean

MID='stop_shooting'
def classify_speed(pre,end,threshold,margin=0):
    if pre is None or end is None or threshold is None or not all(math.isfinite(x) for x in [pre,end,threshold]):return 'unknown'
    if max(pre,end)<threshold-margin:return 'ready'
    if min(pre,end)>threshold+margin:return 'moving'
    return 'ambiguous'

def movement_segment(rows,threshold,enter_multiplier,min_seconds):
    active=None;segments=[]
    for x in rows:
        v=x.get('speed_xy');dt=x.get('interval_seconds')
        if v is None or dt is None or not math.isfinite(v) or not math.isfinite(dt):
            if active and active['duration']>=min_seconds:segments.append(active)
            active=None;continue
        if active is None and v>threshold*enter_multiplier:active={'start_tick':int(x['interval_start_tick']),'end_tick':int(x['tick']),'duration':float(dt),'peak_speed':v}
        elif active:
            if v<threshold:
                if active['duration']>=min_seconds:segments.append(active)
                active=None
            else:active.update(end_tick=int(x['tick']),duration=active['duration']+dt,peak_speed=max(active['peak_speed'],v))
    if active and active['duration']>=min_seconds:segments.append(active)
    return segments[-1] if segments else None

def analyze(ctx,p,cancel,progress):
    dt=ctx.meta['tick_seconds'];evidence=[];groups=defaultdict(list)
    for r in ctx.rounds():
        if not r['complete']:continue
        check_cancel(cancel);rid=r['round_id'];shots=ctx.query('shots',round_id=rid);movement=ctx.query('movement',round_id=rid)
        if shots.empty:continue
        byplayer={pid:f for pid,f in movement.groupby('player_id')}
        for shot in shots.to_dict('records'):
            pid=shot['player_id'];a=json.loads(shot['pre_json']);b=json.loads(shot['end_json']);profile=json.loads(shot['profile_json']);reasons=json.loads(shot['unknown_reasons']);kind='unknown';seg=None;first=False;wait=None
            threshold=profile['threshold']*p['threshold_scale'] if profile and profile['threshold'] is not None else None
            if threshold is None:reasons.append('武器最大速度/开镜状态缺失，无法计算阈值')
            if not shot['is_gun']:kind='excluded';reasons=['非已配置枪械']
            elif a and b and (a.get('is_airborne') is True or b.get('is_airborne') is True):kind='excluded';reasons.append('空中射击另列，不判为操作错误')
            elif a and b and (a.get('is_airborne') is not False or b.get('is_airborne') is not False):reasons.append('在地面状态未知')
            elif not reasons and ctx.capabilities.get('estimated_velocity',{}).get('usable'):
                kind=classify_speed(a.get('speed_xy'),b.get('speed_xy'),threshold,p['boundary_margin'])
                if kind in ('ambiguous','unknown'):reasons.append('相邻区间跨阈值或速度缺失，不能强行二分')
            history=byplayer.get(pid)
            history=history[history.tick.between(shot['tick']-math.ceil(p['movement_lookback_ms']/1000/dt),shot['tick']-1)].to_dict('records') if history is not None else []
            history=clean(history)
            first_status='none'
            if threshold is not None:
                history=[{**x,'speed_xy':x.get('speed_xy') if x.get('weapon_handle')==a.get('weapon_handle') and x.get('is_airborne') is False and x.get('is_alive') is True else None} for x in history] if a else []
                seg=movement_segment(history,threshold,p['movement_enter_multiplier'],p['movement_min_ms']/1000)
                prev=shot.get('previous_fire_tick');prev=None if prev is None or not math.isfinite(prev) else prev
                first=bool(seg and (prev is None or prev<seg['start_tick']))
                expected_start=max(r['live_tick']+1,shot['tick']-math.ceil(p['movement_lookback_ms']/1000/dt))
                complete_history=bool(history) and {int(x['tick']) for x in history}==set(range(expected_start,shot['tick'])) and all(x.get('speed_xy') is not None for x in history)
                first_status='first' if first and complete_history else 'none' if complete_history else 'unknown'
                first=first_status=='first'
                if first:
                    low=[x for x in history if x['tick']>seg['end_tick'] and x.get('speed_xy') is not None and x['speed_xy']<threshold-p['boundary_margin']]
                    if low and all(x.get('speed_xy') is not None and x['speed_xy']<threshold-p['boundary_margin'] for x in history if x['tick']>=low[0]['tick']):wait=(shot['tick']-low[0]['tick'])*dt
            else:first_status='unknown'
            row={'evidence_id':shot['shot_id'],'round_id':rid,'player_id':pid,'tick':shot['tick'],'start_tick':shot['tick']-2,'end_tick':shot['tick'],'start_time':shot['time_start'],'end_time':shot['time_end'],'weapon':shot['weapon'],'weapon_group':shot['weapon_group'],'weapon_handle':shot['weapon_handle'],'kind':'stop_shot','judgement':kind,'is_movement_first':first,'movement_first_status':first_status,'movement_segment':seg,'wait_after_low_speed_seconds':wait,'threshold':threshold,'boundary_margin':p['boundary_margin'],'selected_max_speed':profile.get('selected_max_speed') if profile else None,'threshold_source':profile['source'] if profile else None,'grounded':not a['is_airborne'] if a and a.get('is_airborne') is not None else None,'self_pose':'蹲伏' if a and a.get('duck_amount',0) is not None and a['duck_amount']>.5 else '站立/过渡','values':{'pre':a,'end':b},'curve':[{'tick':x['tick'],'speed':x.get('speed_xy')} for x in history]+[{'tick':shot['tick'],'speed':b.get('speed_xy') if b else None}],'raw_field_paths':['X','Y','Z','game_time','is_alive','is_airborne','weapon_handle','weapon_fire'],'reason':'；'.join(reasons) or '武器最大移动速度 × 34% × 参数倍率；相邻区间平均地速判定，不能保证子弹准确','sample_semantics':'two adjacent interval averages, not bounds on instantaneous speed; subtick unknown','quality':'estimated','event_index':shot['event_index']}
            row['weapon_sets']=[s for s in ('all','exclude_run_and_gun') if ctx.providers.weapons.in_weapon_set(shot['weapon'],s)]
            if first_status=='unknown':row['reason']+='；移动回看区间不完整或状态缺失，是否移动后首枪未知'
            row['team']=a.get('team_num') if a else None
            evidence.append(row)
            for weapon_set in row['weapon_sets']:
                groups[(pid,None,None,weapon_set)].append(row);groups[(pid,shot['weapon'],None,weapon_set)].append(row)
                if row['grounded'] is not None:groups[(pid,shot['weapon'],row['grounded'],weapon_set)].append(row)
    # Keep a visible null result for a player whose selected weapon set has no samples.
    for row in evidence:
        for weapon_set in ('all','exclude_run_and_gun'):groups.setdefault((row['player_id'],None,None,weapon_set),[])
    metrics=[]
    for (pid,weapon,ground,weapon_set),rows in groups.items():
        scope={'player_id':pid,'weapon_set':weapon_set}
        if weapon:scope.update(weapon=weapon)
        if ground is not None:scope['grounded']=ground
        for mid,chosen in [('shot_stationary_ready_rate',rows),('movement_to_first_shot_ready_rate',[x for x in rows if x['movement_first_status']!='none'])]:
            eligible=[x for x in chosen if x['judgement']!='excluded'];known=[x for x in eligible if x['judgement'] in ('ready','moving') and (mid=='shot_stationary_ready_rate' or x['is_movement_first'])];n=sum(x['judgement']=='ready' for x in known)
            metrics.append(metric(MID,mid,ratio(n,len(known)),scope,'ratio',n=n,d=len(known),eligible=len(eligible),unknown=len(eligible)-len(known),excluded=len(rows)-len(eligible),sample_unit='shot',quality='estimated',evidence=[x['evidence_id'] for x in chosen],method='最大移动速度 × 34% × 参数倍率；边界模糊带；移动后首枪需连续运动历史',limitations=['参考规则不保证子弹准确，未按 demo 补丁标定','无 subtick 开枪前状态','两区间均低速仍不能保证区间内无短暂速度峰值','未验证反向输入、移动精度恢复']))
        if weapon is None:metrics.append(metric(MID,'reverse_input_evidence',None,scope,eligible=len(rows),unknown=len(rows),quality='unknown',method='unavailable',limitations=['无可解释输入证据']))
    return {'status':'partial','metrics':metrics,'evidence':evidence,'details':{'profile_version':ctx.providers.weapons.version,'thresholds_calibrated':False,'instantaneous_speed_verified':False,'notes':['默认显示移动后首枪达标率；可切换所有射击。','全武器含全部已登记枪械；除跑打武器排除冲锋枪、霰弹枪及除沙鹰外的手枪。','速度为采样区间估计；34% 是参考判定规则，不代表必定准确。'],'weapon_data_source':ctx.providers.weapons.data['source']}}
