import json, math
import pandas as pd
import numpy as np
from ..core.common import clean, dumps, check_cancel
from ..adapters.demo.parser import write_table

VERSION='1.1.0'
def enrich(states,tick_s):
    s=states.sort_values(['player_id','tick']).copy()
    for col in ['X','Y','Z','game_time','is_alive','team_num']:
        if col not in s:s[col]=np.nan
    g=s.groupby('player_id',sort=False);prev=g.shift()
    dt=s.game_time-prev.game_time;delta_tick=s.tick-prev.tick
    dist=np.sqrt((s.X-prev.X)**2+(s.Y-prev.Y)**2)
    valid=(delta_tick==1)&(abs(dt-tick_s)<max(0.0005,tick_s*.05))&(s.is_alive==True)&(prev.is_alive==True)&(s.round_id==prev.round_id)&(s.team_num==prev.team_num)&(dist<=64)&((s.Z-prev.Z).abs()<=64)
    if 'pawn_handle' in s:valid=valid&s.pawn_handle.notna()&(s.pawn_handle==prev.pawn_handle)
    s['speed_xy']=(dist/dt).where(valid)
    s['interval_start_tick']=prev.tick.where(valid);s['interval_seconds']=dt.where(valid)
    s['velocity_source']='estimated_position_difference'
    return s

def state_dict(row):
    keys=['tick','game_time','demo_time','X','Y','Z','pitch','yaw','health','is_alive','duck_amount','is_airborne','is_scoped','weapon_handle','active_weapon_name','active_weapon_ammo','accuracy_penalty','recoil_index','recoil_base','shots_fired','speed_xy','interval_start_tick','interval_seconds','team_num','flags','flash_duration','move_type','is_reloading','pawn_handle','burst_mode']
    return clean({k:row.get(k) for k in keys}) if row is not None else None

def build(context,progress,cancel):
    tick_s=context.meta['tick_seconds'];all_shots=[];all_bursts=[];engagements=[]
    for r in context.rounds():
        check_cancel(cancel)
        if not r['complete']:continue
        rid=r['round_id'];progress('共享特征',rid+'：开火、射击序列、事件邻近窗口')
        s=enrich(context.query('player_states',round_id=rid),tick_s)
        ev=context.query('events',round_id=rid);fire=ev[(ev.event_name=='weapon_fire') & ev.in_live_round.fillna(False)].sort_values(['tick','event_index'])
        lookups={pid:df.set_index('tick').to_dict('index') for pid,df in s.groupby('player_id')}
        duplicate=fire.groupby(['player_id','tick']).size().to_dict();per_player={}
        for row in fire.to_dict('records'):
            pid=row['player_id'];t=int(row['tick']);lookup=lookups.get(pid,{})
            a=lookup.get(t-1);b=lookup.get(t)
            if a:a={**a,'tick':t-1}
            if b:b={**b,'tick':t}
            profile=context.providers.weapons.get(row.get('weapon'), clean(a.get('is_scoped')) if a else None)
            known=bool(profile);reason=[]
            if not known:reason.append('非已配置枪械')
            if a is None or b is None:reason.append('缺少相邻 tick 状态')
            if a and b:
                if a.get('is_alive') is not True or b.get('is_alive') is not True:reason.append('死亡或状态不连续')
                if a.get('weapon_handle') is None or a.get('weapon_handle')!=b.get('weapon_handle'):reason.append('武器实例缺失或切换')
                if a.get('pawn_handle')!=b.get('pawn_handle'):reason.append('玩家实体变化')
                if a.get('is_reloading') or b.get('is_reloading'):reason.append('换弹边界')
                if a.get('burst_mode')!=b.get('burst_mode'):reason.append('射击模式切换')
            if duplicate.get((pid,t),0)>1:reason.append('同 tick 多次开火；原生顺序不可用')
            prev=per_player.get(pid)
            shot={'shot_id':row['event_id'],'event_id':row['event_id'],'event_index':row['event_index'],'round_id':rid,'player_id':pid,'tick':t,'demo_time':t*tick_s,
             'time_start':(t-1)*tick_s,'time_end':t*tick_s,'native_resolution_seconds':tick_s,'subtick':None,'source_sequence':None,
             'weapon':profile['weapon'] if profile else row.get('weapon'),'weapon_group':profile['group'] if profile else 'other',
             'weapon_handle':str(int(a['weapon_handle'])) if a and pd.notna(a.get('weapon_handle')) else None,
             'profile_json':dumps(profile),'pre_json':dumps(state_dict(a)),'end_json':dumps(state_dict(b)),'unknown_reasons':dumps(reason),
             'previous_fire_tick':prev['tick'] if prev else None,'is_gun':known,'feature_version':VERSION,'time_semantics':'bracket: previous tick end and event tick end; no exact pre-shot/subtick state'}
            all_shots.append(shot);per_player[pid]=shot
        for pid,group in pd.DataFrame([x for x in all_shots if x['round_id']==rid and x['is_gun']]).groupby('player_id') if any(x['round_id']==rid and x['is_gun'] for x in all_shots) else []:
            current=[];prev=None
            def flush():
                if not current:return
                first=current[0];last=current[-1];bid='burst:'+first['shot_id']
                ambiguous=any(json.loads(x['unknown_reasons']) for x in current)
                burst={'burst_id':bid,'round_id':rid,'player_id':pid,'tick':first['tick'],'end_tick':last['tick'],'weapon':first['weapon'],'weapon_group':first['weapon_group'],'weapon_handle':first['weapon_handle'],'shot_count':len(current),'shot_ids_json':dumps([x['shot_id'] for x in current]),'ambiguous':ambiguous,'feature_version':VERSION,'segmentation':'instance, ammo increase, shot-counter reset, death, profile experimental recovery gap; mode changes unavailable'}
                all_bursts.append(burst);engagements.append({'engagement_id':bid,'round_id':rid,'player_id':pid,'tick':first['tick'],'end_tick':last['tick'],'weapon':first['weapon'],'kind':'event_nearby_candidate_window','first_visibility_tick':None,'feature_version':VERSION})
            for shot in group.sort_values(['tick','event_index']).to_dict('records'):
                profile=json.loads(shot['profile_json']);a=json.loads(shot['pre_json']);b=json.loads(prev['end_json']) if prev else None
                split=prev is None or shot['weapon_handle']!=prev['weapon_handle'] or shot['weapon']!=prev['weapon'] or (shot['tick']-prev['tick'])*tick_s>profile['recovery_gap']
                if a and b:
                    split=split or a.get('pawn_handle')!=b.get('pawn_handle') or a.get('burst_mode')!=b.get('burst_mode') or a.get('is_reloading') is True or b.get('is_reloading') is True
                    split=split or (a.get('active_weapon_ammo') is not None and b.get('active_weapon_ammo') is not None and a['active_weapon_ammo']>b['active_weapon_ammo']) or (a.get('shots_fired') is not None and b.get('shots_fired') is not None and a['shots_fired']<b['shots_fired'])
                if split:flush();current=[]
                current.append(shot);prev=shot
            flush()
        # High-frequency interval facts, reused by the stop module, with NULL at discontinuities.
        cols=[c for c in ['player_id','round_id','tick','demo_time','game_time','speed_xy','interval_start_tick','interval_seconds','is_airborne','is_alive','duck_amount','weapon_handle','velocity_source'] if c in s]
        write_table(context.root,'movement',s[cols],rid)
    for name,rows in [('shots',all_shots),('bursts',all_bursts),('engagements',engagements)]:write_table(context.root,name,pd.DataFrame(rows))
