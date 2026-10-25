"""Synthetic review scenarios and persistence boundaries; no fabricated real scores."""
import json
from pathlib import Path
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.providers import WeaponProfiles
from backend.core.registry import discover
from backend.modules.combat_review.analyzer import build_card,first_shot_status,trade_after,analyze
from backend.modules.head_line.context_windows import analyze_context_windows,phases
from backend.modules.head_line.analyzer import window_measure
from backend.modules.recoil_control.analyzer import damage_by_shot
from test_module_scenarios import Context


def event(kind='player_death',tick=100,**kw):
    return dict(event_id=kind+':'+str(tick),event_name=kind,tick=tick,player_id='2',user_steamid='2',attacker_steamid='1',
        attacker_team_num=2,user_team_num=3,round_id='r001',in_live_round=True,weapon='ak47',**kw)


def params():return discover()['combat_review']['defaults']


def test_trade_same_tick_and_wrong_team_do_not_count():
    death=event();same=event(tick=100);same.update(user_steamid='1',attacker_steamid='3',user_team_num=2,attacker_team_num=3)
    assert trade_after(death,[same],.01,5) is None
    later={**same,'tick':101,'event_id':'later'}
    assert trade_after(death,[later],.01,5)['seconds']==pytest.approx(.01)
    later['attacker_team_num']=2
    assert trade_after(death,[later],.01,5) is None


def test_positive_flash_duration_never_becomes_blind_tag():
    death=event();state=dict(tick=99,player_id='2',is_alive=True,is_reloading=True,active_weapon_name='flashbang',flash_duration=5)
    row=build_card('2',1,150,100,death,[death],[],{('2',99):state},.01,WeaponProfiles(),'r001',params())
    assert {t['code'] for t in row['tags']}=={'reload_death','utility_death'}
    assert row['distance_units'] is None and row['first_shot']['status']=='no_shot'
    assert all(t['quality']=='observed' for t in row['tags'])


def test_missing_pre_state_is_unknown_not_utility_death():
    row=build_card('2',1,150,100,event(),[],[],{},.01,WeaponProfiles(),'r001',params())
    assert row['tags']==[] and row['unknown_reasons'] and row['self_snapshot'] is None


def test_two_attackers_require_enemy_damage_not_team_damage():
    a=event('player_hurt',90,dmg_health=30);b={**a,'event_id':'hurt2','attacker_steamid':'3'}
    own={**a,'event_id':'hurt3','attacker_steamid':'4','attacker_team_num':3}
    row=build_card('2',1,150,100,event(),[a,b,own],[],{},.01,WeaponProfiles(),'r001',params())
    assert row['enemy_attacker_ids']==['1','3']
    assert [t['code'] for t in row['tags']]==['multiple_attackers']


def shot(tick=10):
    s={'is_airborne':False,'speed_xy':100}
    return dict(shot_id='fire:'+str(tick),tick=tick,player_id='1',weapon='ak47',profile_json=json.dumps({'threshold':73.1}),
        pre_json=json.dumps(s),end_json=json.dumps(s),unknown_reasons='[]',round_id='r001',is_gun=True)


def test_first_shot_speed_is_not_movement_first_qualification():
    assert first_shot_status(shot())['status']=='moving'
    s=shot();s['unknown_reasons']='["boundary"]';assert first_shot_status(s)['status']=='unknown'


def test_damage_association_ambiguous_same_tick_not_double_counted():
    hurts=[event('player_hurt',10,dmg_health=70,hitgroup=1)]
    one=damage_by_shot([shot()],hurts,WeaponProfiles())
    assert one[0]['raw_damage']==70
    two=damage_by_shot([shot(),{**shot(),'shot_id':'other'}],hurts,WeaponProfiles())
    assert all(s['raw_damage'] is None and s['damage_events']==[] for s in two)
    later=damage_by_shot([shot(9)],hurts,WeaponProfiles())
    assert later[0]['damage_events']==[]


def test_combat_round_scope_and_no_shot_episode_inside_death_window():
    ctx=Context({'events':pd.DataFrame([event()]),'shots':pd.DataFrame([{**shot(95),'player_id':'2'}])})
    result=analyze(ctx,params(),None,lambda *a:None)
    assert len(result['evidence'])==1 and result['evidence'][0]['review_type']=='death'


def states(pid='2',weapon='ak47'):
    return [dict(tick=t,player_id=pid,round_id='r001',is_alive=True,pitch=float(t%3),yaw=0,weapon_handle=1,pawn_handle=2,
        team_num=3,active_weapon_name=weapon,X=1,Y=1,Z=1) for t in range(1,201)]


def test_context_windows_keep_death_nonkill_separate_and_exclude_awp():
    ctx=Context({'events':pd.DataFrame([event()]),'player_states':pd.DataFrame(states(weapon='awp')),
        'bursts':pd.DataFrame([dict(burst_id='b',tick=150,end_tick=160,player_id='2',round_id='r001')])})
    metrics,rows=analyze_context_windows(ctx,discover()['head_line']['defaults'],None,lambda *a:None,window_measure)
    assert {e['analysis_mode'] for e in rows}=={'death_window','engagement_window'}
    assert all(e['judgement']=='excluded' for e in rows)
    assert all(m['value'] is None for m in metrics if m['unit']=='degrees')


def test_phase_window_stops_before_first_shot():
    p=phases(states(),1,100,[50,60],.01,WeaponProfiles(),window_measure)
    assert p['before_first_shot']['end_tick']==49 and p['shooting_phase']['start_tick']==50
    assert p['before_first_shot']['valid_seconds']==pytest.approx(.48)


def test_legacy_positive_flash_peak_does_not_remove_geometry():
    from backend.modules.head_line.legacy import analyze as legacy
    from test_module_scenarios import head_context
    ctx=head_context();ctx.tables['player_states']['flash_duration']=5.0
    result=legacy(ctx,discover()['head_line']['defaults'],None,lambda *a:None)
    known=[e for e in result['evidence'] if e['judgement']!='unknown']
    assert known and all(e['blind_state']=='unknown' for e in known)
    assert not any('致盲或致盲状态未知' in e['reason'] for e in result['evidence'])


def test_annotations_persist_and_do_not_cross_algorithm_version(tmp_path,monkeypatch):
    import backend.routers.combat as router
    monkeypatch.setattr(router,'DATA',tmp_path)
    result={'demo':{'demo_hash':'a'*64},'modules':{'combat_review':{'evidence':[{'evidence_id':'combat:1','algorithm_version':'1.0'}]}}}
    path=tmp_path/'result.json';path.write_text(json.dumps(result),encoding='utf8')
    from backend.core import jobs
    monkeypatch.setattr(jobs,'get',lambda jid:{'result':str(path)} if jid=='test' else None)
    app=FastAPI();app.include_router(router.router);client=TestClient(app)
    url='/api/jobs/test/combat-annotations'
    assert client.put(url,json={'evidence_id':'missing','label':'problem'}).status_code==404
    assert client.put(url,json={'evidence_id':'combat:1','label':'wrong'}).status_code==422
    assert client.put(url,json={'evidence_id':'combat:1','label':'reasonable','note':'保护队友','starred':True}).status_code==200
    assert client.get(url).json()['rows'][0]['note']=='保护队友'
    result['modules']['combat_review']['evidence'][0]['parameter_snapshot']={'before_death_seconds':3};path.write_text(json.dumps(result),encoding='utf8')
    assert client.get(url).json()['rows']==[]
    result['modules']['combat_review']['evidence'][0]['parameter_snapshot']={};path.write_text(json.dumps(result),encoding='utf8')
    assert client.get(url).json()['rows'][0]['note']=='保护队友'
    result['modules']['combat_review']['evidence'][0]['algorithm_version']='2.0';path.write_text(json.dumps(result),encoding='utf8')
    assert client.get(url).json()['rows']==[]
    assert client.get('/api/jobs/missing/combat-annotations').status_code==404
