"""Independent event-window cross-check using direct parser calls, not module code."""
import json,sys,math
from pathlib import Path
import pandas as pd
from demoparser2 import DemoParser
ROOT=Path(__file__).resolve().parents[1]
run=json.loads((ROOT/'docs/integration.json').read_text(encoding='utf-8'))
data=json.loads((ROOT/'data/results'/run['validated_job_id']/'result.json').read_text(encoding='utf-8'))
p=DemoParser(sys.argv[1]);events=dict(p.parse_events(['player_death','player_hurt','weapon_fire','round_freeze_end','round_end'],player=['team_num','health'],other=['game_time']))
deaths=events['player_death'];ends=events['round_end'];freezes=events['round_freeze_end']
windows=[]
for t in freezes.tick:
    candidates=ends[(ends.tick>t)&ends.winner.notna()]
    if len(candidates):windows.append((int(t),int(candidates.tick.min())))
live=deaths.apply(lambda e:any(a<=e.tick<=b for a,b in windows),axis=1)
enemy=(deaths.attacker_steamid!=deaths.user_steamid)&deaths.attacker_team_num.isin([2,3])&deaths.user_team_num.isin([2,3])&(deaths.attacker_team_num!=deaths.user_team_num)
counts=deaths[live&enemy].groupby('attacker_steamid').size().to_dict()
actual={m['scope']['player_id']:m['value'] for m in data['modules']['basic_stats']['metrics'] if m['metric_id']=='kills' and len(m['scope'])==1}
assert all(actual.get(str(pid),0)==n for pid,n in counts.items())
sample_ticks=[int(x) for x in deaths.tick.iloc[:3]]
states=p.parse_ticks(['X','Y','Z','pitch','yaw','health','is_alive','game_time','duck_amount'],ticks=sorted(set(t+d for t in sample_ticks for d in [-2,-1,0,1])))
states['steamid']=states.steamid.astype(str)
reviews=[]
for t in sample_ticks:
    e=deaths[deaths.tick==t].iloc[0];victim=e.user_steamid;rows=states[(states.steamid==victim)&states.tick.between(t-1,t)]
    assert rows[rows.tick==t].iloc[0].health==0 and not rows[rows.tick==t].iloc[0].is_alive
    reviews.append({'tick':t,'attacker':e.attacker_name,'victim':e.user_name,'weapon':e.weapon,'headshot':bool(e.headshot),'event_attached_user_health':int(e.user_health),'states':json.loads(rows.to_json(orient='records'))})
assert reviews[0]['tick']==2909 and reviews[0]['attacker']=='Jee' and reviews[0]['victim']=='TeSeS' and reviews[0]['event_attached_user_health']==100
# Independent speed and geometric arithmetic from saved evidence values.
speed_reviews=[]
for e in [e for e in data['modules']['stop_shooting']['evidence'] if e['judgement'] in ('ready','moving')][:6]:
    a,b=e['values']['pre'],e['values']['end'];v=math.hypot(b['X']-a['X'],b['Y']-a['Y'])/(b['game_time']-a['game_time']);assert abs(v-b['speed_xy'])<1e-5
    speed_reviews.append({'tick':e['tick'],'computed_speed':v,'saved_speed':b['speed_xy'],'judgement':e['judgement']})
geometry_reviews=[]
for e in [x for x in data['modules']['head_line']['evidence'] if x.get('eye')][:6]:
    eye,head=e['eye'],e['head'];target=math.degrees(math.atan2(head[2]-eye[2],math.hypot(head[0]-eye[0],head[1]-eye[1])))
    assert abs(target-e['target_elevation'])<1e-8 and e['quality']=='estimated'
    geometry_reviews.append({'tick':e['tick'],'target_angle':target,'vertical_error':e['vertical_error'],'visibility':e['visibility']})
assert all(point['effective_recoil'] is None and point['residual'] is None for e in data['modules']['recoil_control']['evidence'] for point in e['curve'])
report={'job_id':run['validated_job_id'],'independent_enemy_kills':counts,'sum_kills':sum(counts.values()),'raw_deaths':len(deaths),'out_of_live_deaths':int((~live).sum()),'in_live_non_enemy_deaths':int((live&~enemy).sum()),'death_windows':reviews,'position_speed_checks':speed_reviews,'geometry_checks':geometry_reviews,'effective_recoil_remains_null':True,'limits':'Independent arithmetic and parser queries; same underlying parser, not an independently implemented Source2 decoder.'}
(ROOT/'docs/event_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['death_windows','geometry_checks','position_speed_checks']},ensure_ascii=False))
