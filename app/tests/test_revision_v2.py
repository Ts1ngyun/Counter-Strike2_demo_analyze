"""Synthetic boundary fixtures; none are claimed as recorded-player results."""
import json
import math
import pandas as pd
import pytest
from backend.providers import WeaponProfiles
from backend.core.registry import discover
from backend.modules.head_line.analyzer import window_measure, kill_exclusion, analyze
from backend.modules.stop_shooting.analyzer import analyze as stop_analyze
from backend.modules.recoil_control.analyzer import sampled_trajectory
from test_module_scenarios import Context


def test_weapon_reference_and_scope():
    p=WeaponProfiles()
    assert len(p.data['profiles'])==34
    assert p.get('AK-47')['threshold']==pytest.approx(73.1)
    assert p.get('AWP',True)['threshold']==34
    assert p.get('AWP',None)['threshold'] is None
    for name in ['mp9','nova','xm1014','mag7','sawedoff','glock','revolver','cz75a','usp_silencer']:
        assert p.in_weapon_set(name,'all')
        assert not p.in_weapon_set(name,'exclude_run_and_gun')
    for name in ['ak47','m4a1','awp','ssg08','deagle','negev','m249']:
        assert p.in_weapon_set(name,'exclude_run_and_gun')
    for name in ['taser','knife','hegrenade']:assert not p.in_weapon_set(name,'all')


def aim_states(start=1,end=100):
    return [dict(tick=t,player_id='1',round_id='r001',is_alive=True,pitch=5.0,
                 yaw=0,weapon_handle=1,pawn_handle=2,team_num=2,active_weapon_name='ak47') for t in range(start,end+1)]


def test_pitch_window_robust_outlier_and_gap():
    rows=aim_states();rows[50]['pitch']=80;rows[60]['active_weapon_name']='knife'
    m=window_measure(rows,1,100,.01,WeaponProfiles())
    assert m['pitch_p95_p5']==0 and m['pitch_range']==75
    assert m['valid_seconds']==pytest.approx(.97)
    assert m['curve'][59]['view_pitch'] is None and m['curve'][60]['view_pitch'] is None
    assert m['curve'][58]['segment_id']!=m['curve'][61]['segment_id']


def death(weapon='ak47',tick=101):
    return dict(event_id='death:1',event_name='player_death',tick=tick,round_id='r001',
                attacker_steamid='1',user_steamid='2',attacker_team_num=2,user_team_num=3,
                headshot=True,weapon=weapon,in_live_round=True)


@pytest.mark.parametrize('weapon,expected',[('awp','excluded_awp'),('taser','excluded_taser'),('hegrenade','non_gun_kill'),('nova','shotgun_lethal_distance_unverified')])
def test_kill_exclusions(weapon,expected):
    status,code,info=kill_exclusion(death(weapon),WeaponProfiles(),pd.DataFrame(),[])
    assert code==expected and status in ('excluded','unknown')


def test_shotgun_observed_body_kill_not_universal_distance():
    e=death('nova');e['headshot']=False
    states=pd.DataFrame([dict(player_id='1',tick=100,X=0,Y=0,Z=0),dict(player_id='2',tick=100,X=100,Y=0,Z=0,health=100,armor_value=100)])
    h=dict(event_name='player_hurt',tick=101,user_steamid='2',attacker_steamid='1',weapon='nova',hitgroup=2,health=0,dmg_health=120)
    f=dict(event_name='weapon_fire',tick=101,player_id='1',weapon='nova')
    status,code,info=kill_exclusion(e,WeaponProfiles(),states,[h,f])
    assert code=='shotgun_body_one_shot_observed' and status=='excluded'
    assert info['distance_units']==100 and info['body_one_shot_distance_units'] is None
    assert kill_exclusion(e,WeaponProfiles(),states,[h,h,f])[0]=='unknown'


def test_kill_window_no_post_kill_and_exclusion_counts():
    rows=aim_states();rows+=aim_states(101,102)
    rows[-2]['pitch']=80;rows[-1]['pitch']=-80
    events=[death(),dict(death('awp'),event_id='death:2'),dict(death('nova'),event_id='death:3')]
    ctx=Context({'player_states':pd.DataFrame(rows),'events':pd.DataFrame(events)})
    result=analyze(ctx,discover()['head_line']['defaults'],None,lambda *a:None)
    m=next(m for m in result['metrics'] if m['metric_id']=='kill_pitch_span_p50' and 'weapon' not in m['scope'])
    assert m['value']==0 and m['evaluated_count']==1 and m['excluded_count']==1 and m['unknown_count']==1
    e=next(e for e in result['evidence'] if e['event_id']=='death:1')
    assert all(x['tick']<101 for x in e['curve']) and e['overlapping_window_ids']


@pytest.mark.parametrize('change,expected',[(None,'continuous_attack_samples'),('release','intermittent_attack_samples'),('disagree','unknown'),('missing','unknown'),('pawn','unknown')])
def test_attack_samples_not_assumed_from_shots(change,expected):
    rows=[dict(tick=t,is_alive=True,pitch=t,yaw=179 if t==1 else -179,weapon_handle=1,pawn_handle=2,FIRE=True,usercmd_buttonstate_1=1) for t in [1,2,3]]
    if change=='release':rows[1].update(FIRE=False,usercmd_buttonstate_1=0)
    if change=='disagree':rows[1]['usercmd_buttonstate_1']=0
    if change=='missing':rows.pop(1)
    if change=='pawn':rows[1]['pawn_handle']=3
    curve,status=sampled_trajectory(pd.DataFrame(rows),{'tick':1,'end_tick':3,'weapon_handle':'1'},[{'tick':1},{'tick':3}])
    assert status==expected
    assert all(x['effective_recoil'] is None for x in curve)
    if change is None:assert curve[1]['relative_yaw']==2


def test_weapon_scope_and_first_shot_denominators():
    provider=WeaponProfiles();shots=[];movement=[]
    for pid,weapon,speed in [('1','ak47',120),('2','glock',120)]:
        for t in range(40,101):movement.append(dict(player_id=pid,round_id='r001',tick=t,speed_xy=speed if t<90 else 0,interval_start_tick=t-1,interval_seconds=.01,is_airborne=False,is_alive=True,weapon_handle=10))
        for i,t in enumerate([100,105]):
            state=dict(is_airborne=False,is_alive=True,speed_xy=0,weapon_handle=10,duck_amount=0,team_num=2)
            shots.append(dict(shot_id=pid+str(t),player_id=pid,round_id='r001',tick=t,pre_json=json.dumps(state),end_json=json.dumps(state),profile_json=json.dumps(provider.get(weapon)),unknown_reasons='[]',is_gun=True,weapon=weapon,weapon_group=provider.get(weapon)['group'],weapon_handle='10',previous_fire_tick=100 if i else None,event_index=i,time_start=(t-1)*.01,time_end=t*.01))
        for t in range(101,105):movement.append(dict(player_id=pid,round_id='r001',tick=t,speed_xy=0,interval_start_tick=t-1,interval_seconds=.01,is_airborne=False,is_alive=True,weapon_handle=10))
    ctx=Context({'shots':pd.DataFrame(shots),'movement':pd.DataFrame(movement)})
    ctx.capabilities['estimated_velocity']={'usable':True}
    r=stop_analyze(ctx,discover()['stop_shooting']['defaults'],None,lambda *a:None)
    metrics=[m for m in r['metrics'] if 'weapon' not in m['scope']]
    first=next(m for m in metrics if m['scope']=={'player_id':'1','weapon_set':'all'} and m['metric_id']=='movement_to_first_shot_ready_rate')
    all_shots=next(m for m in metrics if m['scope']=={'player_id':'1','weapon_set':'all'} and m['metric_id']=='shot_stationary_ready_rate')
    assert first['denominator']==1 and all_shots['denominator']==2
    empty=next(m for m in metrics if m['scope']=={'player_id':'2','weapon_set':'exclude_run_and_gun'} and m['metric_id']=='movement_to_first_shot_ready_rate')
    assert empty['value'] is None and empty['denominator']==0
    assert all('exclude_run_and_gun' not in e['weapon_sets'] for e in r['evidence'] if e['player_id']=='2')


def test_evidence_scope_before_pagination(monkeypatch):
    from backend import main
    from fastapi.testclient import TestClient
    rows=[{'evidence_id':'a','weapon_sets':['all','exclude_run_and_gun']},{'evidence_id':'b','weapon_sets':['all']}]
    result={'modules':{'stop_shooting':{'evidence':rows,'metrics':[{'metric_id':'first','scope':{'weapon_set':'all'},'evidence_refs':['a','b']},{'metric_id':'first','scope':{'weapon_set':'exclude_run_and_gun'},'evidence_refs':['a']}]}}}
    monkeypatch.setattr(main,'result_of',lambda _:result)
    client=TestClient(main.app)
    r=client.get('/api/jobs/example/evidence/stop_shooting?metric_id=first&weapon_set=exclude_run_and_gun&limit=1').json()
    assert r['total']==1 and r['rows'][0]['evidence_id']=='a'
