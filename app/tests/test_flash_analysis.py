import pandas as pd
import pytest

from backend.modules.utility_analysis.analyzer import analyze, native_match, state_effects


class Context:
    def __init__(self, events, states=None, native=True, extracted=True):
        self.events = events
        self.states = states or []
        self.meta = {'tick_seconds': 0.015625, 'event_inventory': {'requested': ['flashbang_detonate', 'player_blind'],
                     'available': ['player_blind'] if native else [], 'extraction_complete': extracted}}

    def rounds(self):
        return [{'round_id': 'r001', 'complete': True}]

    def query(self, table, **kwargs):
        if table == 'events':
            return pd.DataFrame(self.events)
        if table == 'players':
            return pd.DataFrame([{'player_id': str(i)} for i in (1, 2, 3)])
        if table == 'player_states':
            return pd.DataFrame([s for s in self.states if kwargs['start'] <= s['tick'] <= kwargs['end']])
        raise AssertionError(table)


def event(name, ident, **kw):
    return {'event_name': name, 'event_id': ident, 'tick': 100, 'round_id': 'r001', 'in_live_round': True, **kw}


def det(ident='det:1', **kw):
    return event('flashbang_detonate', ident, **{'entityid': 11, 'user_steamid': '1', 'user_team_num': 2, **kw})


def blind(ident='blind:1', **kw):
    return event('player_blind', ident, **{'entityid': 11, 'attacker_steamid': '1', 'user_steamid': '2', 'user_team_num': 3, 'blind_duration': 2., **kw})


def state(pid, tick, duration, **kw):
    return {'player_id': pid, 'tick': tick, 'flash_duration': duration, 'pawn_handle': 99, 'game_time': tick / 64,
            'is_alive': True, 'team_num': 3 if pid == '2' else 2, **kw}


def run(events, **kwargs):
    return analyze(Context(events, **kwargs), {'kill_window_seconds': 5}, None, lambda *a: None)


def value(result, mid, pid='1'):
    return next(m for m in result['metrics'] if m['metric_id'] == mid and m['scope']['player_id'] == pid)


def test_native_identity_enemy_friend_self_and_no_double_count():
    events = [det(), blind(), blind(), blind('blind:2', user_steamid='3', user_team_num=2), blind('blind:3', user_steamid='1', user_team_num=2)]
    result = run(events)
    flash = result['details']['flash_review'][0]
    assert flash['enemy_count'] == flash['teammate_count'] == flash['self_count'] == 1
    assert value(result, 'enemy_blind_records')['value'] == 1
    assert value(result, 'enemy_blind_records')['coverage'] == 1
    assert result['status'] == 'succeeded'


def test_native_zero_is_known_but_missing_stream_is_unknown():
    assert value(run([det()]), 'enemy_blind_records')['value'] == 0
    absent = run([det()], native=False)
    assert value(absent, 'enemy_blind_records')['value'] is None
    assert value(absent, 'enemy_blind_records')['unknown_count'] == 1
    assert absent['status'] == 'partial'


def test_old_cache_does_not_claim_zero_detonations():
    result = run([], extracted=False, native=False)
    assert value(result, 'flash_detonations')['value'] is None


def test_entity_mismatch_and_same_tick_ambiguity_stay_unknown():
    result = run([det(), blind(entityid=12)])
    assert len(result['details']['unmatched_blind_events']) == 1
    assert value(result, 'enemy_blind_records')['value'] is None
    same = run([det(), det('det:2'), blind()])
    assert all(f['assessment'] == 'unknown' and not f['effects'] for f in same['details']['flash_review'])


def test_entity_reuse_never_pairs_across_ticks():
    result = run([det(tick=99), blind()])
    assert len(result['details']['unmatched_blind_events']) == 1
    assert not result['details']['flash_review'][0]['effects']
    assert value(result, 'enemy_blind_records')['value'] is None


def test_unknown_team_does_not_create_false_zero_enemy_outcome():
    result = run([det(), blind(user_team_num=None)])
    assert value(result, 'enemy_blind_records')['value'] is None


def test_state_new_value_single_tick_estimate_not_persistent_duration_sum():
    states = [state('2', 99, 0), state('2', 100, 2.5), state('2', 101, 2.5)]
    result = run([det(), det('det:2', tick=101)], states=states, native=False)
    first, second = result['details']['flash_review']
    assert first['assessment'] == 'estimated' and first['enemy_duration'] == 2.5
    assert first['effects'][0]['previous_duration'] == 0
    assert second['assessment'] == 'unknown' and not second['effects']
    m = value(result, 'enemy_blind_records')
    assert m['value'] == 1 and m['unknown_count'] == 2 and m['coverage'] == 0
    affected = value(result, 'enemy_affected_flashes')
    assert affected['value'] == 1 and affected['coverage'] == .5


@pytest.mark.parametrize('patch', [{'pawn_handle': 100}, {'is_alive': False}, {'game_time': 8}, {'team_num': 2}, {'flash_duration': None}])
def test_discontinuity_is_not_state_effect(patch):
    result = run([det()], states=[state('2', 99, 0), state('2', 100, 2.5, **patch)] if 'flash_duration' not in patch else [state('2', 99, 0), state('2', 100, None)], native=False)
    assert not result['details']['flash_review'][0]['effects']


def test_simultaneous_detonations_never_get_nearest_state_assignment():
    result = run([det(), det('det:2', entityid=12, user_steamid='3')],
                 states=[state('2', 99, 0), state('2', 100, 3)], native=False)
    assert all(not f['effects'] for f in result['details']['flash_review'])


def test_recorded_flash_assist_distinct_from_kill_association():
    death = event('player_death', 'death:1', tick=110, user_steamid='2', user_team_num=3,
                  attacker_steamid='3', attacker_team_num=2, assister_steamid='1', assister_team_num=2, assistedflash=True)
    result = run([det(), blind(), death])
    assert value(result, 'flash_assists_recorded')['value'] == 1
    assert result['details']['flash_review'][0]['kills'][0]['game_flash_assist_for_thrower'] is True
    death['assistedflash'] = False
    result = run([det(), blind(), death])
    assert value(result, 'flash_assists_recorded')['value'] == 0
    assert len(result['details']['flash_review'][0]['kills']) == 1
    assert result['details']['flash_review'][0]['kills'][0]['game_flash_assist_for_thrower'] is False


def test_same_tick_kill_not_time_ordered_and_outside_window_excluded():
    deaths = [event('player_death', f'death:{tick}', tick=tick, user_steamid='2', user_team_num=3,
                    attacker_steamid='3', attacker_team_num=2, assistedflash=False) for tick in (100, 421)]
    result = run([det(), blind(), *deaths])
    assert not result['details']['flash_review'][0]['kills']


def test_missing_assist_field_not_zero():
    result = run([det(), event('player_death', 'death:1')])
    assert value(result, 'flash_assists_recorded')['value'] is None
    assert value(result, 'flash_assists_recorded')['unknown_count'] == 1


def test_outside_live_round_excluded_and_cancel(tmp_path):
    assert not run([det(in_live_round=False)])['details']['flash_review']
    cancel = tmp_path / 'cancel'; cancel.touch()
    with pytest.raises(InterruptedError):
        analyze(Context([det()]), {'kill_window_seconds': 5}, cancel, lambda *a: None)
