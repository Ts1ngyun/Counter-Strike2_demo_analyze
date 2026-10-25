"""Validate the approved revision on an existing real job. Service must be running."""
import json
import sys
from collections import Counter
from pathlib import Path
import httpx
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.core.contracts import metric_validator,evidence_validator
from backend.core.context import AnalysisContext

jid=sys.argv[1]
c=httpx.Client(base_url='http://127.0.0.1:8765',trust_env=False,timeout=120)
r=c.get(f'/api/jobs/{jid}/export/json');r.raise_for_status();result=r.json()
for module in result['modules'].values():
    assert module['status'] in ('succeeded','partial'), module.get('error')
    for m in module['metrics']:metric_validator.validate(m)
    for e in module['evidence']:evidence_validator.validate(e)
stop=result['modules']['stop_shooting']
for m in stop['metrics']:
    if m['metric_id'] not in ('movement_to_first_shot_ready_rate','shot_stationary_ready_rate'):continue
    scope=m['scope']
    rows=[e for e in stop['evidence'] if e['player_id']==scope['player_id'] and scope['weapon_set'] in e['weapon_sets']
          and ('weapon' not in scope or e['weapon']==scope['weapon'])
          and ('grounded' not in scope or e['grounded']==scope['grounded'])]
    if m['metric_id']=='movement_to_first_shot_ready_rate':rows=[e for e in rows if e['movement_first_status']!='none']
    known=[e for e in rows if e['judgement'] in ('ready','moving') and
           (m['metric_id']=='shot_stationary_ready_rate' or e['movement_first_status']=='first')]
    assert m['denominator']==len(known)
    assert m['numerator']==sum(e['judgement']=='ready' for e in known)
    assert set(m['evidence_refs'])=={e['evidence_id'] for e in rows}
for e in stop['evidence']:
    if e['threshold'] is not None:
        assert abs(e['threshold']-.34*e['selected_max_speed']*e['parameter_snapshot']['threshold_scale'])<1e-8
    if 'exclude_run_and_gun' in e['weapon_sets']:
        assert e['weapon_group'] not in ('smg','shotgun')
        assert e['weapon_group']!='pistol' or e['weapon']=='deagle'
head=result['modules']['head_line'];kills=[e for e in head['evidence'] if e['kind']=='kill_aim']
assert all(e['end_tick']<e['kill_tick'] for e in kills)
assert all(e['judgement']=='excluded' for e in kills if e['weapon'] in ('awp','taser'))
ctx=AnalysisContext(result['facts_path']);events=ctx.query('events')
raw=events[(events.event_name=='player_death') & events.in_live_round.fillna(False)].drop_duplicates('event_id')
raw=raw[(raw.attacker_steamid!=raw.user_steamid) & raw.attacker_team_num.isin([2,3]) & raw.user_team_num.isin([2,3]) & (raw.attacker_team_num!=raw.user_team_num)]
assert {e['event_id'] for e in kills}==set(raw.event_id)
for e in [x for x in kills if x['judgement']=='descriptive'][:10]:
    frame=ctx.query('player_states',player=e['player_id'],start=e['tick'],end=e['end_tick'],round_id=e['round_id'])
    lookup=frame.set_index('tick')
    values=[x['view_pitch'] for x in e['curve'] if x['view_pitch'] is not None]
    assert np.isclose(e['pitch_p95_p5'],np.percentile(values,95)-np.percentile(values,5))
    for x in e['curve']:
        if x['view_pitch'] is not None:assert np.isclose(x['view_pitch'],lookup.loc[x['tick'],'pitch'])
recoil=result['modules']['recoil_control']
for e in recoil['evidence']:
    assert all(x.get('effective_recoil') is None and x.get('residual') is None for x in e['curve'])
    if e['attack_input_status']=='continuous_attack_samples':
        assert len(e['curve'])==e['end_tick']-e['tick']+1
        assert all(x['attack_sample'] is True and x['command_attack_sample'] is True for x in e['curve'])
for field,value in [('weapon_set','exclude_run_and_gun')]:
    filtered=c.get(f'/api/jobs/{jid}/evidence/stop_shooting',params={field:value,'metric_id':'movement_to_first_shot_ready_rate','limit':200}).json()
    assert all(value in e['weapon_sets'] for e in filtered['rows'])
page=c.get(f'/api/jobs/{jid}/evidence/head_line',params={'analysis_mode':'kill_window','limit':200}).json()
assert page['total']==len(kills) and all(e['kind']=='kill_aim' for e in page['rows'])
for fmt in ('csv','html'):
    export=c.get(f'/api/jobs/{jid}/export/{fmt}');export.raise_for_status()
    assert 'kill_pitch_span_p50' in export.text
assert c.get('/api/modules').json()[1]['presentation']['scope_selectors'][0]['default']=='kill_window'
report={'job_id':jid,'demo_hash':result['demo']['demo_hash'],'passed':True,
        'kill_windows':len(kills),'kill_judgements':dict(Counter(e['exclusion_code'] or e['judgement'] for e in kills)),
        'attack_input_observations':dict(Counter(e['attack_input_status'] for e in recoil['evidence'])),
        'metrics':sum(len(m['metrics']) for m in result['modules'].values()),
        'evidence':sum(len(m['evidence']) for m in result['modules'].values()),'performance':result['performance'],
        'limitations':['one real demo only','no real shotgun or taser kill in this fixture; covered by synthetic boundary tests','shotgun general lethal distance remains uncalibrated']}
(ROOT/'docs/revision-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
