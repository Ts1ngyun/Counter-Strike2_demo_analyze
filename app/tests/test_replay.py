import json
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.routers import replay

@pytest.fixture
def replay_client(tmp_path,monkeypatch):
    root=tmp_path/'facts'/'fixture';root.mkdir(parents=True)
    result={'facts_path':str(root),'demo':{'demo_hash':'a'*64,'tick_seconds':.015625,'header':{'map_name':'de_anubis'}},
        'rounds':[{'round_id':'r001','start_tick':100,'live_tick':110,'end_tick':200}],
        'players':[{'player_id':'1','name':'A'}]}
    result_path=tmp_path/'result.json';result_path.write_text(json.dumps(result))
    monkeypatch.setattr(replay,'DATA',tmp_path)
    monkeypatch.setattr(replay.jobs,'get',lambda jid:{'result':str(result_path)} if jid=='job' else None)
    states=[{'tick':t,'round_id':'r001','player_id':'1','name':'A','X':t*2.,'Y':-t*1.,'Z':1.,
        'yaw':90.,'health':100,'is_alive':True,'team_num':2,'active_weapon_name':'AK-47'} for t in range(100,201)]
    for name,rows in [('player_states',states),('events',[{'tick':133,'round_id':'r001','event_name':'player_death','event_id':'player_death:0','event_index':0,'attacker_name':'A','user_name':'B','raw_json':'{}'}])]:
        (root/name).mkdir();pd.DataFrame(rows).to_parquet(root/name/'part.parquet',index=False)
    app=FastAPI();app.include_router(replay.router)
    return TestClient(app),tmp_path,result

def test_replay_sampling_keeps_events_and_bounds(replay_client):
    client,_,_=replay_client
    meta=client.get('/api/jobs/job/replay/meta').json()
    assert meta['bounds']['x_min']==200 and meta['map_mode']=='world_coordinates'
    response=client.get('/api/jobs/job/replay/frames?round_id=r001&start=0&end=300&step=8')
    assert response.status_code==200
    data=response.json();assert (data['start'],data['end'])==(100,200)
    assert all((s['tick']-100)%8==0 or s['tick']==200 for s in data['states'])
    assert data['states'][-1]['tick']==200
    assert data['events'][0]['tick']==133  # event remains exact even between sampled state ticks
    assert 'raw_json' not in data['events'][0]
    precise=client.get('/api/jobs/job/replay/frames?round_id=r001&start=133&end=133&step=1').json()
    assert [x['tick'] for x in precise['states']]==[133]

def test_invalid_replay_ranges(replay_client):
    client,_,_=replay_client
    for query in ['round_id=no','round_id=r001&start=400','round_id=r001&step=0']:
        assert client.get('/api/jobs/job/replay/frames?'+query).status_code in (404,422)
    assert client.get('/api/jobs/unknown/replay/meta').status_code==404

def test_bookmark_persistence_validation_and_soft_delete(replay_client):
    client,path,_=replay_client;base='/api/jobs/job/replay/bookmarks'
    item={'round_id':'r001','tick':133,'player_id':'1','title':'复盘','note':'跟进时机','lines':[[{'x':10,'y':-20},{'x':30,'y':40}]]}
    saved=client.post(base,json=item);assert saved.status_code==200
    bid=saved.json()['id'];assert client.get(base).json()['bookmarks'][0]['note']=='跟进时机'
    assert client.post(base,json={**item,'tick':300}).status_code==422
    assert client.post(base,json={**item,'player_id':'missing'}).status_code==422
    assert client.post(base,json={**item,'end_tick':120}).status_code==422
    assert client.delete(base+'/'+bid).status_code==200
    assert client.get(base).json()['bookmarks']==[]
    assert json.loads((path/'replay'/('a'*64+'.json')).read_text())['trash'][0]['id']==bid
    assert client.post(base+'/'+bid+'/restore').status_code==200
    restored=client.get(base).json()
    assert restored['bookmarks'][0]['lines']==item['lines'] and restored['trash']==[]
    assert client.delete(base+'/../../bad').status_code==404

def test_reject_fact_path_escape(replay_client,monkeypatch,tmp_path):
    client,path,r=replay_client;r['facts_path']=str(path.parent/'outside')
    (path/'result.json').write_text(json.dumps(r))
    assert client.get('/api/jobs/job/replay/meta').status_code==400
