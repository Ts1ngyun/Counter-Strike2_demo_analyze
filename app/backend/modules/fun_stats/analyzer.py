"""Teammate-flash summary (fun_stats).

Summarize native teammate-blind events with traceable evidence.

Rules that the data contract forces on this module:

- Only a native ``player_blind`` event can prove that a flash blinded a
  concrete teammate. Damage events, kill events and ``flash_duration`` state
  changes are NEVER used to infer blindness.
- The blind event is authoritative for attacker, victim and both teams. A
  paired ``flashbang_detonate`` is used only as the flash instance identity and
  as a fallback when the blind event omits the thrower team. When the two teams
  disagree the native event wins and the conflict is recorded.
- A missing native event stream means unknown, never zero. Missing victim,
  missing team, missing duration or missing flash identity are counted as
  unknown per metric instead of being silently dropped.
- ``blind_duration`` is the duration granted by one blind event. It is a
  record, not screen whiteness and not remaining blindness, so it is summed
  only once per (flash, teammate) pair and never integrated over ticks.
"""
from collections import Counter, defaultdict
import math

from ...core.common import check_cancel, clean, metric

MID = 'fun_stats'
TEAMS = (2, 3)


def valid_id(value):
    """SteamID must be a decimal string; lossy floats are refused, not rounded."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        # A 17-digit SteamID cannot survive float64; a rounded value would be
        # a wrong person, so treat it as unavailable instead of guessing.
        if not math.isfinite(value) or abs(value) > 2 ** 53 or value != int(value):
            return None
        value = int(value)
    text = str(value).strip()
    return text if text.isdigit() and text != '0' else None


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def team_of(value):
    value = number(value)
    return int(value) if value in TEAMS else None


def relation(thrower, victim, thrower_team, victim_team):
    if not victim:
        return 'unknown'
    if thrower == victim:
        return 'self'
    if thrower_team is None or victim_team is None:
        return 'unknown'
    return 'teammate' if thrower_team == victim_team else 'enemy'


def problem(event, rid, reason, kind, det=None, player_id=None, target_id=None):
    return {'event_id': event.get('event_id'), 'round_id': rid,
            'tick': int(event.get('tick') or 0), 'kind': kind,
            'player_id': player_id, 'target_id': target_id,
            'entity_id': event.get('entityid'),
            'detonation_event_id': det['event_id'] if det else None, 'reason': reason}


def analyze(ctx, parameters, cancellation, progress):
    inventory = ctx.meta.get('event_inventory', {})
    requested = set(inventory.get('requested', []))
    available = set(inventory.get('available', []))
    complete = inventory.get('extraction_complete') is True
    detonation_available = complete and 'flashbang_detonate' in requested
    native_available = complete and 'player_blind' in requested and 'player_blind' in available

    participants = {valid_id(x.get('player_id', x.get('steamid')))
                    for x in clean(ctx.query('players').to_dict('records'))}
    participants.discard(None)

    records, detonations = [], []
    unattributable, ambiguous, unpaired, conflicts = [], [], [], []
    excluded = Counter()
    zero_duration = 0
    for r in ctx.rounds():
        check_cancel(cancellation)
        if not r.get('complete'):
            excluded[r.get('phase', 'incomplete')] += 1
            continue
        rid = r['round_id']
        frame = ctx.query('events', round_id=rid)
        events = clean(frame.drop_duplicates('event_id').to_dict('records')) if len(frame) else []
        live = [e for e in events if e.get('in_live_round')]

        dets = []
        for e in live:
            if e.get('event_name') != 'flashbang_detonate':
                continue
            owner = valid_id(e.get('user_steamid'))
            det = {'event_id': e.get('event_id'), 'round_id': rid, 'tick': int(e.get('tick') or 0),
                   'player_id': owner, 'player_name': e.get('user_name') or owner or '未知投掷者',
                   'team': team_of(e.get('user_team_num')), 'entity_id': e.get('entityid'),
                   'effects': [], 'assessable': native_available, 'ambiguous_events': 0}
            dets.append(det)
            detonations.append(det)
            if owner:
                participants.add(owner)
        by_tick = defaultdict(list)
        for det in dets:
            by_tick[det['tick']].append(det)

        round_problems = []
        for e in live:
            if e.get('event_name') != 'player_blind':
                continue
            check_cancel(cancellation)
            tick = int(e.get('tick') or 0)
            entity = e.get('entityid')
            victim = valid_id(e.get('user_steamid'))
            thrower = valid_id(e.get('attacker_steamid'))
            duration = number(e.get('blind_duration'))
            duration_ok = duration is not None and duration >= 0
            # An absent entity id cannot prove flash identity. Refuse the match
            # instead of treating None == None as the same entity.
            det = None
            if entity is not None and thrower is not None:
                candidates = [d for d in by_tick[tick]
                              if d['entity_id'] is not None and d['entity_id'] == entity
                              and d['player_id'] == thrower]
                det = candidates[0] if len(candidates) == 1 else None

            if thrower is None:
                entry = problem(e, rid, '缺少有效投掷者 SteamID，无法归属到任何玩家', 'invalid_thrower',
                                det=det, target_id=victim)
                unattributable.append(entry)
                round_problems.append(entry)
                continue

            participants.add(thrower)
            det_team = det['team'] if det else None
            event_team = team_of(e.get('attacker_team_num'))
            conflict = event_team is not None and det_team is not None and event_team != det_team
            # Documented rule: the native blind event owns the teams; the
            # detonation only fills a missing thrower team.
            thrower_team = event_team if event_team is not None else det_team
            victim_team = team_of(e.get('user_team_num'))
            rel = relation(thrower, victim, thrower_team, victim_team)
            identity = (('detonation', det['event_id']) if det is not None
                        else ('entity', rid, tick, entity) if entity is not None else None)
            record = {'evidence_id': 'teammate_flash:' + str(
                          e.get('event_id') or '{0}:{1}:{2}:{3}'.format(rid, tick, thrower, victim)),
                      'event_id': e.get('event_id'), 'round_id': rid, 'tick': tick,
                      'player_id': thrower, 'player_name': e.get('attacker_name') or thrower,
                      'thrower_team': thrower_team, 'event_team': event_team,
                      'detonation_team': det_team, 'team_conflict': conflict,
                      'target_id': victim, 'target_name': e.get('user_name') or (victim or '未知受影响玩家'),
                      'target_team': victim_team, 'relation': rel,
                      'duration': duration if duration_ok else None,
                      'duration_missing': not duration_ok,
                      'entity_id': entity, 'identity': identity,
                      'detonation_event_id': det['event_id'] if det else None}
            records.append(record)

            if conflict:
                conflicts.append({'event_id': e.get('event_id'), 'round_id': rid, 'tick': tick,
                                  'player_id': thrower, 'target_id': victim,
                                  'event_team': event_team, 'detonation_team': det_team,
                                  'detonation_event_id': det['event_id'],
                                  'rule': '原生致盲事件阵营优先；此处仅记录冲突，不用于推断失明'})

            if det is None and identity is not None and rel != 'unknown':
                # The record is fully classified, but an unmatched native event
                # may be the hidden outcome of a nearby detonation.
                unpaired.append(problem(e, rid, '未能与唯一闪光配对；记录按实体身份保留', 'unpaired',
                                        player_id=thrower, target_id=victim))
                round_problems.append(unpaired[-1])
            if rel == 'unknown' or identity is None:
                reason = ('受影响玩家 SteamID 缺失，不能确定是否队友' if not victim else
                          '投掷者或受影响玩家的阵营缺失，敌我关系不能判定' if identity is not None else
                          '缺少闪光实体身份且未配对，无法区分重复记录')
                entry = problem(e, rid, reason, 'ambiguous_identity' if identity is None else 'unknown_team',
                                det=det, player_id=thrower, target_id=victim)
                ambiguous.append(entry)
                round_problems.append(entry)
                continue
            if rel == 'teammate':
                if duration_ok and duration == 0:
                    zero_duration += 1
                    continue
                if det is not None:
                    det['effects'].append(record)

        if native_available:
            for det in dets:
                # An unpaired native event that could belong to this flash hides
                # its complete outcome; do not turn that into "no teammate hit".
                related = [f for f in round_problems if (
                    f.get('detonation_event_id') == det['event_id'] or
                    f['tick'] == det['tick'] or
                    (f.get('entity_id') is not None and f['entity_id'] == det['entity_id']) or
                    (f.get('entity_id') is None and f.get('player_id') == det['player_id']))]
                if related:
                    det['assessable'] = False
                    det['ambiguous_events'] = len(related)
        progress('趣味统计', '{0}：累计 {1} 条原生致盲记录'.format(rid, len(records)))

    # One effect = one flash x one teammate. Flash identity is the paired
    # detonation, else the native entity+tick; duplicates without either are
    # already unknown and never reach this ledger.
    chosen = {}
    for record in records:
        if record['relation'] != 'teammate' or record['identity'] is None:
            continue
        if record['duration'] == 0:
            continue
        key = (record['identity'], record['player_id'], record['target_id'])
        current = chosen.get(key)
        if current is None or (current['duration'] is None and record['duration'] is not None):
            chosen[key] = record
    effects = sorted(chosen.values(), key=lambda x: (x['player_id'], x['round_id'], x['tick'], x['target_id']))

    by_player = defaultdict(list)
    for record in records:
        by_player[record['player_id']].append(record)
    effects_by_player = defaultdict(list)
    for effect in effects:
        effects_by_player[effect['player_id']].append(effect)
    dets_by_player = defaultdict(list)
    for det in detonations:
        if det['player_id']:
            dets_by_player[det['player_id']].append(det)

    metrics, evidence = [], []
    for effect in effects:
        evidence.append({
            'evidence_id': effect['evidence_id'], 'round_id': effect['round_id'],
            'player_id': effect['player_id'], 'tick': effect['tick'],
            'kind': 'teammate_flash', 'weapon': 'flashbang',
            'event_refs': [x for x in (effect['event_id'], effect['detonation_event_id']) if x],
            'values': {'target_id': effect['target_id'], 'target_name': effect['target_name'],
                       'duration': effect['duration'], 'relation': effect['relation'],
                       'thrower_team': effect['thrower_team'], 'target_team': effect['target_team'],
                       'event_team': effect['event_team'], 'detonation_team': effect['detonation_team'],
                       'team_conflict': effect['team_conflict'],
                       'entity_id': effect['entity_id'],
                       'detonation_event_id': effect['detonation_event_id'],
                       'identity_kind': effect['identity'][0] if effect['identity'] else None},
            'quality': 'observed' if effect['duration'] is not None else 'estimated',
            'raw_field_paths': ['player_blind.attacker_steamid', 'player_blind.user_steamid',
                                'player_blind.user_team_num', 'player_blind.attacker_team_num',
                                'player_blind.blind_duration', 'player_blind.entityid'],
            'reason': '原生 player_blind 记录：投掷者与该玩家同队且不是本人；不使用伤害事件推断失明'})

    for pid in sorted(participants):
        own = by_player.get(pid, [])
        unknown_records = [x for x in own if x['relation'] == 'unknown' or x['identity'] is None]
        known = len(own) - len(unknown_records)
        # Unknown throwers may belong to any player: expose uncertainty, never assign effects.
        unknown_records = unknown_records + unattributable
        own_effects = effects_by_player.get(pid, [])
        teammates = {x['target_id'] for x in own_effects}
        missing_seconds = [x for x in own_effects if x['duration'] is None]
        known_seconds = [x for x in own_effects if x['duration'] is not None]
        own_dets = dets_by_player.get(pid, [])
        incidents = [d for d in own_dets if d['effects']]
        hidden = [d for d in own_dets if not d['effects'] and not d['assessable']]
        scope = {'player_id': pid}
        refs = [x['evidence_id'] for x in own_effects]
        quality = ('observed' if native_available and not unknown_records
                   else 'estimated' if own_effects else 'unknown')

        metrics.append(metric(
            MID, 'teammate_flash_effects', len(own_effects) if native_available and (own_effects or not unknown_records) else None, scope,
            eligible=len(own) + len(unattributable), evaluated_count=known, unknown=len(unknown_records),
            quality=quality, sample_unit='blind_effect', evidence=refs,
            method='原生 player_blind 中投掷者与该玩家同队、非本人的原生记录（排除已知零时长，缺失时长不影响事件计数），按（闪光身份, 受影响队友）去重',
            limitations=['未知阵营或缺失闪光身份的记录计入 unknown，不当作 0',
                         '同一颗闪光对同一名队友只计一次；同一队友在不同闪光中重复计数']))

        representatives = {}
        for effect in own_effects:
            representatives.setdefault(effect['target_id'], effect['evidence_id'])
        metrics.append(metric(
            MID, 'teammates_flashed', len(teammates) if native_available and (teammates or not unknown_records) else None, scope,
            eligible=len(own) + len(unattributable), evaluated_count=known, unknown=len(unknown_records),
            quality=quality, sample_unit='teammate', evidence=sorted(representatives.values()),
            method='被该玩家闪光致盲过的不同队友数；同一队友多次被闪只计一次',
            limitations=['阵营缺失的记录不计入队友，也不计入敌方，单独保留 unknown']))

        seconds_unknown = len(unknown_records) + len(missing_seconds)
        seconds_eligible = len(own_effects) + len(unknown_records)
        if not native_available:
            seconds_value, seconds_quality = None, 'unknown'
        elif known_seconds:
            seconds_value = round(sum(x['duration'] for x in known_seconds), 3)
            seconds_quality = 'observed' if seconds_unknown == 0 else 'estimated'
        elif seconds_unknown:
            seconds_value, seconds_quality = None, 'unknown'
        else:
            seconds_value, seconds_quality = 0.0, 'observed'
        metrics.append(metric(
            MID, 'teammate_blind_seconds', seconds_value, scope,
            unit='second', eligible=seconds_eligible, evaluated_count=len(known_seconds),
            unknown=seconds_unknown, quality=seconds_quality, sample_unit='blind_effect',
            evidence=refs,
            method='每（闪光身份, 队友）配对记录一次 blind_duration，再求和；时长缺失单独计入 unknown',
            limitations=['记录时长不是屏幕白化时长，也不是剩余致盲时间',
                         '有缺失时数值是已知下限，必须结合 unknown 与覆盖率阅读',
                         '不按 tick 累加，不能据此判断某次击杀发生时的可见状态']))

        incident_ids = {d['event_id'] for d in incidents}
        incident_refs = [x['evidence_id'] for x in own_effects if x['detonation_event_id'] in incident_ids]
        metrics.append(metric(
            MID, 'teammate_flash_incidents', len(incidents) if native_available and detonation_available and (incidents or not hidden) else None, scope,
            eligible=len(own_dets), evaluated_count=len(own_dets) - len(hidden), unknown=len(hidden),
            quality=('observed' if native_available and detonation_available and not hidden
                     else 'estimated' if incidents else 'unknown'),
            sample_unit='detonation', evidence=incident_refs,
            method='该玩家引爆的闪光中，至少致盲一名队友的颗数',
            limitations=['原生致盲事件缺失或配对歧义时不判定为没有闪到队友，计入 unknown',
                         '只统计完整正式回合内的引爆']))

    breakdown = {}
    for effect in effects:
        key = (effect['player_id'], effect['target_id'])
        item = breakdown.setdefault(key, {
            'player_id': effect['player_id'], 'player_name': effect['player_name'],
            'teammate_id': effect['target_id'], 'teammate_name': effect['target_name'],
            'effects': 0, 'seconds': 0.0, 'missing_seconds': 0, 'rounds': set()})
        item['effects'] += 1
        if effect['duration'] is None:
            item['missing_seconds'] += 1
        else:
            item['seconds'] += effect['duration']
        item['rounds'].add(effect['round_id'])
    per_teammate = [{**{k: v for k, v in item.items() if k != 'rounds'},
                     'seconds': (None if item['missing_seconds'] == item['effects'] else round(item['seconds'], 3)), 'rounds': len(item['rounds'])}
                    for item in breakdown.values()]
    per_teammate.sort(key=lambda x: (x['player_id'], -x['effects'], x['teammate_id']))

    unresolved = sum(1 for x in records if x['relation'] == 'unknown' or x['identity'] is None)
    status = 'partial' if (not native_available or not detonation_available
                           or unattributable or unresolved
                           or any(m['unknown_count'] for m in metrics)) else 'succeeded'
    notes = [
        '只使用原生 player_blind 致盲事件；伤害、击杀与状态字段不用于推断失明。',
        '缺少原生事件流、阵营或闪光身份时保留 unknown，不补零、不按最近点强配。',
        '致盲事件的阵营优先于引爆阵营；两者冲突时记录在 team_conflicts，仍按原生事件判定。',
        'blind_duration 是单次致盲的记录时长，按（闪光, 队友）求和，不按 tick 累计；缺失时只给已知下限。',
        '完整正式回合之外（热身、重开、回放结束、不完整回合）不计入。']
    return {'status': status, 'metrics': metrics, 'evidence': evidence,
            'details': {
                'teammate_flashes': [{k: v for k, v in x.items() if k != 'evidence_id'} for x in effects],
                'per_teammate': per_teammate,
                'native_blind_records': len(records),
                'zero_duration_records': zero_duration,
                'team_conflicts': conflicts,
                'unattributable_blind_events': unattributable,
                'ambiguous_blind_events': ambiguous,
                'unpaired_blind_events': unpaired,
                'unmatched_blind_events': unattributable + ambiguous + unpaired,
                'event_support': {'detonation_extracted': detonation_available,
                                  'native_blind_available': native_available},
                'excluded': dict(excluded),
                'notes': notes}}
