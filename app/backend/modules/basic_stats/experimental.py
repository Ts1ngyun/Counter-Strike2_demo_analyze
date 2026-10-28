"""Auditable estimates, not HLTV scores. No fitted win-probability model is shipped."""
from collections import Counter, defaultdict
from functools import lru_cache


@lru_cache(None)
def elimination_probability(own, opponents):
    """Chance to eliminate the other team if every next duel is an independent 50/50."""
    if own <= 0:
        return 0.0
    if opponents <= 0:
        return 1.0
    return (elimination_probability(own - 1, opponents) +
            elimination_probability(own, opponents - 1)) / 2


def preplant_swing(membership, events, round_id):
    """Signed percentage-point credit for enemy kills before the first bomb plant.

    Unknown roster/order invalidates the round, rather than imputing a 5v5 state.
    Plant-tick kills are excluded because event order within a tick is not trusted.
    Environmental/team deaths update the state but receive no player credit.
    """
    sides = {pid: s['team_num'] for pid, s in membership.items()}
    if Counter(sides.values()) != {2: 5, 3: 5}:
        return None, [], 'opening_roster_not_5v5'
    plant = min((e['tick'] for e in events if e['event_name'] == 'bomb_planted'), default=float('inf'))
    deaths = sorted((e for e in events if e['event_name'] == 'player_death' and e['tick'] < plant), key=lambda e: e['tick'])
    if any(n > 1 for n in Counter(e['tick'] for e in deaths).values()):
        return None, [], 'same_tick_death_order'
    alive = set(sides)
    scores = defaultdict(float)
    rows = []
    for e in deaths:
        victim, attacker = e.get('user_steamid'), e.get('attacker_steamid')
        if victim not in alive:
            return None, [], 'missing_or_duplicate_victim'
        if e.get('user_team_num') != sides[victim]:
            return None, [], 'team_state_conflict'
        counts = Counter(sides[pid] for pid in alive)
        if not counts[2] or not counts[3]:
            return None, [], 'death_after_elimination'
        opposing = attacker in sides and sides[attacker] != sides[victim]
        if attacker not in (None, '', '0', victim) and (attacker not in alive or e.get('attacker_team_num') != sides[attacker]):
            return None, [], 'attacker_state_unknown'
        if opposing:
            team = sides[attacker]
            before = elimination_probability(counts[team], counts[sides[victim]])
            after = elimination_probability(counts[team], counts[sides[victim]] - 1)
            delta = 100 * (after - before)
            scores[attacker] += delta
            scores[victim] -= delta
            for pid, target, signed in [(attacker, victim, delta), (victim, attacker, -delta)]:
                rows.append({'evidence_id': f"swing:{e['event_id']}:{pid}", 'round_id': round_id,
                             'player_id': pid, 'target_id': target, 'tick': e['tick'],
                             'kind': 'round_swing', 'weapon': e.get('weapon'),
                             'raw_field_paths': ['player_death', 'bomb_planted', 'team_num', 'is_alive'],
                             'quality': 'estimated', 'values': {'own_alive_before': counts[team],
                             'enemy_alive_before': counts[sides[victim]], 'attacking_team': team,
                             'attacker_probability_before': before, 'attacker_probability_after': after,
                             'signed_percentage_points': signed}, 'event_refs': [e['event_id']],
                             'reason': '下包前人数模型；每次对枪按五五开估算，击杀加分、被击杀减分。非 HLTV。'})
        alive.remove(victim)
    return scores, rows, None
