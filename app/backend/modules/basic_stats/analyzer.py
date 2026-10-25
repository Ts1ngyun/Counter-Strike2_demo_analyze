from collections import Counter,defaultdict
import json,math
import pandas as pd
from ...core.common import metric,ratio,check_cancel,clean

MID='basic_stats'
def enemy(e):
    return bool(e.get('attacker_steamid') and e.get('user_steamid') and e['attacker_steamid']!=e['user_steamid'] and e.get('attacker_team_num') in (2,3) and e.get('user_team_num') in (2,3) and e['attacker_team_num']!=e['user_team_num'])

def capped_damage(e,pre_health,same_tick_count):
    raw=e.get('dmg_health');post=e.get('health')
    if raw is None:return None
    if same_tick_count!=1 or pre_health is None or post is None:return None
    if not (0<=post<=pre_health<=100):return None
    effective=min(raw,pre_health)
    return effective if abs((pre_health-post)-effective)<0.01 else None

def analyze(ctx,p,cancel,progress):
    all_metrics=[];evidence=[];stats=defaultdict(Counter);weapons=defaultdict(Counter);sides=defaultdict(Counter);multis=defaultdict(Counter)
    participants=set();eligible_rounds=0;excluded=Counter()
    for r in ctx.rounds():
        check_cancel(cancel)
        if not r['complete']:excluded[r['phase']]+=1;continue
        rid=r['round_id'];eligible_rounds+=1
        ev=ctx.query('events',round_id=rid).drop_duplicates('event_id')
        live=ev[ev.in_live_round.fillna(False)].to_dict('records')
        states=ctx.query('player_states',start=int(r['live_tick']),end=int(r['live_tick']))
        endstates=ctx.query('player_states',start=int(r['end_tick']),end=int(r['end_tick']))
        membership={x['player_id']:x for x in states.to_dict('records') if x.get('team_num') in (2,3) and x.get('is_alive') and x['player_id'] not in ('0','None')}
        deaths=[clean(e) for e in live if e['event_name']=='player_death'];kills=[e for e in deaths if enemy(e)]
        hurts=[clean(e) for e in live if e['event_name']=='player_hurt'];hurt_counts=Counter((e['user_steamid'],e['tick']) for e in hurts)
        per=defaultdict(Counter);round_refs=defaultdict(list)
        death_tick={e['user_steamid']:e['tick'] for e in deaths}
        first_tick=min((e['tick'] for e in kills),default=None);opening=[e for e in kills if e['tick']==first_tick]
        for e in deaths:
            victim=e.get('user_steamid');att=e.get('attacker_steamid')
            if victim in membership:per[victim]['deaths']+=1;round_refs[victim].append(e['event_id'])
            if not enemy(e):excluded['self_or_team_or_unknown_death']+=1;continue
            if att not in membership or victim not in membership:excluded['missing_participant']+=1;continue
            per[att]['kills']+=1;per[att]['hs_kills']+=int(e.get('headshot') is True);round_refs[att].append(e['event_id'])
            weapons[(att,e.get('weapon'))]['kills']+=1;weapons[(att,e.get('weapon'))]['hs_kills']+=int(e.get('headshot') is True)
            assister=e.get('assister_steamid')
            if assister in membership and assister not in (att,victim) and membership[assister]['team_num']==membership[att]['team_num']:
                per[assister]['assists']+=1;per[assister]['flash_assists']+=int(e.get('assistedflash') is True)
            if len(opening)==1 and e['event_id']==opening[0]['event_id']:per[att]['opening_kills']+=1;per[victim]['opening_deaths']+=1
            for trade in kills:
                delta=(trade['tick']-e['tick'])*ctx.meta['tick_seconds']
                if 0<delta<=p['trade_seconds'] and trade['user_steamid']==att and trade['attacker_steamid'] in membership and trade['attacker_steamid']!=victim and trade['attacker_team_num']==e['user_team_num']:
                    per[victim]['traded']=1
        for e in hurts:
            if not enemy(e):excluded['non_enemy_hurt']+=1;continue
            att=e.get('attacker_steamid');victim=e.get('user_steamid')
            if att not in membership or victim not in membership:continue
            before=ctx.query('player_states',player=victim,start=int(e['tick'])-1,end=int(e['tick'])-1)
            pre=int(before.iloc[0].health) if len(before)==1 and before.iloc[0].is_alive else None
            dmg=capped_damage(e,pre,hurt_counts[(victim,e['tick'])]);raw=e.get('dmg_health')
            per[att]['raw_damage']+=raw or 0;per[att]['hurt_events']+=1;per[att]['head_hurt_events']+=int(e.get('hitgroup')=='head')
            per[att]['effective_known']+=int(dmg is not None);per[att]['effective_unknown']+=int(dmg is None);per[att]['effective_damage']+=dmg or 0
            if e.get('weapon') in ('hegrenade','inferno','molotov','incgrenade'):per[att]['grenade_damage_raw']+=raw or 0
            weapons[(att,e.get('weapon'))]['raw_damage']+=raw or 0
            evidence.append({'evidence_id':e['event_id'],'round_id':rid,'player_id':att,'target_id':victim,'tick':e['tick'],'weapon':e.get('weapon'),'kind':'damage','values':{'raw_damage':raw,'previous_tick_health':pre,'event_payload_health_after':e.get('health'),'attached_event_health':e.get('user_health'),'effective_damage':dmg},'reason':'相邻 tick 生命差与事件伤害一致，且该受害者本 tick 唯一受伤事件' if dmg is not None else '不能可靠封顶；保留原始伤害并使精确 ADR unavailable','raw_field_paths':['player_hurt.dmg_health','player_hurt.health','health'],'event_index':e['event_index'],'sample_semantics':'previous tick end versus event payload post-damage; entity attachment not used as pre-health'})
        for e in live:
            if e['event_name']=='weapon_fire' and e.get('user_steamid') in membership:per[e['user_steamid']]['fire_events']+=1
        for pid,state in membership.items():
            participants.add(pid);s=per[pid];s['participated_rounds']=1
            last=endstates[endstates.player_id==pid]
            survival=bool(len(last)==1 and last.iloc[0].is_alive and pid not in death_tick)
            s['survived']=int(survival);s['kast']=int(s['kills']>0 or s['assists']>0 or survival or s['traded']>0)
            s['opening_unknown']=int(len(opening)>1)
            stats[pid].update(s);sides[(pid,int(state['team_num']))].update(s);multis[pid][str(s['kills'])]+=1
            evidence.append({'evidence_id':f'{rid}:{pid}','round_id':rid,'player_id':pid,'tick':int(r['live_tick']),'end_tick':int(r['end_tick']),'team':int(state['team_num']),'kind':'round_stats','values':dict(s),'event_refs':round_refs[pid],'reason':'参与分母：freeze_end 的存活正式 T/CT 玩家；完整回合；KAST_local=击杀/游戏助攻/存活/5 秒内队友补掉击杀者之一','raw_field_paths':['round_start','round_freeze_end','round_end','player_death','player_hurt','is_alive','team_num']})
    def emit(pid,s,scope):
        scope={'player_id':pid,**scope};rr=s['participated_rounds'];refs=[f"{x['round_id']}:{pid}" for x in evidence if x.get('kind')=='round_stats' and x['player_id']==pid and ('team' not in scope or x['team']==scope['team'])]
        for k in ['kills','deaths','assists','flash_assists','hs_kills','participated_rounds','opening_kills','opening_deaths','grenade_damage_raw']:
            all_metrics.append(metric(MID,k,s[k],scope,unit='hp' if k=='grenade_damage_raw' else 'count',evidence=refs,eligible=rr))
        all_metrics.append(metric(MID,'opening_difference',s['opening_kills']-s['opening_deaths'],scope,eligible=rr,unknown=s['opening_unknown'],evidence=refs))
        for mid,num,den,unit in [('kd',s['kills'],s['deaths'],'kills/death'),('kpr',s['kills'],rr,'per_round'),('dpr',s['deaths'],rr,'per_round'),('hs_kill_pct',s['hs_kills'],s['kills'],'ratio'),('survival_rate',s['survived'],rr,'ratio'),('kast_local',s['kast'],rr,'ratio'),('adr_raw',s['raw_damage'],rr,'hp/round'),('head_hurt_event_share',s['head_hurt_events'],s['hurt_events'],'ratio'),('head_hurt_events_per_fire',s['head_hurt_events'],s['fire_events'],'events/fire')]:
            all_metrics.append(metric(MID,mid,ratio(num,den),scope,unit,n=num,d=den,evidence=refs,limitations=['零分母返回 null','hurt/fire 是事件比，不是命中率','ADR raw 未保证过量伤害封顶'] if mid in ('adr_raw','head_hurt_events_per_fire') else ['KAST_local 是本产品规则；同 tick 交易/首杀顺序不明时不认定'] if mid=='kast_local' else []))
        all_metrics.append(metric(MID,'adr_effective',ratio(s['effective_damage'],rr) if not s['effective_unknown'] else None,scope,'hp/round',n=s['effective_damage'] if not s['effective_unknown'] else None,d=rr,eligible=s['hurt_events'],evaluated_count=s['effective_known'],unknown=s['effective_unknown'],sample_unit='hurt_event',quality='derived' if not s['effective_unknown'] else 'unknown',evidence=refs,method='逐事件唯一受伤、相邻生命差验证；任一伤害未知则整项不称精确 ADR',limitations=[f"{s['effective_unknown']} 个对敌伤害事件不能封顶；伤害覆盖率按 hurt 事件计算，ADR 分母仍为参与回合"] ))
    for pid,s in stats.items():emit(pid,s,{})
    for (pid,side),s in sides.items():emit(pid,s,{'team':side})
    for (pid,w),s in weapons.items():
        for k in ['kills','hs_kills','raw_damage']:all_metrics.append(metric(MID,k,s[k],{'player_id':pid,'weapon':w},unit='hp' if k=='raw_damage' else 'count',eligible=s['kills'],evidence=[e['evidence_id'] for e in evidence if e['player_id']==pid and e.get('weapon')==w]))
    return {'status':'partial' if any(s['effective_unknown'] for s in stats.values()) else 'succeeded','metrics':all_metrics,'evidence':evidence,'details':{'multi_kill_round_distribution':dict(multis),'excluded':dict(excluded),'official_rounds':eligible_rounds,'participants':sorted(participants)}}
