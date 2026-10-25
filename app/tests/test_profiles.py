import copy
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from backend.routers import profiles
from backend.core.common import metric


def fixture_result(digest='a', n=1, d=2, version='1'):
    modules = {'stop_shooting': {'status': 'partial', 'metrics': [], 'evidence': []}}
    for pid in ['111', '222']:
        m = metric('stop_shooting', 'ready_rate', n/d, {'player_id': pid}, 'ratio', n=n,d=d,eligible=d)
        m.update(algorithm_version=version, parameter_snapshot={}, identities={'provider':'same'}, definition={'title':'达标率'})
        modules['stop_shooting']['metrics'].append(m)
        modules['stop_shooting']['evidence'].append({'player_id':pid,'evidence_id':pid,'tick':10,'reason':'fixture'})
    return {'job_id':digest,'demo':{'demo_hash':digest*64,'header':{'map_name':'de_test'},'tick_seconds':.015625},
            'players':[{'player_id':p,'name':'P'+p} for p in ['111','222']], 'rounds':[], 'modules':modules}


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(profiles,'DATA',tmp_path)
    monkeypatch.setattr(profiles,'load_result',lambda jid: fixture_result(jid))
    app=FastAPI();app.include_router(profiles.router)
    return TestClient(app)


def make_profile(client):
    return client.post('/api/profiles',json={'name':'训练档案'}).json()['id']


def save(client,pid,job='a',players=None):
    return client.post(f'/api/profiles/{pid}/entries',json={'job_id':job,'player_ids':players or ['111']})


def test_multiple_ids_selected_only_and_idempotent(client):
    pid=make_profile(client)
    one=save(client,pid).json()['entries'][0]
    snap=client.get(f'/api/profiles/{pid}/entries/{one["id"]}').json()['snapshot']
    assert snap['player']['player_id']=='111'
    assert all(m['scope']['player_id']=='111' for m in snap['modules']['stop_shooting']['metrics'])
    assert all(e['player_id']=='111' for e in snap['modules']['stop_shooting']['evidence'])
    assert save(client,pid).json()['entries'][0]['action']=='already_saved'
    save(client,pid,players=['111','222','222'])
    result=client.get('/api/profiles/'+pid).json()
    assert result['distinct_demos']==1 and len(result['entries'])==2
    assert len(result['series'])==2  # Distinct IDs must not become one trend.
    assert client.get('/api/profiles').json()[0]['player_count']==2


def test_invalid_selection_atomic(client):
    pid=make_profile(client)
    assert save(client,pid,players=['111','999']).status_code==422
    assert not client.get('/api/profiles/'+pid).json()['entries']
    assert save(client,pid,players=['0']).status_code==422
    assert save(client,pid,players=['1e9']).status_code==422
    assert client.post('/api/profiles',json={'name':'  '}).status_code==422


def test_revisions_and_reversible_removal(client,monkeypatch):
    pid=make_profile(client);entry=save(client,pid).json()['entries'][0]['id']
    monkeypatch.setattr(profiles,'load_result',lambda jid:fixture_result('a',n=2,d=3))
    assert save(client,pid).json()['entries'][0]['revision']==2
    old=client.get(f'/api/profiles/{pid}/entries/{entry}?revision=1').json()
    assert old['snapshot']['modules']['stop_shooting']['metrics'][0]['value']==.5
    client.patch(f'/api/profiles/{pid}/entries/{entry}',json={'hidden':True})
    assert not client.get('/api/profiles/'+pid).json()['series']
    assert len(client.get('/api/profiles/'+pid+'?include_hidden=true').json()['hidden_entries'])==1
    client.patch(f'/api/profiles/{pid}/entries/{entry}',json={'hidden':False})
    assert len(client.get('/api/profiles/'+pid).json()['entries'])==1
    # Snapshots continue to work without original results.
    monkeypatch.setattr(profiles,'load_result',lambda jid: (_ for _ in ()).throw(RuntimeError('missing original')))
    assert client.get(f'/api/profiles/{pid}/entries/{entry}').status_code==200
    export=client.get(f'/api/profiles/{pid}/export/json').json()
    assert len(export['entries'][0]['history'])==2


def test_weighted_aggregation_versions_and_unknown(client,monkeypatch):
    pid=make_profile(client)
    save(client,pid)
    monkeypatch.setattr(profiles,'load_result',lambda jid:fixture_result('b',9,10))
    save(client,pid,'b')
    data=client.get('/api/profiles/'+pid).json()
    assert len(data['series'])==1
    assert data['series'][0]['value']==10/12
    monkeypatch.setattr(profiles,'load_result',lambda jid:fixture_result('c',9,10,version='2'))
    save(client,pid,'c')
    assert len(client.get('/api/profiles/'+pid).json()['series'])==2
    broken=fixture_result('d');broken['modules']['stop_shooting']['metrics'][0].update(value=None,numerator=None,quality='unknown')
    monkeypatch.setattr(profiles,'load_result',lambda jid:broken)
    save(client,pid,'d')
    data=client.get('/api/profiles/'+pid).json()
    assert next(s for s in data['series'] if s['algorithm_version']=='1')['value'] is None


def test_quantiles_not_averaged_and_profile_isolation(client,monkeypatch):
    pid=make_profile(client);other=make_profile(client)
    r=fixture_result();r['modules']['stop_shooting']['metrics'][0]['aggregation']='none'
    monkeypatch.setattr(profiles,'load_result',lambda jid:r)
    entry=save(client,pid).json()['entries'][0]['id']
    assert client.get('/api/profiles/'+pid).json()['series'][0]['value'] is None
    assert client.get(f'/api/profiles/{other}/entries/{entry}').status_code==404
    assert client.patch(f'/api/profiles/{other}/entries/{entry}',json={'hidden':True}).status_code==404


def test_pattern_headings_are_stable_and_occurrences_keep_specific_facts(client,monkeypatch):
    pid=make_profile(client)
    labels=[('队友在 2.34 秒后击杀原击杀者','片段内受到 2 名敌人伤害'),
            ('队友在 4.50 秒后击杀原击杀者','片段内受到 4 名敌人伤害')]
    for index,digest in enumerate(['a','b']):
        r=fixture_result(digest)
        tags=[{'code':code,'label':label,'quality':'observed'} for code,label in zip(['traded','multiple_attackers'],labels[index])]
        tags.append({'code':'future_signal','label':f'具体片段 {index}','quality':'derived'})
        r['modules']['combat_review']={'status':'succeeded','metrics':[],'evidence':[{
            'evidence_id':'combat:'+digest,'player_id':'111','algorithm_version':'1','parameter_snapshot':{},
            'tick':10+index,'round_id':'r001','reason':'；'.join(labels[index]),'tags':tags}]}
        monkeypatch.setattr(profiles,'load_result',lambda jid,result=r:result)
        assert save(client,pid,digest).status_code==200
    patterns={p['code']:p for p in client.get('/api/profiles/'+pid).json()['patterns']}
    assert patterns['traded']['label']=='队友完成补枪'
    assert patterns['multiple_attackers']['label']=='受到多名敌人伤害'
    # Unknown future codes also avoid promoting the first clip's dynamic detail to a heading.
    assert patterns['future_signal']['label']=='future_signal'
    for code,index in [('traded',0),('multiple_attackers',1)]:
        pattern=patterns[code]
        assert pattern['count']==2 and pattern['match_count']==2
        assert [o['label'] for o in pattern['occurrences']]==[pair[index] for pair in labels]
        assert all(o['label'] in o['reason'] for o in pattern['occurrences'])
