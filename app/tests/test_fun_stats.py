"""Synthetic boundary tests for fun_stats teammate-flash summary.

Rules under test: native player_blind only, no damage inference, unknown never
becomes zero, per-metric unknown/coverage, flash identity requires a valid
entity or detonation, native team wins over detonation team, and agreement with
the flash module's teammate ledger on the same fixture.
"""
import pandas as pd
import pytest

from backend.modules.fun_stats.analyzer import analyze
from backend.modules.utility_analysis.analyzer import analyze as flash_analyze


class Context:
    def __init__(self, events, native=True, extracted=True, rounds=None):
        self.events = events
        self.rounds_data = rounds or [{'round_id': 'r001', 'complete': True}]
        self.meta = {'tick_seconds': 0.015625, 'event_inventory': {
            'requested': ['flashbang_detonate', 'player_blind'],
            'available': ['player_blind'] if native else [],
            'extraction_complete': extracted}}

    def rounds(self):
        return [{'phase': 'live', **r} for r in self.rounds_data]

    def query(self, table, **kwargs):
        if table == 'events':
            rows = self.events
            if kwargs.get('round_id'):
                rows = [e for e in rows if e['round_id'] == kwargs['round_id']]
            return pd.DataFrame(rows)
        if table == 'players':
            return pd.DataFrame([{'player_id': str(i)} for i in (1, 2, 3, 4)])
        raise AssertionError(table)


def event(name, ident, tick=100, rid='r001', **kw):
    return {'event_name': name, 'event_id': ident, 'tick': tick, 'round_id': rid,
            'in_live_round': True, **kw}


def det(ident='det:1', tick=100, entity=11, owner='1', team=2, rid='r001'):
    return event('flashbang_detonate', ident, tick=tick, rid=rid,
                 **{'entityid': entity, 'user_steamid': owner, 'user_team_num': team})


def blind(ident='blind:1', tick=100, entity=11, thrower='1', victim='2',
          thrower_team=2, victim_team=2, duration=2.0, rid='r001'):
    return event('player_blind', ident, tick=tick, rid=rid, **{
        'entityid': entity, 'attacker_steamid': thrower, 'attacker_team_num': thrower_team,
        'user_steamid': victim, 'user_team_num': victim_team, 'blind_duration': duration})


def run(events, **kwargs):
    return analyze(Context(events, **kwargs), {}, None, lambda *a: None)


def value(result, mid, pid='1'):
    return next(m for m in result['metrics'] if m['metric_id'] == mid and m['scope']['player_id'] == pid)


def test_teammate_effect_counts_targets_and_seconds():
    result = run([det(),
                  blind('blind:1', victim='2', victim_team=2, duration=2.0),
                  blind('blind:2', victim='3', victim_team=3, duration=1.5)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] == 1 and effects['quality'] == 'observed'
    assert value(result, 'teammates_flashed')['value'] == 1
    assert value(result, 'teammate_blind_seconds')['value'] == 2.0
    assert value(result, 'teammate_flash_incidents')['value'] == 1
    assert result['status'] == 'succeeded'


def test_enemy_blind_does_not_become_teammate_effect():
    result = run([det(), blind(victim='3', victim_team=3)])
    assert value(result, 'teammate_flash_effects')['value'] == 0
    assert value(result, 'teammates_flashed')['value'] == 0
    assert value(result, 'teammate_blind_seconds')['value'] == 0


def test_self_flash_is_not_a_teammate_flash():
    result = run([det(), blind(victim='1', victim_team=2)])
    assert value(result, 'teammate_flash_effects')['value'] == 0
    assert value(result, 'teammates_flashed')['value'] == 0


def test_two_flashes_by_same_teammate_count_twice_but_one_teammate():
    result = run([det(), blind('blind:1', tick=100, entity=11, duration=2.0),
                  det('det:2', tick=200, entity=12), blind('blind:2', tick=200, entity=12, duration=1.0)])
    assert value(result, 'teammate_flash_effects')['value'] == 2
    assert value(result, 'teammates_flashed')['value'] == 1
    assert value(result, 'teammate_blind_seconds')['value'] == 3.0
    assert value(result, 'teammate_flash_incidents')['value'] == 2


def test_duplicate_native_record_for_same_pair_counts_once():
    result = run([det(),
                  blind('blind:1', victim='2', duration=2.0),
                  blind('blind:2', victim='2', duration=2.0)])
    assert value(result, 'teammate_flash_effects')['value'] == 1
    assert result['details']['native_blind_records'] == 2


def test_duplicate_events_without_detonation_dedupe_by_entity_identity():
    # Review item 3: two event ids for the same tick/entity/thrower/victim must
    # not count as two flashes or four seconds.
    result = run([blind('blind:1', tick=100, entity=99, duration=2.0),
                  blind('blind:2', tick=100, entity=99, duration=2.0)])
    assert value(result, 'teammate_flash_effects')['value'] == 1
    assert value(result, 'teammate_blind_seconds')['value'] == 2.0
    assert len(result['details']['unpaired_blind_events']) == 2


def test_missing_native_stream_is_unknown_not_zero():
    result = run([det()], native=False)
    for mid in ('teammate_flash_effects', 'teammates_flashed',
                'teammate_blind_seconds', 'teammate_flash_incidents'):
        metric = value(result, mid)
        assert metric['value'] is None, mid
        assert metric['quality'] == 'unknown', mid
    assert result['status'] == 'partial'
    assert result['details']['event_support']['native_blind_available'] is False


def test_zero_is_kept_when_native_stream_is_complete():
    result = run([det()])
    metric = value(result, 'teammate_flash_effects')
    assert metric['value'] == 0 and metric['quality'] == 'observed'
    assert result['status'] == 'succeeded'


def test_unknown_team_is_not_counted_as_teammate_and_stays_unknown():
    result = run([det(), blind(victim='2', victim_team=None)])
    metric = value(result, 'teammate_flash_effects')
    assert metric['value'] is None
    assert metric['unknown_count'] == 1 and metric['coverage'] == 0
    assert result['status'] == 'partial'
    assert result['details']['unmatched_blind_events'][0]['reason'].startswith('投掷者或受影响玩家')


def test_unknown_team_also_marks_seconds_unknown():
    result = run([det(), blind(victim='2', victim_team=None)])
    seconds = value(result, 'teammate_blind_seconds')
    assert seconds['value'] is None
    assert seconds['unknown_count'] == 1 and seconds['coverage'] == 0


def test_missing_duration_keeps_effect_but_seconds_unknown():
    # Review item 1: duration=None must not produce 0/observed/unknown_count=0.
    result = run([det(), blind(duration=None)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] == 1 and effects['unknown_count'] == 0
    seconds = value(result, 'teammate_blind_seconds')
    assert seconds['value'] is None
    assert seconds['unknown_count'] == 1 and seconds['coverage'] == 0
    assert seconds['quality'] == 'unknown'
    assert result['status'] == 'partial'


def test_partially_known_seconds_is_a_lower_bound_with_coverage():
    result = run([det(), blind('blind:1', tick=100, entity=11, duration=2.0),
                  det('det:2', tick=200, entity=12), blind('blind:2', tick=200, entity=12, duration=None)])
    seconds = value(result, 'teammate_blind_seconds')
    assert seconds['value'] == 2.0
    assert seconds['unknown_count'] == 1 and seconds['coverage'] == 0.5
    assert seconds['quality'] == 'estimated'
    assert any('已知下限' in x for x in seconds['limitations'])


def test_invalid_victim_is_unknown_for_known_thrower():
    result = run([det(), blind(victim=None)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] is None and effects['unknown_count'] == 1
    assert effects['coverage'] == 0
    seconds = value(result, 'teammate_blind_seconds')
    assert seconds['value'] is None and seconds['unknown_count'] == 1
    assert result['status'] == 'partial'


def test_invalid_thrower_is_global_and_not_attributed_to_a_player():
    result = run([det(), blind(thrower=None)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] is None and effects['unknown_count'] == 1
    assert len(result['details']['unattributable_blind_events']) == 1
    assert result['status'] == 'partial'


def test_thrower_team_falls_back_to_detonation_when_event_omits_it():
    result = run([det(team=2), blind(thrower_team=None, victim_team=2)])
    assert value(result, 'teammate_flash_effects')['value'] == 1
    assert not result['details']['team_conflicts']


def test_null_entity_ids_never_pair():
    # Review item 2: None == None must not be treated as the same entity.
    result = run([det(entity=None), blind(entity=None)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] is None and effects['unknown_count'] == 1
    incident = value(result, 'teammate_flash_incidents')
    assert incident['value'] is None and incident['unknown_count'] == 1
    assert result['status'] == 'partial'


def test_unpaired_blind_still_counts_effect_but_not_incident():
    result = run([det(entity=11), blind(entity=99, victim_team=2)])
    assert value(result, 'teammate_flash_effects')['value'] == 1
    incident = value(result, 'teammate_flash_incidents')
    assert incident['value'] is None and incident['unknown_count'] == 1
    assert result['status'] == 'partial'


def test_team_conflict_prefers_native_event_and_is_recorded():
    # Review item 4: detonation team 3, native blind teams 2. The native event
    # wins, so this IS a teammate flash, and the conflict is logged.
    result = run([det(team=3), blind(thrower_team=2, victim_team=2)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] == 1 and effects['coverage'] == 1
    conflicts = result['details']['team_conflicts']
    assert len(conflicts) == 1 and conflicts[0]['event_team'] == 2 and conflicts[0]['detonation_team'] == 3
    assert result['evidence'][0]['values']['team_conflict'] is True
    assert result['status'] == 'succeeded'


def test_team_conflict_agrees_with_flash_module():
    events = [det(team=3), blind(thrower_team=2, victim_team=2)]
    ours = run(events)
    theirs = flash_analyze(Context(events), {'kill_window_seconds': 5}, None, lambda *a: None)
    mate = next(m for m in theirs['metrics']
                if m['metric_id'] == 'teammate_blind_records' and m['scope']['player_id'] == '1')
    # Both modules prefer the native event team, falling back only when absent.
    assert mate['value'] == 1
    assert value(ours, 'teammate_flash_effects')['value'] == 1


def test_zero_duration_blind_is_not_an_effect():
    result = run([det(), blind(duration=0.0)])
    assert value(result, 'teammate_flash_effects')['value'] == 0
    assert result['details']['zero_duration_records'] == 1


def test_only_complete_rounds_are_counted():
    rounds = [{'round_id': 'r001', 'complete': True}, {'round_id': 'r002', 'complete': False, 'phase': 'warmup'}]
    events = [det(), blind(victim='2'),
              det('det:2', rid='r002', tick=300, entity=21),
              blind('blind:2', rid='r002', tick=300, entity=21, victim='2')]
    result = run(events, rounds=rounds)
    assert result['details']['excluded'] == {'warmup': 1}
    assert value(result, 'teammate_flash_effects')['value'] == 1


def test_evidence_points_back_to_native_event_and_fields():
    result = run([det(), blind(victim='2')])
    evidence = result['evidence'][0]
    assert evidence['kind'] == 'teammate_flash'
    assert evidence['event_refs'] == ['blind:1', 'det:1']
    assert evidence['values']['target_id'] == '2'
    assert 'player_blind.blind_duration' in evidence['raw_field_paths']
    metric = value(result, 'teammate_flash_effects')
    assert metric['evidence_refs'] == [evidence['evidence_id']]


def test_per_teammate_summary_lists_seconds_and_rounds():
    result = run([det(), blind(victim='2', duration=2.0)])
    row = result['details']['per_teammate'][0]
    assert row['player_id'] == '1' and row['teammate_id'] == '2'
    assert row['effects'] == 1 and row['seconds'] == 2.0 and row['rounds'] == 1


def test_cancellation_is_honoured(tmp_path):
    cancel = tmp_path / 'cancel'
    cancel.touch()
    with pytest.raises(InterruptedError):
        analyze(Context([det()]), {}, cancel, lambda *a: None)


def test_agrees_with_flash_module_teammate_ledger():
    events = [det(),
              blind('blind:1', victim='2', victim_team=2, duration=2.0),
              blind('blind:2', victim='3', victim_team=2, duration=1.0)]
    ours = run(events)
    theirs = flash_analyze(Context(events), {'kill_window_seconds': 5}, None, lambda *a: None)
    mate = next(m for m in theirs['metrics']
                if m['metric_id'] == 'teammate_blind_records' and m['scope']['player_id'] == '1')
    assert value(ours, 'teammate_flash_effects')['value'] == mate['value'] == 2
    assert value(ours, 'teammate_blind_seconds')['value'] == 3.0


def test_duplicate_effects_never_leave_dangling_metric_evidence():
    result = run([det(), blind('a', duration=None), blind('b', duration=2.0)])
    ids = {e['evidence_id'] for e in result['evidence']}
    assert len(ids) == 1
    for metric in result['metrics']:
        assert set(metric['evidence_refs']) <= ids


def test_missing_seconds_breakdown_is_null():
    result = run([det(), blind(duration=None)])
    assert result['details']['per_teammate'][0]['seconds'] is None


def test_unknown_thrower_preserves_known_lower_bound():
    result = run([det(), blind('a'), blind('b', thrower=None)])
    effects = value(result, 'teammate_flash_effects')
    assert effects['value'] == 1 and effects['quality'] == 'estimated'
    assert effects['unknown_count'] == 1 and effects['coverage'] == 0.5
    assert len(result['evidence']) == 1


def test_utility_conflict_is_visible_in_effect():
    result = flash_analyze(Context([det(team=3), blind(thrower_team=2)]),
                           {'kill_window_seconds': 5}, None, lambda *a: None)
    effect = result['details']['flash_review'][0]['effects'][0]
    assert effect['team_conflict'] is True and effect['event_team'] == 2
    assert effect['relation'] == 'teammate'
