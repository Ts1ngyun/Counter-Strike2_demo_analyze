"""Synthetic checks for the explicitly non-HLTV, preplant estimate."""
import pytest
import pandas as pd
from backend.modules.basic_stats.experimental import elimination_probability, preplant_swing
from backend.modules.basic_stats.analyzer import analyze
from test_module_scenarios import Context


def roster():
    return {str(i): {'player_id': str(i), 'team_num': 2 if i <= 5 else 3, 'is_alive': True} for i in range(1, 11)}


def kill(tick=10, attacker='1', victim='6'):
    return dict(event_name='player_death', event_id=f'{tick}:{victim}', tick=tick,
                attacker_steamid=attacker, user_steamid=victim,
                attacker_team_num=roster().get(attacker,{}).get('team_num'),
                user_team_num=roster()[victim]['team_num'], round_id='r001', in_live_round=True)


def test_probability_symmetry_and_boundaries():
    for a in range(1,6):
        for b in range(1,6):
            assert elimination_probability(a,b)+elimination_probability(b,a)==pytest.approx(1)
            assert elimination_probability(a,b-1)>=elimination_probability(a,b)
    assert elimination_probability(1,1)==.5
    assert elimination_probability(5,4)==pytest.approx(.63671875)
    assert elimination_probability(0,5)==0
    assert elimination_probability(5,0)==1


def test_kill_credit_is_signed_balanced_and_auditable():
    scores, rows, error=preplant_swing(roster(),[kill()],'r001')
    assert error is None and scores['1']==pytest.approx(13.671875)
    assert scores['6']==-scores['1'] and sum(scores.values())==0
    assert len(rows)==2 and rows[0]['event_refs']==['10:6']
    from backend.core.contracts import evidence_validator
    for row in rows:
        evidence_validator.validate({**row,'demo_hash':'a'*64,'start_time':.1,'end_time':.1,
            'native_resolution_seconds':.01,'subtick':None,'source_sequence':None,
            'parameter_snapshot':{},'algorithm_version':'1.2.0'})


def test_plant_tick_and_after_plant_do_not_score():
    scores, rows, error=preplant_swing(roster(),[kill(9),dict(event_name='bomb_planted',tick=10),kill(10,victim='7'),kill(11,victim='8')],'r001')
    assert error is None and len(rows)==2
    assert scores['1']==pytest.approx(13.671875)


@pytest.mark.parametrize('events,reason',[
    ([kill(),kill(victim='7')],'same_tick_death_order'),
    ([kill(),kill(11)],'missing_or_duplicate_victim'),
    ([kill(),kill(11,attacker='6',victim='2')],'attacker_state_unknown'),
    ([dict(kill(),user_team_num=2)],'team_state_conflict'),
])
def test_unreliable_round_never_partially_scores(events,reason):
    scores,rows,error=preplant_swing(roster(),events,'r001')
    assert scores is None and rows==[] and error==reason


def test_roster_unknown_is_not_zero():
    members=roster();members.pop('10')
    assert preplant_swing(members,[],'r001')[0] is None


def test_world_death_updates_population_without_giving_credit():
    world=dict(kill(9),attacker_steamid='0',attacker_team_num=None)
    scores,rows,error=preplant_swing(roster(),[world,kill(10,victim='7')],'r001')
    expected=100*(elimination_probability(5,3)-elimination_probability(5,4))
    assert error is None and scores['1']==pytest.approx(expected) and len(rows)==2


def test_module_integration_evidence_and_round_metrics():
    states=[dict(s,tick=t,round_id='r001') for s in roster().values() for t in [1,200]]
    result=analyze(Context({'player_states':pd.DataFrame(states),'events':pd.DataFrame([kill()])}),{'trade_seconds':5},None,lambda *a:None)
    metric=next(m for m in result['metrics'] if m['metric_id']=='round_swing' and m['scope']=={'player_id':'1'})
    assert metric['value']==pytest.approx(13.671875) and metric['coverage']==1
    assert metric['quality']=='estimated' and metric['unit']=='pp/round'
    assert any(ref.startswith('swing:') for ref in metric['evidence_refs'])
    assert all(m['metric_id']!='impact' for m in result['metrics'])
    available={e['evidence_id'] for e in result['evidence']}
    assert set(metric['evidence_refs'])<=available
    row=next(r for r in result['details']['round_stats'] if r['player_id']=='1')
    assert next(m['value'] for m in row['metrics'] if m['metric_id']=='round_swing')==metric['value']
