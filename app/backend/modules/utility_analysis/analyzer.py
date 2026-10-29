"""Auditable flash review. Event identity first; conservative state-change fallback.

flash_duration is a held duration value, NOT remaining blindness. Never integrate
it over ticks or use it to assert blindness at the time of a kill.
"""
from collections import Counter, defaultdict
import math

from ...core.common import check_cancel, clean, metric

MID = 'utility_analysis'


def valid_id(value):
    return str(value) if value is not None and str(value).isdigit() and str(value) != '0' else None


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def relation(thrower, target, source_team, target_team):
    if not thrower or not target:
        return 'unknown'
    if thrower == target:
        return 'self'
    if source_team not in (2, 3) or target_team not in (2, 3):
        return 'unknown'
    return 'teammate' if source_team == target_team else 'enemy'


def state_effects(flash, same_tick_flashes, rows):
    """Match an actual new state value only to a unique same-tick detonation.

    A repeated equal positive value can conceal a refresh and is deliberately
    unknown. Missing rows, pawn changes, death and gaps cannot create effects.
    """
    if len(same_tick_flashes) != 1:
        return [], '同 tick 多颗闪光爆炸，状态变化不能唯一归属'
    tick = flash['tick']
    indexed = defaultdict(dict)
    for row in rows:
        if row.get('tick') in (tick - 1, tick):
            indexed[row.get('player_id')][row['tick']] = row
    effects = []
    for pid, pair in indexed.items():
        previous, current = pair.get(tick - 1), pair.get(tick)
        if not previous or not current or not valid_id(pid):
            continue
        if not previous.get('is_alive') or not current.get('is_alive'):
            continue
        if current.get('pawn_handle') is None or previous.get('pawn_handle') != current.get('pawn_handle'):
            continue
        if current.get('team_num') not in (2, 3) or previous.get('team_num') != current.get('team_num'):
            continue
        before, after = number(previous.get('flash_duration')), number(current.get('flash_duration'))
        if before is None or after is None or before < 0 or after <= 0 or abs(after - before) <= 1e-6:
            continue
        dt = number(current.get('game_time'))
        prev_time = number(previous.get('game_time'))
        if dt is None or prev_time is None or abs(dt - prev_time - flash['tick_seconds']) > 1e-4:
            continue
        effects.append({'target_id': str(pid), 'target_name': current.get('name', str(pid)),
                        'relation': relation(flash['player_id'], str(pid), flash['team'], current.get('team_num')),
                        'tick': tick, 'duration': after, 'previous_duration': before,
                        'quality': 'estimated', 'source': 'same_tick_duration_change',
                        'reason': '相邻 tick 新正值变化与唯一同 tick 爆炸对应；不证明屏幕白度或完整受影响人数'})
    return effects, '仅收录相邻状态的新正值变化；未检测到变化不等于没有致盲'


def native_match(event, flashes):
    """Do not assign by nearest location/time. Entity identity + tick + owner."""
    entity = event.get('entityid')
    if entity is None:
        return None
    candidates = [f for f in flashes if f['entity_id'] == entity and f['tick'] == event.get('tick')]
    attacker = valid_id(event.get('attacker_steamid'))
    if attacker:
        candidates = [f for f in candidates if f['player_id'] == attacker]
    return candidates[0] if len(candidates) == 1 else None


def analyze(ctx, p, cancel, progress):
    flashes, evidence, unmatched, assistants = [], [], [], []
    deaths_by_round = {}
    inventory = ctx.meta.get('event_inventory', {})
    requested, available = set(inventory.get('requested', [])), set(inventory.get('available', []))
    complete_inventory = inventory.get('extraction_complete') is True
    detonation_available = complete_inventory and 'flashbang_detonate' in requested
    # Requested but absent from the recorded event stream cannot establish a
    # complete blind ledger. This is crucial for CS2 demos without player_blind.
    native_available = complete_inventory and 'player_blind' in requested and 'player_blind' in available
    participants = {valid_id(x.get('player_id', x.get('steamid'))) for x in clean(ctx.query('players').to_dict('records'))}
    participants.discard(None)
    unmatched_by_round = defaultdict(list)
    excluded = Counter()
    for r in ctx.rounds():
        check_cancel(cancel)
        if not r.get('complete'):
            excluded[r.get('phase', 'incomplete')] += 1
            continue
        rid = r['round_id']
        frame = ctx.query('events', round_id=rid)
        events = clean(frame.drop_duplicates('event_id').to_dict('records')) if len(frame) else []
        live = [e for e in events if e.get('in_live_round')]
        dets = [e for e in live if e.get('event_name') == 'flashbang_detonate']
        native = [e for e in live if e.get('event_name') == 'player_blind']
        deaths = [e for e in live if e.get('event_name') == 'player_death']
        deaths_by_round[rid] = deaths
        round_flashes = []
        for e in dets:
            owner = valid_id(e.get('user_steamid'))
            if owner:
                participants.add(owner)
            f = {'evidence_id': 'flash:' + e['event_id'], 'event_id': e['event_id'],
                 'round_id': rid, 'tick': int(e['tick']), 'player_id': owner or '',
                 'player_name': e.get('user_name', owner or '未知投掷者'), 'team': e.get('user_team_num'),
                 'entity_id': e.get('entityid'), 'position': {k: e.get(k) for k in ('x', 'y', 'z')},
                 'tick_seconds': ctx.meta.get('tick_seconds'), 'effects': [], 'kills': [],
                 'assessment': 'observed' if native_available else 'unknown',
                 'assessment_reason': '按原生 player_blind 与实体 ID、同 tick 唯一配对' if native_available else '缺少原生 player_blind 事件',
                 'unmatched_effect_count': 0}
            round_flashes.append(f)
        for e in native:
            f = native_match(e, round_flashes)
            duration = number(e.get('blind_duration'))
            target = valid_id(e.get('user_steamid'))
            if f is None or not target or duration is None or duration < 0:
                unmatched.append({'event_id': e['event_id'], 'round_id': rid, 'tick': e['tick'],
                                  'player_id': valid_id(e.get('attacker_steamid')), 'target_id': target,
                                  'reason': '实体 ID、同 tick、投掷者不能唯一配对，或受影响玩家/时长缺失'})
                unmatched_by_round[rid].append(e)
                continue
            event_team = number(e.get('attacker_team_num'))
            source_team = event_team if event_team in (2, 3) else f['team']
            team_conflict = event_team in (2, 3) and f['team'] in (2, 3) and event_team != f['team']
            f['effects'].append({'event_id': e['event_id'], 'target_id': target,
                                 'target_name': e.get('user_name', target), 'tick': int(e['tick']),
                                 'relation': relation(f['player_id'], target, source_team, e.get('user_team_num')),
                                 'event_team': event_team, 'detonation_team': f['team'], 'team_conflict': team_conflict,
                                 'duration': duration, 'quality': 'observed', 'source': 'player_blind',
                                 'reason': '原生致盲事件按实体 ID 与同 tick 唯一匹配'})
        by_tick = defaultdict(list)
        for f in round_flashes:
            by_tick[f['tick']].append(f)
        for f in round_flashes:
            if native_available:
                # An unpaired native event can hide the outcome for a flash;
                # never classify a zero outcome where the ledger is ambiguous.
                ambiguous = [e for e in unmatched_by_round[rid] if e.get('tick') == f['tick'] or
                             (e.get('entityid') is not None and e.get('entityid') == f['entity_id']) or
                             (e.get('entityid') is None and valid_id(e.get('attacker_steamid')) == f['player_id'])]
                if ambiguous:
                    f['assessment'] = 'unknown'
                    f['unmatched_effect_count'] = len(ambiguous)
                    f['assessment_reason'] = '同 tick、同实体或身份相关的致盲事件不能唯一配对，不能确认完整影响'
                if any(e['relation'] == 'unknown' for e in f['effects']):
                    f['assessment'] = 'unknown'
                    f['assessment_reason'] = '存在阵营关系缺失的致盲记录，敌我影响不能完整判定'
            elif f['tick_seconds']:
                states = ctx.query('player_states', start=f['tick'] - 1, end=f['tick'])
                rows = clean(states.to_dict('records')) if len(states) else []
                f['effects'], f['assessment_reason'] = state_effects(f, by_tick[f['tick']], rows)
                if f['effects']:
                    f['assessment'] = 'estimated'
            for key in ('enemy', 'teammate', 'self', 'unknown'):
                selected = [e for e in f['effects'] if e['relation'] == key and (e.get('duration') or 0) > 0]
                f[key + '_count'] = len({e['target_id'] for e in selected})
                f[key + '_duration'] = sum(e['duration'] for e in selected)
            f['recorded_effects'] = len(f['effects'])
            flashes.append(f)
        # Game-recorded assists remain valid even when no detonation is matchable.
        for d in deaths:
            pid = valid_id(d.get('assister_steamid'))
            if d.get('assistedflash') is True and pid and pid not in (d.get('attacker_steamid'), d.get('user_steamid')):
                if d.get('assister_team_num') in (2, 3) and d.get('assister_team_num') == d.get('attacker_team_num') and d.get('user_team_num') in (2, 3) and d.get('user_team_num') != d.get('attacker_team_num'):
                    assistants.append({'player_id': pid, 'round_id': rid, 'tick': d['tick'], 'event_id': d['event_id'],
                                       'target_id': d.get('user_steamid'), 'killer_id': d.get('attacker_steamid'),
                                       'target_name': d.get('user_name'), 'killer_name': d.get('attacker_name')})
                    participants.add(pid)
        progress('闪光弹分析', f'{rid}：累计 {len(flashes)} 次引爆')
    assist_refs = {}
    for assist in assistants:
        evidence_id = 'flash_assist:' + assist['event_id']
        assist['evidence_id'] = evidence_id
        assist_refs.setdefault(assist['player_id'], []).append(evidence_id)
        evidence.append({**assist, 'kind': 'flash_assist', 'weapon': 'flashbang',
                         'values': {'game_recorded_flash_assist': True},
                         'raw_field_paths': ['player_death.assistedflash', 'player_death.assister_steamid'],
                         'reason': '游戏记录的对敌闪光助攻；不强行归属到某一颗闪光'})
    for f in flashes:
        check_cancel(cancel)
        targets = {e['target_id'] for e in f['effects'] if e['relation'] == 'enemy' and (e.get('duration') or 0) > 0}
        for d in deaths_by_round[f['round_id']]:
            delta = (d['tick'] - f['tick']) * (f['tick_seconds'] or 0)
            if not 0 < delta <= p['kill_window_seconds'] or d.get('user_steamid') not in targets:
                continue
            if d.get('attacker_team_num') != f['team'] or d.get('user_team_num') == f['team']:
                continue
            f['kills'].append({'event_id': d['event_id'], 'tick': d['tick'], 'seconds_after': delta,
                               'target_id': d.get('user_steamid'), 'target_name': d.get('user_name'),
                               'killer_id': d.get('attacker_steamid'), 'killer_name': d.get('attacker_name'),
                               'game_flash_assist_for_thrower': d.get('assistedflash') is True and d.get('assister_steamid') == f['player_id']})
        reason = f['assessment_reason'] + '；闪后击杀仅为时间关联，不证明该闪导致击杀'
        evidence.append({'evidence_id': f['evidence_id'], 'round_id': f['round_id'], 'player_id': f['player_id'],
                         'tick': f['tick'], 'weapon': 'flashbang', 'kind': 'flash_review', 'team': f['team'],
                         'event_refs': [f['event_id']] + [e['event_id'] for e in f['effects'] if e.get('event_id')],
                         'values': {k: v for k, v in f.items() if k not in ('evidence_id', 'tick_seconds')},
                         'reason': reason, 'quality': f['assessment'],
                         'raw_field_paths': ['flashbang_detonate.entityid', 'flashbang_detonate.user_steamid',
                                             'player_blind.blind_duration' if native_available else 'flash_duration',
                                             'player_death.assistedflash']})
    for u in unmatched:
        evidence.append({'evidence_id': 'unmatched:' + u['event_id'], **u, 'player_id': u['player_id'] or '',
                         'kind': 'flash_unmatched', 'weapon': 'flashbang', 'values': {'unmatched': True},
                         'raw_field_paths': ['player_blind.entityid', 'player_blind.blind_duration', 'player_blind.attacker_team_num', 'player_blind.user_team_num']})
    metrics = []
    all_deaths = [d for ds in deaths_by_round.values() for d in ds]
    assist_unknown = sum(not isinstance(d.get('assistedflash'), bool) or (d.get('assistedflash') is True and
                         (not valid_id(d.get('assister_steamid')) or d.get('assister_team_num') not in (2, 3)))
                         for d in all_deaths)
    for pid in sorted(participants):
        own = [f for f in flashes if f['player_id'] == pid]
        scope = {'player_id': pid}
        refs = [f['evidence_id'] for f in own]
        metrics.append(metric(MID, 'flash_detonations', len(own) if detonation_available else None, scope,
                              eligible=len(own), quality='observed' if detonation_available else 'unknown',
                              method='完整正式回合内归属于该玩家的 flashbang_detonate 数量', sample_unit='detonation', evidence=refs))
        metrics.append(metric(MID, 'flash_assists_recorded', len(assist_refs.get(pid, [])) if not assist_unknown or assist_refs.get(pid) else None, scope,
                              eligible=len(all_deaths), unknown=assist_unknown, quality='observed' if not assist_unknown else 'unknown',
                              method='游戏 player_death.assistedflash=true 且有效同队 assister 的对敌击杀',
                              sample_unit='death_event', evidence=assist_refs.get(pid, [])))
        for rel, mid in [('enemy', 'enemy_blind_records'), ('teammate', 'teammate_blind_records'), ('self', 'self_blind_records')]:
            # A positive state-change record proves at least one associated
            # target, but cannot prove the COMPLETE target count for this flash.
            known_flashes = [f for f in own if f['assessment'] == 'observed']
            unknown = len(own) - len(known_flashes)
            value = sum(f[rel + '_count'] for f in own)
            quality = 'observed' if native_available and not unknown else 'estimated' if value else 'unknown'
            metrics.append(metric(MID, mid, value if known_flashes or value else None, scope,
                                  eligible=len(own), evaluated_count=len(known_flashes), unknown=unknown,
                                  quality=quality, method='已记录的每颗闪受影响人数之和；未判定闪不视作零；同一人可在不同闪重复计数',
                                  sample_unit='detonation', evidence=refs,
                                  limitations=['状态推导仅确认新正值变化的关联；统计可能低于实际受影响次数',
                                               'flash_duration 是记录值而非剩余致盲时间，不能由此推断屏幕白度']))
        known_enemy = [f for f in own if f['assessment'] == 'observed' or f['enemy_count'] > 0]
        metrics.append(metric(MID, 'enemy_affected_flashes', sum(f['enemy_count'] > 0 for f in own) if known_enemy else None,
                              scope, eligible=len(own), evaluated_count=len(known_enemy), unknown=len(own) - len(known_enemy),
                              quality='observed' if native_available else 'estimated' if known_enemy else 'unknown',
                              sample_unit='detonation', evidence=refs, method='至少记录到一名敌方受影响的闪光颗数；不是完整命中率'))
    unknown_count = sum(f['assessment'] != 'observed' for f in flashes)
    return {'status': 'partial' if not detonation_available or not native_available or unknown_count or unmatched or assist_unknown else 'succeeded',
            'metrics': metrics, 'evidence': evidence,
            'details': {'flash_review': flashes, 'flash_assists': assistants, 'unmatched_blind_events': unmatched,
                        'event_support': {'detonation_extracted': detonation_available, 'native_blind_available': native_available},
                        'excluded': dict(excluded), 'notes': [
                            '只统计完整正式回合内引爆。引爆次数与投出次数可能不同。',
                            '原生致盲事件按实体 ID、同 tick 与投掷者唯一配对；歧义不按最近点强配。',
                            '缺少原生 player_blind 时，仅把相邻存活同实体状态的新正值变化关联到唯一同 tick 爆炸，标为估计；未检测到变化显示未知。',
                            '记录时长不是实测全白时长，持续状态不逐 tick 累加；闪后击杀是时间关联，游戏闪助单独统计。']}}
