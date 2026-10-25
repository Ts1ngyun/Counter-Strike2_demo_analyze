"""Explicitly synthetic module-level fixtures: no recorded-player performance."""
import json
from pathlib import Path
import pandas as pd
import pytest
from backend.providers import Providers
from backend.modules.head_line.analyzer import analyze as head_analyze
from backend.modules.recoil_control.analyzer import analyze as recoil_analyze
from backend.core.registry import discover
from backend.features.build import build,enrich
from backend.modules.basic_stats.analyzer import analyze as basic_analyze

class Context:
    def __init__(self,tables,root=None,dt=.01):
        self.tables=tables;self.root=root;self.meta={'tick_seconds':dt,'header':{'map_name':'synthetic'}}
        self.providers=Providers(self.meta);self.capabilities={'continuous_time':{'usable':True}}
    def rounds(self):return [{'round_id':'r001','complete':True,'live_tick':1,'end_tick':200}]
    def query(self,table,**filters):
        d=self.tables.get(table,pd.DataFrame()).copy()
        for field,key in [('player_id','player'),('round_id','round_id')]:
            if filters.get(key) is not None and field in d:d=d[d[field]==filters[key]]
        if 'tick' in d:
            if filters.get('start') is not None:d=d[d.tick>=filters['start']]
            if filters.get('end') is not None:d=d[d.tick<=filters['end']]
        return d

def head_context(targets=True,airborne=False,reloading=False):
    rows=[]
    for tick in range(75,97):
        for pid,x,y,team in [('1',0,0,2)]+([('2',100,10,3),('3',200,0,3)] if targets else []):
            rows.append(dict(player_id=pid,tick=tick,round_id='r001',X=x,Y=y,Z=0,pitch=0,yaw=0,duck_amount=0,team_num=team,is_alive=True,is_airborne=airborne if pid=='1' else False,is_reloading=reloading,move_type=2,flash_duration=0,active_weapon_name='ak47'))
    return Context({'player_states':pd.DataFrame(rows),'engagements':pd.DataFrame([dict(player_id='1',round_id='r001',tick=100,end_tick=110,engagement_id='synthetic-1',weapon='ak47')])})
def test_multiple_targets_select_distance_not_closest_crosshair():
    r=head_analyze(head_context(),discover()['head_line']['defaults'],None,lambda *x:None)
    known=[e for e in r['evidence'] if e['judgement']!='unknown']
    assert known and all(e['target_id']=='2' and e['ambiguous_candidates'] for e in known)
    assert all(e['visibility']['visible'] is None and e['quality']=='estimated' for e in known)
    assert all(m['value'] is None for m in r['metrics'] if m['metric_id']=='verified_head_in_band_time')
@pytest.mark.parametrize('kwargs',[{'targets':False},{'airborne':True},{'reloading':True}])
def test_no_target_air_or_reload_never_scores(kwargs):
    r=head_analyze(head_context(**kwargs),discover()['head_line']['defaults'],None,lambda *x:None)
    assert all(e['judgement']=='unknown' for e in r['evidence'])
    assert all(m['value'] is None for m in r['metrics'])

def recoil_context(hurt=False):
    shots=[]
    for i in range(4):
        s={'pitch':-i,'yaw':0,'duck_amount':0,'is_airborne':False,'speed_xy':0,'recoil_base':[i,0,0],'recoil_index':i}
        shots.append({'shot_id':str(i),'tick':10+i*5,'pre_json':json.dumps(s),'end_json':json.dumps(s)})
    return Context({'bursts':pd.DataFrame([{'burst_id':'synth','round_id':'r001','player_id':'1','tick':10,'end_tick':25,'weapon':'ak47','weapon_group':'rifle','weapon_handle':'12','shot_count':4,'shot_ids_json':json.dumps([str(i) for i in range(4)]),'ambiguous':False}]),'shots':pd.DataFrame(shots),'events':pd.DataFrame([{'event_name':'player_hurt' if hurt else 'unrelated','player_id':'1','tick':20}])})
def test_flinch_excludes_stability():
    r=recoil_analyze(recoil_context(True),discover()['recoil_control']['defaults'],None,lambda *x:None)
    assert r['evidence'][0]['judgement']=='excluded'
    assert next(m for m in r['metrics'] if m['metric_id']=='descriptive_sequences')['value']==0
def test_raw_base_never_becomes_effective_recoil():
    r=recoil_analyze(recoil_context(),discover()['recoil_control']['defaults'],None,lambda *x:None)
    assert r['evidence'][0]['judgement']=='descriptive'
    assert all(x['effective_recoil'] is None and x['residual'] is None for x in r['evidence'][0]['curve'])

@pytest.mark.parametrize('change',['reload','instance','mode','pawn'])
def test_burst_split_on_semantic_boundary(tmp_path,change):
    states=[]
    for t in range(1,20):
        states.append(dict(player_id='1',tick=t,game_time=t/64,demo_time=t/64,round_id='r001',X=0,Y=0,Z=0,team_num=2,is_alive=True,is_airborne=False,weapon_handle=10 if t<8 or change!='instance' else 11,pawn_handle=20 if t<8 or change!='pawn' else 21,burst_mode=bool(t>=8 and change=='mode'),is_reloading=bool(t==8 and change=='reload'),active_weapon_ammo=30-t if t<8 or change!='reload' else 50-t,shots_fired=t,pitch=0,yaw=0,duck_amount=0,health=100))
    ev=pd.DataFrame([dict(player_id='1',tick=t,event_name='weapon_fire',event_index=i,event_id=str(i),round_id='r001',in_live_round=True,weapon='ak47') for i,t in enumerate([5,7,9,11])])
    ctx=Context({'player_states':pd.DataFrame(states),'events':ev},tmp_path,1/64)
    build(ctx,lambda *x:None,None)
    bursts=pd.read_parquet(tmp_path/'bursts/0000.parquet')
    assert len(bursts)>=2
def test_pawn_reuse_breaks_velocity():
    s=pd.DataFrame([dict(player_id='1',tick=i+1,game_time=(i+1)/64,round_id='r1',X=i,Y=0,Z=0,is_alive=True,team_num=2,pawn_handle=i+100) for i in range(2)])
    assert pd.isna(enrich(s,1/64).iloc[1].speed_xy)

def test_basic_zero_denominators_and_kd_not_percentage():
    rows=[dict(player_id=pid,tick=t,round_id='r001',team_num=team,is_alive=(pid!='2' or t==1)) for t in [1,200] for pid,team in [('1',2),('2',3)]]
    death=dict(event_name='player_death',event_id='d:1',event_index=0,round_id='r001',tick=20,in_live_round=True,attacker_steamid='1',user_steamid='2',attacker_team_num=2,user_team_num=3,assister_steamid=None,headshot=True,weapon='ak47')
    ctx=Context({'player_states':pd.DataFrame(rows),'events':pd.DataFrame([death,death])},dt=.01)
    r=basic_analyze(ctx,{'trade_seconds':5},None,lambda *x:None)
    m={x['metric_id']:x for x in r['metrics'] if x['scope']=={'player_id':'1'}}
    assert m['kills']['value']==1 # duplicate delivery with same stable event ID
    assert m['kd']['value'] is None and m['kd']['unit']=='kills/death'
    victim={x['metric_id']:x for x in r['metrics'] if x['scope']=={'player_id':'2'}}
    assert victim['hs_kill_pct']['value'] is None and victim['kd']['value']==0
