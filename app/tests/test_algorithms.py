"""Synthetic unit sequences. Never reported as real-demo performance."""
import math,json
import numpy as np
import pandas as pd
import pytest
from backend.modules.head_line.analyzer import geometry,weighted_quantile
from backend.modules.stop_shooting.analyzer import classify_speed,movement_segment
from backend.modules.recoil_control.analyzer import residual
from backend.modules.basic_stats.analyzer import capped_damage,enemy
from backend.providers import PlayerGeometryProvider,MapGeometryProvider,VisibilityProvider
from backend.features.build import enrich
from backend.adapters.demo.parser import make_rounds
from backend.core.common import ratio,wrap,fingerprint
from backend.core.registry import discover,topo,capability_expr
from backend.core.pipeline import validated_config

@pytest.mark.parametrize('dz,pitch',[(0,0),(100,-45),(-100,45)])
def test_pitch_sign_and_elevation(dz,pitch):
    g=geometry((0,0,64),(100,0,64+dz),pitch,0,4)
    assert abs(g['vertical_error'])<1e-8
@pytest.mark.parametrize('self_duck,target_duck',[(0,0),(1,0),(0,1),(1,1),(.5,.75)])
def test_continuous_pose(self_duck,target_duck):
    provider=PlayerGeometryProvider();p={'eye_stand':64,'eye_duck':46,'head_stand':64,'head_duck':46}
    a=provider.points({'X':0,'Y':0,'Z':0,'duck_amount':self_duck},p)[0]
    b=provider.points({'X':100,'Y':0,'Z':0,'duck_amount':target_duck},p)[1]
    assert a[2]==64-18*self_duck and b[2]==64-18*target_duck
    g=geometry(a,b,0,0,4)
    assert math.isclose(g['vertical_error'],-math.degrees(math.atan2(18*(self_duck-target_duck),100)))
def test_distance_scaled_tolerance():assert geometry((0,0,64),(100,0,64),0,0,4)['tolerance']>geometry((0,0,64),(1000,0,64),0,0,4)['tolerance']
def test_behind_enemy_not_in_cone():assert abs(geometry((0,0,64),(-100,0,64),0,0,4)['horizontal_error'])==180
def test_visibility_unknown_is_not_true():assert VisibilityProvider(MapGeometryProvider()).query('map',(0,0,0),(1,1,1),1)['visible'] is None
def test_duration_not_row_count():assert weighted_quantile([0,100],[.9,.1],.5)==0
@pytest.mark.parametrize('a,b,expected',[(0,0,'ready'),(30,40,'ready'),(120,150,'moving'),(120,30,'ambiguous'),(70,70,'ambiguous'),(None,0,'unknown'),(float('nan'),0,'unknown')])
def test_speed_interval_boundaries(a,b,expected):assert classify_speed(a,b,70,5)==expected
def movement(values):return [{'tick':i+1,'interval_start_tick':i,'interval_seconds':.02,'speed_xy':v} for i,v in enumerate(values)]
def test_stationary_not_movement_first():assert movement_segment(movement([0]*30),70,1.25,.08) is None
def test_short_jitter_not_movement():assert movement_segment(movement([100,100,0,0]),70,1.25,.08) is None
def test_hysteresis_and_deceleration():
    s=movement_segment(movement([110,100,80,75,50,0]),70,1.25,.08)
    assert s['start_tick']==0 and s['end_tick']==4
def test_reversed_but_too_fast():assert classify_speed(100,110,70,5)=='moving'
def test_sparse_breaks_segment():assert movement_segment(movement([100,None,100,100]),70,1.25,.08) is None
def states(xs,ticks=None,alive=None):
    return pd.DataFrame([dict(player_id='76561190000000000',tick=(ticks or list(range(1,len(xs)+1)))[i],game_time=(ticks or list(range(1,len(xs)+1)))[i]/64,round_id='r1',X=x,Y=0,Z=0,is_alive=(alive or [True]*len(xs))[i],team_num=2) for i,x in enumerate(xs)])
def test_constant_velocity():assert enrich(states([0,1,2]),1/64).speed_xy.iloc[-1]==64
def test_respawn_no_difference():assert math.isnan(enrich(states([0,100,200],alive=[True,False,True]),1/64).speed_xy.iloc[-1])
def test_teleport_no_difference():assert math.isnan(enrich(states([0,1000]),1/64).speed_xy.iloc[-1])
def test_gap_no_difference():assert math.isnan(enrich(states([0,1],ticks=[1,65]),1/64).speed_xy.iloc[-1])
def test_misaligned_time_no_difference():
    s=states([0,1]);s.loc[1,'game_time']=9
    assert math.isnan(enrich(s,1/64).speed_xy.iloc[-1])
@pytest.mark.parametrize('factor,expected',[(-1,0),(0,2),(-2,-2)])
def test_recoil_ideal_none_over(factor,expected):
    punch=np.array([[0,0],[2,0]]);view=punch*factor
    assert residual(view,punch)[1,0]==expected
def test_target_motion_removed():
    punch=np.array([[0,0],[2,1]]);target=np.array([[0,0],[0,10]])
    assert np.allclose(residual(target-punch,punch,target),0)
def test_no_double_punch():assert np.allclose(residual([[0,0],[0,0]],[[0,0],[5,5]],view_includes_punch=True),0)
def test_wrap_yaw():assert residual([[0,179],[0,-179]],[[0,0],[0,0]])[1,1]==2
def test_missing_recoil():assert residual([[0,0]],None) is None
def test_damage_cap():assert capped_damage({'dmg_health':111,'health':0},100,1)==100
def test_damage_mismatch_unknown():assert capped_damage({'dmg_health':111,'health':50},100,1) is None
def test_same_tick_multiple_hurt_not_bullets():assert capped_damage({'dmg_health':25,'health':50},100,2) is None
@pytest.mark.parametrize('att,vic,at,vt,expected',[('1','2',2,3,True),('1','2',2,2,False),('1','1',2,2,False),(None,'2',2,3,False),('1','2',None,3,False)])
def test_enemy_filter(att,vic,at,vt,expected):assert enemy(dict(attacker_steamid=att,user_steamid=vic,attacker_team_num=at,user_team_num=vt))==expected
def event(name,t,**kw):return dict(event_name=name,tick=t,event_id=f'{name}:{t}',is_warmup_period=False,**kw)
def test_normal_pre_restart_after_end_not_restart():
    r=make_rounds([event('round_start',1,round=1),event('round_freeze_end',10),event('round_end',80,winner='CT'),event('cs_pre_restart',90)],100)
    assert r[0]['phase']=='official'
def test_restart_before_end_incomplete():
    r=make_rounds([event('round_start',1),event('round_freeze_end',10),event('cs_pre_restart',50),event('round_end',80,winner='CT')],100)
    assert r[0]['phase']=='restart'
def test_incomplete_round():assert make_rounds([event('round_start',1),event('round_freeze_end',10)],100)[0]['phase']=='incomplete'
def test_warmup():
    e=event('round_start',1);e['is_warmup_period']=True
    assert make_rounds([e,event('round_freeze_end',10),event('round_end',80,winner='CT')],100)[0]['phase']=='warmup'
def test_round_id_survives_raw_reset_and_overtime():
    ev=[]
    for i,raw in enumerate([1,2,1,25,26]):ev.extend([event('round_start',i*100+1,round=raw),event('round_freeze_end',i*100+10),event('round_end',i*100+80,winner='T')])
    r=make_rounds(ev,500);assert len(set(x['round_id'] for x in r))==5 and r[-1]['raw_round']==26
def test_zero_denominator_unknown():assert ratio(0,0) is None and ratio(5,0) is None
def test_registry_planned_empty():
    m=discover();assert set(m)=={'basic_stats','head_line','stop_shooting','recoil_control','combat_review','role_analysis','positioning_analysis','utility_analysis','fun_stats'}
    for k in ['role_analysis','positioning_analysis']:
        assert not m[k]['enabled'] and not m[k]['metric_ids'] and not m[k]['parameters_schema_body']['properties']
def test_planned_never_queued():
    with pytest.raises(ValueError):validated_config({'modules':['role_analysis']})
def test_cycle_detection():
    with pytest.raises(ValueError):topo({'a':['b'],'b':['a']})
def test_missing_dependency():
    with pytest.raises(ValueError):topo({'a':['b']})
def test_any_all_capability():
    caps={'position':{'usable':True},'native':{'usable':False}}
    assert capability_expr({'any_of':['position','native']},caps)
    assert not capability_expr({'all_of':['position','native']},caps)
def test_cache_param_and_version_invalidation():
    assert len({fingerprint({'p':p,'v':v}) for p,v in [(1,'1'),(2,'1'),(1,'2')]})==3
def test_steam_id_string_only():
    with pytest.raises(ValueError):validated_config({'players':[76561198041683378]})
def test_invalid_window():
    with pytest.raises(ValueError):validated_config({'modules':['head_line'],'parameters':{'head_line':{'window_start_ms':-50,'window_end_ms':-250}}})
