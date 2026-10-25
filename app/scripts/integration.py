"""Real-demo HTTP integration: upload, bad-file isolation, dedupe, cancel, cache."""
import json,time,sys,struct
from pathlib import Path
import httpx

app=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]);out=app/'docs'/'integration.json'
client=httpx.Client(base_url='http://127.0.0.1:8765',timeout=600,trust_env=False)
log={'source':str(source),'test_kind':'one_real_demo_plus_duplicate_and_synthetic_corrupt_container','started':time.time()}
def upload(name=None,config=None):
    with source.open('rb') as f:r=client.post('/api/upload',files={'file':(name or source.name,f,'application/octet-stream')},data={'config':json.dumps(config or {})})
    r.raise_for_status();return r.json()
def get(jid):return next(j for j in client.get('/api/jobs').json() if j['id']==jid)
def wait(jid):
    last=None;deadline=time.time()+900
    while time.time()<deadline:
        j=get(jid)
        if j['stage']!=last:print(jid[:6],j['status'],j['stage'],flush=True);last=j['stage']
        if j['status'] not in ('queued','running'):return j
        time.sleep(.3)
    raise TimeoutError(jid)

cancelled=upload();deadline=time.time()+30
while time.time()<deadline:
    snapshot=get(cancelled['id'])
    if snapshot['status']=='running' and snapshot['stage'] in ('高频状态','共享特征','模块分析'):break
    time.sleep(.05)
log['cancel_stage']=snapshot['stage']
t=time.perf_counter();client.post(f"/api/jobs/{cancelled['id']}/cancel").raise_for_status();log['cancel']=wait(cancelled['id']);log['cancel_seconds']=time.perf_counter()-t
assert log['cancel']['status']=='cancelled'
bad=client.post('/api/upload',files={'file':('truncated-test.dem',b'PBDEMS2\0'+struct.pack('<II',0,0)+bytes([7,1,50])+b'xx','application/octet-stream')}).json()
first=upload();second=upload(name='duplicate-validation.dem')
log['uploads']=[bad,first,second];log['batch_jobs']=[wait(j['id']) for j in [bad,first,second]]
assert log['batch_jobs'][0]['status']=='failed'
assert all(j['status'] in ('partial','succeeded') for j in log['batch_jobs'][1:])
assert second['duplicate']
full=client.get(f"/api/jobs/{first['id']}/export/json").json();cached=client.get(f"/api/jobs/{second['id']}/export/json").json()
assert full['demo']['header']['map_name']=='de_anubis' and len(full['players'])==10
assert len([r for r in full['rounds'] if r['complete']])==20
assert {x['team_clan_name']:x['team_rounds_total'] for x in full['demo']['final_state']}=={'Team Falcons':13,'TYLOO':7}
assert full['capabilities']['events']['event_counts']['player_death']==132
assert full['capabilities']['events']['event_counts']['player_hurt']==504
assert full['capabilities']['events']['event_counts']['weapon_fire']==2276
assert cached['performance']['facts_cache_hit'] and all(m['cache_hit'] for m in cached['modules'].values())
for fmt in ['json','csv','html']:
    r=client.get(f"/api/jobs/{first['id']}/export/{fmt}");r.raise_for_status();assert len(r.content)>100
    (app/'docs'/('sample-report.'+fmt)).write_bytes(r.content) if fmt=='html' else None
log['performance']=full['performance'];log['cached_performance']=cached['performance'];log['validated_job_id']=first['id'];log['duplicate_job_id']=second['id'];log['facts_path']=full['facts_path']
log['counts']={mid:{'metrics':len(m['metrics']),'evidence':len(m['evidence']),'status':m['status']} for mid,m in full['modules'].items()}
# Parameter change should reuse facts and unaffected module results.
cfg=full['config'];cfg['parameters']['stop_shooting']['threshold_scale']=1.05
changed=client.post(f"/api/jobs/{first['id']}/retry",json=cfg).json();log['parameter_recompute_job']=wait(changed['id'])
changed_result=client.get(f"/api/jobs/{changed['id']}/export/json").json()
assert changed_result['performance']['facts_cache_hit']
assert not changed_result['modules']['stop_shooting']['cache_hit']
assert all(v['cache_hit'] for k,v in changed_result['modules'].items() if k!='stop_shooting')
log['parameter_recompute_performance']=changed_result['performance']
agg=client.post('/api/aggregate',json={'job_ids':[first['id'],second['id']]}).json();assert agg['distinct_demos']==1
log['deduplicated_aggregate_demos']=agg['distinct_demos'];log['elapsed_seconds']=time.time()-log['started']
out.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(log,ensure_ascii=False),flush=True)
