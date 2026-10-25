import math,json
from collections import defaultdict
import numpy as np
from ...core.common import metric,ratio,wrap,check_cancel,clean

MID='head_line'
def geometry(eye,head,pitch,yaw,radius):
    dx,dy,dz=[h-e for h,e in zip(head,eye)];distance=math.hypot(dx,dy)
    if distance<1:return None
    target=math.degrees(math.atan2(dz,distance));vertical=-pitch-target
    horizontal=wrap(yaw-math.degrees(math.atan2(dy,dx)))
    return {'vertical_error':vertical,'horizontal_error':horizontal,'target_elevation':target,'aim_elevation':-pitch,'tolerance':math.degrees(math.atan2(radius,distance)),'distance':distance,'eye':eye,'head':head}
def pose(d):return '站立' if d<.1 else '蹲伏' if d>.9 else '过渡'
def distance_bucket(d):return '<250' if d<250 else '250–500' if d<500 else '500–1000' if d<1000 else '1000–2000' if d<2000 else '≥2000'
def weighted_quantile(values,weights,q):
    if not values:return None
    order=np.argsort(values);v=np.asarray(values)[order];w=np.asarray(weights)[order];return float(v[np.searchsorted(np.cumsum(w),sum(w)*q,side='left')])

def analyze(ctx,p,cancel,progress):
    if p['window_start_ms']>=p['window_end_ms']:raise ValueError('窗口开始必须早于结束')
    dt=ctx.meta['tick_seconds'];evidence=[];groups=defaultdict(list);totals=defaultdict(float);excluded=defaultdict(int);window_count=defaultdict(int)
    if not ctx.capabilities.get('continuous_time',{}).get('usable'):return {'status':'unsupported','metrics':[],'evidence':[],'details':{'reason':'时间连续性验证失败'}}
    for r in ctx.rounds():
        if not r['complete']:continue
        check_cancel(cancel);rid=r['round_id'];s=ctx.query('player_states',round_id=rid);eng=ctx.query('engagements',round_id=rid)
        if eng.empty:continue
        engagements=eng.to_dict('records');needed=set()
        for e in engagements:
            start=e['tick']+math.ceil(p['window_start_ms']/1000/dt);end=e['tick']+math.floor(p['window_end_ms']/1000/dt)
            needed.update(range(start,end+2))
        ticks=defaultdict(list)
        for row in s[s.tick.isin(needed)].to_dict('records'):ticks[int(row['tick'])].append(row)
        for e in engagements:
            pid=e['player_id'];window_count[pid]+=1
            start=e['tick']+math.ceil(p['window_start_ms']/1000/dt);end=e['tick']+math.floor(p['window_end_ms']/1000/dt)
            totals[pid]+=max(0,end-start+1)*dt
            for t in range(start,end+1):
                rows=ticks.get(t,[]);me=next((x for x in rows if x['player_id']==pid),None)
                base={'evidence_id':f"{e['engagement_id']}:{t}",'round_id':rid,'player_id':pid,'tick':t,'end_tick':t+1,'weapon':e['weapon'],'kind':'head_geometry','window_id':e['engagement_id'],'start_time':t*dt,'end_time':(t+1)*dt,'raw_field_paths':['X','Y','Z','pitch','yaw','duck_amount','is_alive','is_airborne','flash_duration'],'sample_semantics':'same-tick end states; geometry held over one observed interval; estimated'}
                reason=None
                if not me or t<r['live_tick'] or t+1 not in ticks:reason='窗口状态或连续区间不足'
                elif not me.get('is_alive') or me.get('is_airborne') is not False:reason='死亡/空中/在地面状态未知'
                elif me.get('move_type')!=2:reason='非普通移动状态/攀爬或状态未知'
                elif me.get('is_reloading') is not False:reason='换弹/换弹状态未知'
                elif ctx.providers.weapons.get(me.get('active_weapon_name')) is None:reason='非枪械/未配置枪械'
                elif any(me.get(k) is None or not math.isfinite(float(me[k])) for k in ['X','Y','Z','pitch','yaw','duck_amount']):reason='几何字段缺失'
                points=ctx.providers.geometry.points(me,p) if me and not reason else None
                if not points and not reason:reason='姿态/眼位模型不可用'
                candidates=[]
                if not reason:
                    for other in rows:
                        if other['player_id']==pid or other.get('team_num') not in (2,3) or other['team_num']==me['team_num'] or not other.get('is_alive') or other.get('is_airborne') is not False:continue
                        if any(other.get(k) is None or not math.isfinite(float(other[k])) for k in ['X','Y','Z','duck_amount']):continue
                        other_points=ctx.providers.geometry.points(other,p)
                        if not other_points:continue
                        g=geometry(points[0],other_points[1],me['pitch'],me['yaw'],p['head_radius'])
                        if g and abs(g['horizontal_error'])<=p['horizontal_cone_deg']:
                            visibility=ctx.providers.visibility.query(ctx.meta['header'].get('map_name'),points[0],other_points[1],t)
                            if visibility['visible'] is False:continue
                            candidates.append({**g,'target_id':other['player_id'],'visibility':visibility,'self_pose':pose(me['duck_amount']),'target_pose':pose(other['duck_amount']),'self_duck':me['duck_amount'],'target_duck':other['duck_amount'],'team':int(me['team_num'])})
                if not reason and not candidates:reason='前方锥角内无有依据候选；不评价跑图'
                if reason:
                    excluded[pid]+=1;evidence.append({**base,'judgement':'unknown','reason':reason});continue
                candidates.sort(key=lambda c:(c['distance'],c['target_id']))
                chosen=candidates[0];g=chosen;state='in_band' if abs(g['vertical_error'])<=g['tolerance'] else 'high' if g['vertical_error']>0 else 'low'
                record={**base,**chosen,'candidate_ids':[c['target_id'] for c in candidates],'ambiguous_candidates':len(candidates)>1,'judgement':state,'quality':'estimated','weight_seconds':dt,'reason':'事件邻近窗口；前方锥角按距离、SteamID 确定候选；近似头位；可见性与实时致盲状态未知，不代表真实预瞄成绩','blind_state':'unknown','threshold':g['tolerance'],'values':g}
                record['distance_bucket']=distance_bucket(g['distance'])
                evidence.append(record);groups[(pid,None,None,None)].append(record);groups[(pid,g['self_pose'],g['target_pose'],None)].append(record);groups[(pid,None,None,record['distance_bucket'])].append(record)
    metrics=[]
    distributions=[]
    for (pid,sp,tp,dist),rows in groups.items():
        scope={'player_id':pid}
        if sp:scope.update(self_pose=sp,target_pose=tp)
        if dist:scope['distance_bucket']=dist
        den=sum(x['weight_seconds'] for x in rows);eligible=totals[pid] if not sp and not dist else den
        refs=[x['evidence_id'] for x in rows]
        for name,key in [('head_in_band_time','in_band'),('head_high_time','high'),('head_low_time','low')]:
            n=sum(x['weight_seconds'] for x in rows if x['judgement']==key)
            metrics.append(metric(MID,name,ratio(n,den),scope,'ratio',n=n,d=den,eligible=eligible,unknown=max(0,eligible-den),quality='estimated',sample_unit='second',evidence=refs,method='按连续观测时间加权；仅候选条件下的估计',limitations=['无地图可见性验证','头部/眼位为实验线性姿态模型','动画骨骼、攀爬/完整换弹标志不可用','多目标按距离选取，保留歧义']))
        for q in (.5,.9):
            m=metric(MID,'head_abs_error_p'+str(int(q*100)),weighted_quantile([abs(x['vertical_error']) for x in rows],[x['weight_seconds'] for x in rows],q),scope,'degrees',eligible=len(rows),quality='estimated',evidence=refs);m['aggregation']='duration_weighted_quantile';metrics.append(m)
        if not sp and not dist:
            edges=[0,.5,1,2,5,10,20,90,180]
            counts,_=np.histogram([abs(x['vertical_error']) for x in rows],bins=edges,weights=[x['weight_seconds'] for x in rows])
            distributions.append({'player_id':pid,'title':'绝对高度角误差分布（持续时间权重）','unit':'seconds','bins':[{'label':f'{edges[i]}–{edges[i+1]}°','value':float(v)} for i,v in enumerate(counts)]})
    for pid in window_count:
        if not any(k[0]==pid for k in groups):metrics.append(metric(MID,'head_in_band_time',None,{'player_id':pid},'ratio',n=0,d=0,eligible=totals[pid],unknown=totals[pid],quality='unknown',sample_unit='second',limitations=['无可评价候选窗口']))
        for mid in ['verified_head_in_band_time','unconditional_preaim']:metrics.append(metric(MID,mid,None,{'player_id':pid},'ratio',eligible=window_count[pid],unknown=window_count[pid],quality='unknown',limitations=['缺地图射线与验证头部几何/地图锚点'],method='unavailable'))
    return {'status':'partial','metrics':metrics,'evidence':evidence,'details':{'windows':dict(window_count),'distributions':distributions,'geometry_provider':ctx.providers.geometry.version,'visibility':ctx.providers.visibility.version,'verified_samples':0,'target_selection':'forward-cone then nearest distance then decimal SteamID; never victim-based','blind_state':'unknown','deprecated_parameters':{'flash_exclude_seconds':'仅兼容旧配置；flash_duration 是持久峰值，不再用于排除或推断致盲'}}}
