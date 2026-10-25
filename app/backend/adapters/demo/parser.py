from pathlib import Path
import importlib.metadata, json, time, gc
import numpy as np
import pandas as pd
from demoparser2 import DemoParser
from .container import scan
from ...core.common import save, clean, VERSION, check_cancel
from ...core.field_catalog import enrich_catalog

RAW={
 'weapon_handle':'CCSPlayerPawn.CCSPlayer_WeaponServices.m_hActiveWeapon',
 'recoil_base':'CCSPlayerPawn.CCSPlayer_AimPunchServices.m_predictableBaseAngle',
 'recoil_index':'Weapon.m_flRecoilIndex','flags':'CCSPlayerPawn.m_fFlags',
 'move_type':'CCSPlayerPawn.m_MoveType','is_reloading':'Weapon.m_bInReload',
 'pawn_handle':'CCSPlayerController.m_hPawn','burst_mode':'Weapon.m_bBurstMode'}
BASE=['X','Y','Z','health','is_alive','team_num','team_clan_name','team_rounds_total','game_time','is_warmup_period','is_freeze_period','total_rounds_played','round_win_status']
EVENTS=['round_start','round_end','round_freeze_end','round_announce_match_start','cs_pre_restart','player_death','player_hurt','weapon_fire','player_spawn','player_team','player_disconnect','player_connect_full','bomb_planted','bomb_defused','bomb_exploded','grenade_thrown','player_blind','flashbang_detonate']

def write_table(root,name,df,part='0000'):
    d=Path(root)/name;d.mkdir(exist_ok=True,parents=True)
    if len(df): df.to_parquet(d/(str(part)+'.parquet'),index=False)

def make_rounds(events,max_tick):
    starts=sorted([e for e in events if e['event_name']=='round_start'],key=lambda e:e['tick'])
    ends=[e for e in events if e['event_name']=='round_end']
    freezes=[e for e in events if e['event_name']=='round_freeze_end']
    restarts=[e['tick'] for e in events if e['event_name']=='cs_pre_restart']
    rounds=[]
    for i,s in enumerate(starts):
        next_t=starts[i+1]['tick'] if i+1<len(starts) else max_tick+1
        fs=[e for e in freezes if s['tick']<=e['tick']<next_t]
        es=[e for e in ends if s['tick']<e['tick']<next_t and e.get('winner') is not None]
        end=es[0] if es else None; freeze=fs[0] if fs else None
        warm=s.get('is_warmup_period') is not False
        # cs_pre_restart is also emitted between ordinary rounds. Only an
        # interruption before a valid round_end invalidates a round.
        restart=any(s['tick']<t<(end['tick'] if end else next_t) for t in restarts)
        phase='warmup' if warm else 'restart' if restart else 'official' if freeze and end else 'incomplete'
        rounds.append({'round_id':f'r{i+1:03d}','raw_round':s.get('round'),'raw_total_rounds':s.get('total_rounds_played'),
         'tick':s['tick'],'start_tick':s['tick'],'live_tick':freeze['tick'] if freeze else None,'end_tick':end['tick'] if end else next_t-1,'next_tick':next_t,
         'phase':phase,'complete':phase=='official','winner':end.get('winner') if end else None,'reason':end.get('reason') if end else None,
         'source_start':s['event_id'],'source_end':end['event_id'] if end else None})
    return rounds

def extract(source,root,demo_hash,requested_fields,progress,cancel):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    progress('校验容器','扫描命令边界和文件完整性')
    container=scan(source,root/'commands',lambda:check_cancel(cancel))
    p=DemoParser(str(source));header=p.parse_header();parser_version=importlib.metadata.version('demoparser2')
    save(root/'raw_fields.json',p.list_updated_fields())
    progress('解析事件','提取原始事件与回合边界；事件序号仅在同一事件流内有效')
    check_cancel(cancel)
    available_events=p.list_game_events()
    parsed=p.parse_events(EVENTS,player=['health','team_num'],other=['game_time','total_rounds_played','is_warmup_period'])
    events=[]
    for name,df in parsed:
        for i,row in enumerate(json.loads(df.to_json(orient='records'))):
            for k,v in list(row.items()):
                if 'steamid' in k and v is not None:row[k]=str(v)
            events.append({**row,'event_name':name,'event_id':f'{name}:{i}','event_index':i,'source_sequence':None,'command_offset':None,'subtick':None,'time_semantics':'event payload; attached entity fields have unverified event-relative semantics','raw_json':json.dumps(row,ensure_ascii=False)})
    rounds=make_rounds(events,container['last_command_tick'])
    if not rounds:raise ValueError('未获得 round_start 边界，不能构造可审计回合')
    for e in events:
        r=next((r for r in rounds if r['start_tick']<=e['tick']<r['next_tick']),None)
        e['round_id']=r['round_id'] if r else None;e['player_id']=e.get('user_steamid')
        e['in_live_round']=bool(r and r['complete'] and r['live_tick']<=e['tick']<=r['end_tick'])
    event_df=pd.DataFrame(events)
    # Different event types reuse names such as 'reason' with different wire types.
    # Keep exact originals in raw_json; use a string only for conflicting flattened columns.
    for col in event_df.select_dtypes(include=['object']).columns:
        values=event_df[col].dropna()
        types={type(x) for x in values}
        if str in types and len(types)>1:event_df[col]=event_df[col].map(lambda x:None if x is None or isinstance(x,float) and np.isnan(x) else str(x))
    write_table(root,'events',event_df);write_table(root,'rounds',pd.DataFrame(rounds))
    players=p.parse_player_info();players['steamid']=players['steamid'].astype(str);players['player_id']=players['steamid'];write_table(root,'players',players)
    duration=container.get('playback_seconds');ticks=container.get('playback_ticks')
    tick_s=duration/ticks if duration and ticks else None
    if not tick_s or not 0.001<=tick_s<=0.1:raise ValueError('缺少可信 FileInfo 时间比例，不能执行高频机械分析')
    props=sorted(set(BASE+list(requested_fields)))
    probe_start=max(1,min(2905,container['last_command_tick']-12))
    probe=p.parse_ticks([RAW.get(x,x) for x in props]+['aim_punch_angle','velocity_X','velocity_Y'],ticks=list(range(probe_start,min(probe_start+10,container['last_command_tick']+1)))+[1,65])
    probe.rename(columns={v:k for k,v in RAW.items()},inplace=True)
    velocity_alignment={}
    if all(x in probe for x in ['X','Y','velocity_X','velocity_Y','game_time']):
        ordered=probe.sort_values(['steamid','tick']);g=ordered.groupby('steamid');delta=g.game_time.diff();dx=g.X.diff()/delta;dy=g.Y.diff()/delta
        lagx=dx.groupby(ordered.steamid).shift(1);lagy=dy.groupby(ordered.steamid).shift(1)
        adjacent=g.tick.diff().eq(1)&g.tick.diff().groupby(ordered.steamid).shift(1).eq(1)
        velocity_alignment={'probe_start_tick':probe_start,'probe_rows':int(adjacent.sum()),'current_interval_mean_L1_error':float(((ordered.velocity_X-dx).abs()+(ordered.velocity_Y-dy).abs())[adjacent].mean()),'previous_interval_mean_L1_error':float(((ordered.velocity_X-lagx).abs()+(ordered.velocity_Y-lagy).abs())[adjacent].mean())}
    # Probe existence, non-nullness and type independently from semantic validation.
    caps={};fields={};counts={};invalid_counts={};total=0;time_errors=[];name_history={};final=None;rosters={}
    for prop in props+['aim_punch_angle','velocity_X','velocity_Y']:
        col=probe[prop] if prop in probe else None
        caps[prop]={'column_present':col is not None,'non_null':int(col.notna().sum()) if col is not None else 0,'probe_rows':len(probe),
         'dtype':str(col.dtype) if col is not None else None,'usable':False,'semantic_status':'unverified'}
        fields[prop]={'canonical_name':prop,'raw_path':RAW.get(prop,prop),'unit':'degrees' if prop in ('pitch','yaw','recoil_base') else 'Source units' if prop in ('X','Y','Z') else 'seconds (parser-derived)' if prop=='game_time' else 'field-specific; see raw parser schema',
         'coordinate_convention':'Source right-handed X/Y plane, Z up; pitch positive downward' if prop in ('X','Y','Z','pitch','yaw') else None,
         'type':caps[prop]['dtype'],'source':'demoparser2 '+parser_version,'transformation_version':VERSION,'time_semantics':'end-of-demo-tick observation, not pre-event','null_rule':'absent/unavailable retained as NULL; no zero imputation','valid_range':{'duck_amount':[0,1],'pitch':[-90,90]}.get(prop),'dependencies':['X','Y','Z','continuous_time'] if prop.startswith('velocity') else []}
    supported=[x for x in props if x in probe.columns]
    # Filtered DataFrames, not streaming decoding: each bounded call reparses the file.
    batch=8192;last=container['last_command_tick'];all_time_deltas=[]
    for lo in range(0,last+1,batch):
        check_cancel(cancel);hi=min(lo+batch-1,last)
        progress('高频状态',f'请求 tick {lo}–{hi}，每次最多 {batch} tick；解析库会重扫文件')
        df=p.parse_ticks([RAW.get(x,x) for x in supported],ticks=list(range(lo,hi+1)))
        df.rename(columns={v:k for k,v in RAW.items()},inplace=True)
        if df.empty:continue
        df['player_id']=df['steamid'].astype(str);df.drop(columns='steamid',inplace=True)
        df.sort_values(['player_id','tick'],inplace=True)
        df['demo_time']=df['tick']*tick_s;df['net_tick']=None;df['subtick']=None
        df['round_id']=None
        for r in rounds:
            df.loc[df.tick.between(r['start_tick'],r['next_tick']-1),'round_id']=r['round_id']
            if r['live_tick'] is not None and lo<=r['live_tick']<=hi:
                rosters[r['round_id']]=df[df.tick==r['live_tick']][['player_id','name','team_num','team_clan_name','is_alive']].to_dict('records')
        g=df.groupby('player_id',sort=False);dt=g.game_time.diff();tk=g.tick.diff();ok=(tk==1)&dt.notna()
        time_errors.extend((dt[ok]-tick_s).abs().nlargest(4).tolist());all_time_deltas.extend(dt[ok].head(10).tolist())
        for field in props:
            counts[field]=counts.get(field,0)+(int(df[field].notna().sum()) if field in df else 0)
            if field in df and field in ('duck_amount','pitch','health'):
                lower,upper={'duck_amount':(0,1),'pitch':(-90,90),'health':(0,100)}[field]
                invalid_counts[field]=invalid_counts.get(field,0)+int((df[field].notna()&~df[field].between(lower,upper)).sum())
        for row in df[['player_id','name','tick']].drop_duplicates(['player_id','name']).to_dict('records'):
            name_history.setdefault(row['player_id'],{})[row['name']]=min(row['tick'],name_history.get(row['player_id'],{}).get(row['name'],row['tick']))
        total+=len(df)
        weapon_cols=[c for c in ['player_id','tick','demo_time','round_id','weapon_handle','active_weapon_name','active_weapon_ammo','recoil_index','recoil_base','accuracy_penalty','shots_fired','is_scoped'] if c in df]
        write_table(root,'weapon_states',df[weapon_cols],f'{lo:08d}');write_table(root,'player_states',df,f'{lo:08d}')
        final=df[df.tick==df.tick.max()][['player_id','name','team_num','team_clan_name','team_rounds_total']].to_dict('records')
        del df;gc.collect()
    time_ok=bool(time_errors and max(time_errors)<max(0.0005,tick_s*0.05))
    for f in props:
        caps[f].update(coverage=counts.get(f,0)/total if total else 0,non_null=counts.get(f,0),total_rows=total,invalid_range_count=invalid_counts.get(f,0),usable=counts.get(f,0)>0,semantic_status='end_of_tick observation')
    caps.update({
      'events':{'usable':len(events)>0,'event_counts':{n:len(f) for n,f in parsed},'order':'per-event-type index only; cross-type order unknown'},
      'shot_timing':{'usable':True,'quality':'estimated','resolution_seconds':tick_s,'subtick':False,'pre_event_state':False},
      'continuous_time':{'usable':time_ok,'tick_seconds':tick_s,'max_adjacent_game_time_error':max(time_errors) if time_errors else None,'source':'FileInfo ratio validated against adjacent parser game_time; no universal 64 assumption','game_time_origin':float(probe.game_time.min()) if 'game_time' in probe else None},
      'estimated_velocity':{'usable':time_ok and all(counts.get(f,0)>0 for f in ['X','Y','Z']),'quality':'estimated','dependencies':{'all_of':['X','Y','Z','continuous_time']},'semantics':'position interval average; no instantaneous/subtick claim'},
      'native_velocity':{'usable':False,'reason':'velocity aliases are parser-derived and may lag the returned row; not used','measured_alignment':velocity_alignment},
      'grounded_state':{'usable':counts.get('is_airborne',0)>0,'source':'is_airborne; cross-check with flags in evidence'},
      'visibility_geometry':{'usable':False,'reason':'无匹配地图射线/烟雾资源'},
      'effective_recoil':{'usable':False,'reason':'baseAngle 非当前生效 punch；base tick/velocity/interpolation 未还原'},
      'input_buttons':{'usable':False,'reason':'未验证网络输入语义；没有原始键盘日志'},
      'movement_accuracy':{'usable':False,'reason':'accuracy_penalty 含连续射击等混合因素，不等于纯移动误差'}})
    players['name_history_json']=players.player_id.map(lambda x:json.dumps(name_history.get(x,{}),ensure_ascii=False));write_table(root,'players',players)
    meta={'demo_hash':demo_hash,'source_name':Path(source).name,'size_bytes':Path(source).stat().st_size,'header':header,'parser':{'name':'demoparser2','version':parser_version},'normalization_version':VERSION,'protocol':header.get('network_protocol'),'container':container,'tick_seconds':tick_s,'state_rows':total,'extracted_fields':supported,'event_inventory':{'requested':EVENTS,'available':available_events,'returned':[n for n,df in parsed],'counts':{n:len(df) for n,df in parsed},'extraction_complete':True},'final_state':final,'time_contract':{'command_tick':'commands.tick','demo_tick':'player_states.tick; alias to command tick not server tick','net_tick':None,'game_time':'parser-derived time with origin offset; not recording relative','demo_time':'tick * FileInfo interval, subject to continuity checks','subtick':None,'state_semantics':'end-of-tick','event_order':'index within each event type, cross-type order unknown','command_offsets':'available only in command table; cannot map an entity/event to a byte offset'}}
    for r in rounds:r['participants_json']=json.dumps(clean(rosters.get(r['round_id'],[])),ensure_ascii=False)
    write_table(root,'rounds',pd.DataFrame(rounds))
    save(root/'fields.json',enrich_catalog(fields,VERSION,tick_s));save(root/'capabilities.json',caps);save(root/'demos.json',meta)
    return meta
