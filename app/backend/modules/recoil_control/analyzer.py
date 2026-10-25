import math,json
from collections import defaultdict
import numpy as np
from ...core.common import metric,wrap,check_cancel,clean

MID='recoil_control'
def damage_by_shot(seq,events,provider,all_shots=None):
    """Same-tick event association only; no bullet hit ratio or causal guarantee."""
    result=[]
    for index,shot in enumerate(seq):
        candidates=[s for s in (all_shots if all_shots is not None else seq) if s['tick']==shot['tick']
            and s.get('player_id',shot['player_id'])==shot['player_id'] and provider.normalize(s.get('weapon',shot['weapon']))==shot['weapon']]
        hurts=[e for e in events if e.get('event_name')=='player_hurt' and e.get('attacker_steamid')==shot['player_id']
            and e['tick']==shot['tick'] and provider.normalize(e.get('weapon'))==shot['weapon']]
        result.append({'shot_number':index+1,'shot_id':shot['shot_id'],'tick':shot['tick'],
            'association':'same_tick_unique_shot' if len(candidates)==1 else 'ambiguous_same_tick_shots',
            'damage_events':[{k:e.get(k) for k in ('event_id','user_steamid','user_name','dmg_health','dmg_armor','health','hitgroup')} for e in hurts] if len(candidates)==1 else [],
            'ambiguous_event_ids':[e['event_id'] for e in hurts] if len(candidates)!=1 else [],
            'raw_damage':sum(e.get('dmg_health') or 0 for e in hurts) if len(candidates)==1 else None})
    return result

def residual(view,punch,target=None,view_includes_punch=False):
    """Only call with independently validated effective P, never raw baseAngle."""
    if punch is None:return None
    v=np.asarray(view,float);p=np.asarray(punch,float);t=np.asarray(target,float) if target is not None else np.zeros_like(v)
    if v.shape!=p.shape or v.shape!=t.shape:raise ValueError('角轨迹维度不符')
    return wrap((v-v[0])+(0 if view_includes_punch else p-p[0])-(t-t[0]))

def sampled_trajectory(states,burst,shots):
    rows=clean(states.to_dict('records')) if not states.empty else []
    by_tick={int(s['tick']):s for s in rows}; curve=[];flags=[];segment=0;previous=None
    fire_ticks={s['tick'] for s in shots};first_yaw=None;previous_yaw=None;yaw_delta=0
    for tick in range(burst['tick'],burst['end_tick']+1):
        s=by_tick.get(tick);valid=bool(s and s.get('is_alive') is True and s.get('pitch') is not None and s.get('yaw') is not None and s.get('pawn_handle') is not None and s.get('weapon_handle') is not None and str(int(s['weapon_handle']))==str(burst['weapon_handle']))
        if not valid:
            curve.append({'tick':tick,'view_pitch':None,'view_yaw':None,'segment_id':None,'effective_recoil':None,'residual':None});flags.append(None);previous=None;previous_yaw=None;continue
        if previous is None or previous.get('pawn_handle')!=s.get('pawn_handle'):segment+=1;previous_yaw=None
        if first_yaw is None:first_yaw=s['yaw']
        yaw_delta=wrap(s['yaw']-first_yaw) if previous_yaw is None else yaw_delta+wrap(s['yaw']-previous_yaw)
        attack=s.get('FIRE');command=s.get('usercmd_buttonstate_1')
        consistent=isinstance(attack,bool) and command is not None and bool(int(command)&1)==attack
        flags.append(attack if consistent else None)
        curve.append({'tick':tick,'view_pitch':s['pitch'],'view_yaw':s['yaw'],'relative_yaw':yaw_delta,
                      'segment_id':segment,'shot':tick in fire_ticks,'attack_sample':attack,'command_attack_sample':bool(int(command)&1) if command is not None else None,
                      'effective_recoil':None,'residual':None})
        previous=s;previous_yaw=s['yaw']
    status='unknown' if not flags or segment>1 or any(x is None for x in flags) else 'continuous_attack_samples' if all(flags) else 'intermittent_attack_samples'
    return curve,status

def analyze(ctx,p,cancel,progress):
    evidence=[];groups=defaultdict(list)
    for r in ctx.rounds():
        if not r['complete']:continue
        check_cancel(cancel);rid=r['round_id'];bursts=ctx.query('bursts',round_id=rid);shots=ctx.query('shots',round_id=rid);ev=ctx.query('events',round_id=rid)
        if bursts.empty:continue
        event_records=clean(ev.to_dict('records'))
        shotmap={s['shot_id']:s for s in shots.to_dict('records')}
        round_states=ctx.query('player_states',round_id=rid)
        states_by_player={pid:f for pid,f in round_states.groupby('player_id')} if not round_states.empty else {}
        for burst in bursts.to_dict('records'):
            check_cancel(cancel)
            if burst['shot_count']<p['min_burst_shots']:continue
            pid=burst['player_id'];seq=[shotmap[x] for x in json.loads(burst['shot_ids_json'])];curve=[];reasons=[]
            for i,s in enumerate(seq):
                a=json.loads(s['pre_json']);b=json.loads(s['end_json'])
                curve.append({'shot':i+1,'tick':s['tick'],'view_pitch':a.get('pitch') if a else None,'view_yaw':a.get('yaw') if a else None,'raw_base_angle':a.get('recoil_base') if a else None,'recoil_index':a.get('recoil_index') if a else None,'effective_recoil':None,'residual':None,'pre':a,'end':b})
            flinch=ev[(ev.event_name=='player_hurt') & (ev.player_id==pid) & ev.tick.between(burst['tick']-1,burst['end_tick'])]
            if len(flinch):reasons.append('序列内受伤，视角扰动来源混合；从稳定轨迹统计排除')
            if burst['ambiguous']:reasons.append('缺失/同 tick/武器切换边界不确定')
            views=[x['view_pitch'] for x in curve];ducks=[x['pre'].get('duck_amount') for x in curve if x['pre']]
            if len(ducks)!=len(curve) or any(x is None for x in ducks):reasons.append('姿态缺失')
            elif max(ducks)-min(ducks)>p['pose_change_limit']:reasons.append('姿态大变')
            if any(x['pre'] is None or x['pre'].get('is_airborne') is not False or x['pre'].get('speed_xy') is None for x in curve):reasons.append('运动/连续状态异常')
            if any(v is None for v in views):reasons.append('视角缺失')
            category='automatic_sequence' if burst['weapon_group'] in ('rifle','smg') else 'single_fire_sequence'
            row={'evidence_id':burst['burst_id'],'round_id':rid,'player_id':pid,'tick':burst['tick'],'end_tick':burst['end_tick'],'weapon':burst['weapon'],'weapon_group':burst['weapon_group'],'weapon_handle':burst['weapon_handle'],'kind':'view_trajectory','category':category,'shot_count':burst['shot_count'],'judgement':'descriptive' if not reasons else 'excluded','view_pitch_delta':float(wrap(views[-1]-views[0])) if not reasons else None,'curve':curve,'quality':'observed','reason':'；'.join(reasons) or '仅描述玩家视角轨迹；跟枪贡献、随机散布和有效 recoil 未分解','raw_field_paths':['pitch','yaw','CCSPlayerPawn.CCSPlayer_AimPunchServices.m_predictableBaseAngle','Weapon.m_flRecoilIndex','weapon_fire'],'limitations':['有效 recoil 缺失；不生成压枪成功率','无法可靠识别换目标，故不扣除跟枪','射击模式不可用；恢复间隔为武器分组实验规则','raw baseAngle 仅供检查，绝不加入补偿公式'],'sample_semantics':'per-shot previous tick end; not actual rendered crosshair','event_refs':[x['shot_id'] for x in seq]}
            states=states_by_player.get(pid,round_states.iloc[:0])
            if not states.empty:states=states[states.tick.between(burst['tick'],burst['end_tick'])]
            row['per_shot_curve']=curve
            row['shot_damage']=damage_by_shot([{**s,'player_id':pid,'weapon':burst['weapon']} for s in seq],event_records,ctx.providers.weapons,shotmap.values())
            row['target_movement']=[]
            target_ids={d['user_steamid'] for s in row['shot_damage'] for d in s['damage_events'] if d.get('user_steamid')}
            for target in sorted(target_ids):
                tf=states_by_player.get(target)
                samples=clean(tf[tf.tick.between(burst['tick'],burst['end_tick'])].to_dict('records')) if tf is not None else []
                valid=[s for s in samples if all(s.get(k) is not None for k in ('X','Y','Z'))]
                row['target_movement'].append({'player_id':target,'sample_count':len(samples),'airborne_sample_count':sum(s.get('is_airborne') is True for s in samples),
                    'start_position':{k:valid[0][k] for k in ('tick','X','Y','Z')} if valid else None,
                    'end_position':{k:valid[-1][k] for k in ('tick','X','Y','Z')} if valid else None,
                    'meaning':'被伤害对象在序列期间的状态；不是已确认瞄准目标，不用于扣除跟枪'})
            row['curve'],row['attack_input_status']=sampled_trajectory(states,burst,seq)
            row['shot_ticks']=[s['tick'] for s in seq]
            row['hurt_ticks']=flinch.tick.tolist()
            row['raw_field_paths']+=['FIRE -> m_nButtonDownMaskPrev','usercmd_buttonstate_1']
            row['sample_semantics']='end-of-tick network view and attack samples; not rendered crosshair, physical mouse state or continuous subtick hold'
            row['limitations']+=['持续攻击仅指所有已观测 tick 的两个攻击字段一致为真，不能证明采样之间始终按住左键','敌人跑跳/跟枪未分离，不评价压枪准度']
            row['limitations']+=['弹序伤害仅按同 tick 唯一开火关联；无伤害事件不等于空枪，同 tick 多枪不分配伤害','原始伤害可能含溢出，不是有效伤害或弹着点']
            row['reason']+='；'+{'continuous_attack_samples':'观测区间攻击输入持续为真','intermittent_attack_samples':'观测到攻击输入松开或间断','unknown':'攻击输入缺失、字段不一致或轨迹不连续'}[row['attack_input_status']]
            evidence.append(row);groups[(pid,None)].append(row);groups[(pid,burst['weapon'])].append(row)
    metrics=[]
    for (pid,weapon),rows in groups.items():
        scope={'player_id':pid}
        if weapon:scope['weapon']=weapon
        known=[x for x in rows if x['judgement']=='descriptive'];refs=[x['evidence_id'] for x in rows]
        metrics.append(metric(MID,'descriptive_sequences',len(known),scope,eligible=len(rows),unknown=len(rows)-len(known),quality='observed',evidence=refs,sample_unit='sequence'))
        m=metric(MID,'view_pitch_delta_p50',float(np.median([x['view_pitch_delta'] for x in known])) if known else None,scope,'degrees',eligible=len(rows),unknown=len(rows)-len(known),quality='observed',evidence=refs,limitations=['视角变化不等于压枪能力']);m['aggregation']='sequence_quantile';metrics.append(m)
        for mid in ['compensation_residual_rms','actual_impact_dispersion']:metrics.append(metric(MID,mid,None,scope,'degrees',eligible=len(rows),unknown=len(rows),quality='unknown',evidence=refs,method='unavailable',limitations=['未还原当前生效 recoil 与视角是否已含 punch','未获取验证落点，不生成假弹道']))
    return {'status':'partial','metrics':metrics,'evidence':evidence,'details':{'capability_tier':'B','effective_recoil_available':False,'target_compensation':False,'view_includes_punch':'unknown','synthetic_formula_tests_are_not_demo_validation':True,'notes':['逐 tick 展示连续射击中的瞄准方向，并标出开枪、受伤时间。','攻击输入连续观测不等于物理左键持续按下；可筛选连续、间断与未知片段。','对手跑跳和跟枪会改变轨迹；当前只描述动作，不生成压枪准度。']}}
