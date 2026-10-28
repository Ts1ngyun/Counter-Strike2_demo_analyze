import numpy as np
import pandas as pd
import pytest
from backend.adapters.demo.parser import make_rounds, finalize_round_scores, score_total
from backend.modules.head_line.analyzer import window_measure
from backend.modules.basic_stats.analyzer import analyze
from backend.providers import WeaponProfiles
from test_algorithms import event
from test_revision_v2 import aim_states
from test_module_scenarios import Context

def round_events():
    return [event('round_start',1),event('round_freeze_end',10),event('round_end',80,winner=3)]

@pytest.mark.parametrize('weapon',['knife','weapon_knife_karambit','bayonet','ak47',None])
@pytest.mark.parametrize('delta',[0,1])
def test_score_not_weapon_decides(weapon,delta):
    rounds=make_rounds(round_events()+[event('player_death',30,weapon=weapon)],100)
    r=finalize_round_scores(rounds,{'r001':{'before':0,'after':delta,'after_tick':99}})[0]
    assert r['complete']==(delta==1)
    assert r['phase']==('official' if delta==1 else 'unscored')

@pytest.mark.parametrize('before,after,phase',[(None,1,'score_unknown'),(5,0,'score_reset'),(5,7,'score_ambiguous')])
def test_score_missing_reset_jump(before,after,phase):
    r=finalize_round_scores(make_rounds(round_events(),100),{'r001':{'before':before,'after':after,'after_tick':99}})[0]
    assert not r['complete'] and r['phase']==phase

def test_score_snapshots_sides_and_inconsistency():
    assert score_total([{'team_num':2,'team_rounds_total':6},{'team_num':3,'team_rounds_total':7}])==13
    assert score_total([{'team_num':2,'team_rounds_total':7},{'team_num':3,'team_rounds_total':6}])==13
    assert score_total([{'team_num':2,'team_rounds_total':6}]) is None
    assert score_total([{'team_num':2,'team_rounds_total':6},{'team_num':2,'team_rounds_total':7},{'team_num':3,'team_rounds_total':7}]) is None

def test_three_unscored_faceit_rounds_not_counted():
    events=[];snapshots={}
    for i in range(4):
        events.extend([event('round_start',i*100+1),event('round_freeze_end',i*100+10),event('round_end',i*100+80,winner=3)])
        snapshots[f'r{i+1:03d}']={'before':0,'after':int(i==3),'after_tick':i*100+99}
    rounds=finalize_round_scores(make_rounds(events,400),snapshots)
    assert [r['round_id'] for r in rounds if r['complete']]==['r004']

def test_unknown_warmup_and_numpy_flag():
    ev=round_events();ev[0]['is_warmup_period']=None
    assert make_rounds(ev,100)[0]['phase']=='unknown'
    ev[0]['is_warmup_period']=np.bool_(False)
    assert make_rounds(ev,100)[0]['complete']
    ev[1]['is_warmup_period']=True
    assert make_rounds(ev,100)[0]['phase']=='warmup'

def test_float_ticks_endpoint_and_threshold():
    rows=aim_states(1,51);rows[-1]['pitch']=25.25
    m=window_measure(rows,1.0,51.0,.01,WeaponProfiles())
    assert m['valid_seconds']==.5
    assert m['curve'][-1]['tick']==51 and m['pitch_range']==20.25
    assert m['sample_count']==51
    with pytest.raises(ValueError):window_measure(rows,1.5,51,.01,WeaponProfiles())

def test_nonfinite_pitch_never_filled():
    rows=aim_states(1,4);rows[1]['pitch']=float('nan')
    m=window_measure(rows,1.,4.,.01,WeaponProfiles())
    assert m['curve'][0]['view_pitch'] is None
    assert m['valid_seconds']==.01

def test_round_metrics_separate_and_sum():
    class Rounds(Context):
        def rounds(self):return [dict(round_id=f'r00{i}',complete=True,live_tick=i*100,end_tick=i*100+50) for i in [1,2]]
    states=[dict(player_id=pid,round_id=f'r00{i}',tick=t,team_num=team,is_alive=True) for i in [1,2] for t in [i*100,i*100+50] for pid,team in [('1',2),('2',3)]]
    events=[dict(event_name='player_death',event_id=f'd:{i}',round_id=f'r00{i}',tick=i*100+20,in_live_round=True,attacker_steamid='1',user_steamid='2',attacker_team_num=2,user_team_num=3,weapon='ak47') for i in [1,2]]
    r=analyze(Rounds({'events':pd.DataFrame(events),'player_states':pd.DataFrame(states)}),{'trade_seconds':5},None,lambda *a:None)
    rows=r['details']['round_stats']
    assert len(rows)==4
    assert sum(x['values'].get('kills',0) for x in rows if x['player_id']=='1')==2
    assert all('round_id' not in m['scope'] for m in r['metrics'])
    assert all(m['evidence_refs']==[f"{row['round_id']}:{row['player_id']}"] for row in rows for m in row['metrics'])

def test_round_stats_api_filters_and_old_result(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    result={'modules':{'basic_stats':{'details':{'round_stats_schema_version':1,'round_stats':[{'round_id':'r001','player_id':'1'},{'round_id':'r002','player_id':'1'}]}}}}
    monkeypatch.setattr(main,'result_of',lambda jid:result)
    client=TestClient(main.app)
    response=client.get('/api/jobs/synthetic/round-stats?round_id=r002&player=1')
    assert response.status_code==200 and response.json()['rows']==[{'round_id':'r002','player_id':'1'}]
    assert len(result['modules']['basic_stats']['details']['round_stats'])==2
    result['modules']['basic_stats']['details']={}
    assert client.get('/api/jobs/synthetic/round-stats').status_code==409
