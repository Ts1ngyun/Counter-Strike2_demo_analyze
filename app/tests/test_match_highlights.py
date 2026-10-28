from copy import deepcopy
import pytest
from backend.modules.basic_stats.highlights import round_highlights
from backend.services.results import without_retired_impact


def roster():
    return {str(i): {'player_id':str(i), 'team_num':2 if i<=5 else 3, 'is_alive':True} for i in range(1,11)}


def death(tick, attacker, victim):
    return dict(event_name='player_death',event_id=f'd:{tick}:{victim}',tick=tick,
                attacker_steamid=attacker,user_steamid=victim,
                attacker_team_num=roster().get(attacker,{}).get('team_num'),
                user_team_num=roster()[victim]['team_num'],weapon='ak47',headshot=True)


def run(events, winner='T', members=None, final=None):
    dead={e['user_steamid'] for e in events}
    final=final if final is not None else [dict(s,is_alive=pid not in dead) for pid,s in roster().items()]
    return round_highlights({'round_id':'r001','end_tick':100,'winner':winner},members or roster(),events,final)


def one_v_three():
    # First two CTs die, then four Ts: player 1 now faces 8, 9, 10.
    return [death(1,'1','6'),death(2,'2','7')]+[death(i,'8',str(i-1)) for i in range(3,7)]


def test_exact_multi_kills_and_opponent_counts():
    rows=run([death(1,'1','6'),death(2,'1','7'),death(3,'1','8'),death(4,'2','3'),death(5,'0','9')])
    assert len(rows['duels'])==3
    assert [(r['player_id'],r['kills']) for r in rows['multi_kills']]==[('1',3)]
    assert all(d['headshot'] for d in rows['duels'])


def test_one_v_three_counted_once_even_after_reaching_one_v_one():
    rows=run(one_v_three()+[death(7,'1','8'),death(8,'1','9'),death(9,'1','10')])
    assert rows['clutch_unknown_reason'] is None
    own=[r for r in rows['clutches'] if r['player_id']=='1']
    assert len(own)==1 and own[0]['opponents']==3 and own[0]['outcome']=='won'
    assert own[0]['tick']==6 and own[0]['survived']
    assert rows['multi_kills'][0]['kills']==4
    assert next(r for r in rows['clutches'] if r['player_id']=='10')['outcome']=='lost'


def test_same_tick_deaths_are_atomic_no_false_one_v_two():
    events=[death(i,'1',str(i+5)) for i in range(1,4)]
    events += [death(i+3,'9',str(i+1)) for i in range(1,4)]
    events += [death(7,'1','9'),death(7,'9','5')]
    rows=run(events)
    assert sorted((r['player_id'],r['opponents']) for r in rows['clutches'])==[('1',1),('10',1)]


def test_enemy_eliminated_on_same_tick_no_new_clutch():
    events=[death(i,'1',str(i+5)) for i in range(1,5)]
    events += [death(i+4,'10',str(i+1)) for i in range(1,4)]
    events += [death(8,'1','10'),death(8,'10','5')]
    rows=run(events)
    assert not any(r['player_id']=='1' for r in rows['clutches'])


@pytest.mark.parametrize('winner,outcome',[('T','won'),('CT','lost'),(None,'unknown'),(2,'won')])
def test_round_winner_controls_outcome_including_posthumous_bomb_win(winner,outcome):
    rows=run(one_v_three()+[death(7,'8','1')],winner)
    row=next(r for r in rows['clutches'] if r['player_id']=='1')
    assert row['outcome']==outcome and not row['survived']


def test_dead_thrower_can_kill_without_invalidating_state():
    rows=run([death(1,'6','1'),dict(death(2,'1','6'),weapon='hegrenade')])
    assert rows['clutch_unknown_reason'] is None and len(rows['duels'])==2


@pytest.mark.parametrize('fault',['roster','end_missing','end_mismatch','duplicate','team'])
def test_incomplete_data_is_unknown_not_zero(fault):
    events=one_v_three();members=roster();final=None
    if fault=='roster': members.pop('10')
    if fault=='end_missing':final=[]
    if fault=='end_mismatch':final=list(roster().values())
    if fault=='duplicate':events.append(events[0])
    if fault=='team':events[0]['user_team_num']=2
    rows=run(events,members=members,final=final)
    assert rows['clutch_unknown_reason'] and rows['clutches']==[]


def test_retired_impact_projection_leaves_original_and_other_modules_intact():
    metrics=[{'metric_id':'impact','value':1.3},{'metric_id':'kast_local','value':.8}]
    original={'modules':{'basic_stats':{'metrics':metrics,'details':{'round_stats':[{'metrics':metrics}]}},'other':{'metrics':metrics}}}
    snapshot=deepcopy(original)
    projected=without_retired_impact(original)
    assert original==snapshot
    assert [m['metric_id'] for m in projected['modules']['basic_stats']['metrics']]==['kast_local']
    assert len(projected['modules']['basic_stats']['details']['round_stats'][0]['metrics'])==1
    assert projected['modules']['other'] is original['modules']['other']
    assert without_retired_impact({})=={}
