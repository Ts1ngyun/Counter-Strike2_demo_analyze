"""Opponent kills, exact per-round multi-kills and last-alive situations."""
from collections import Counter
from itertools import groupby


def round_highlights(round_info, membership, events, end_states):
    rid = round_info['round_id']
    sides = {pid: row['team_num'] for pid, row in membership.items()}
    deaths = sorted((e for e in events if e['event_name'] == 'player_death'), key=lambda e: (e['tick'], e['event_id']))
    duels = []
    for e in deaths:
        a, v = e.get('attacker_steamid'), e.get('user_steamid')
        if a in sides and v in sides and sides[a] != sides[v] and e.get('attacker_team_num') == sides[a] and e.get('user_team_num') == sides[v]:
            duels.append({'round_id': rid, 'tick': e['tick'], 'attacker_id': a,
                          'victim_id': v, 'weapon': e.get('weapon'), 'headshot': e.get('headshot') is True,
                          'event_id': e['event_id']})
    count = Counter(e['attacker_id'] for e in duels)
    multi = [{'round_id': rid, 'player_id': pid, 'kills': kills,
              'tick': min(e['tick'] for e in duels if e['attacker_id'] == pid),
              'event_refs': [e['event_id'] for e in duels if e['attacker_id'] == pid]}
             for pid, kills in sorted(count.items()) if kills >= 2]

    def unknown(reason):
        return {'duels': duels, 'multi_kills': multi, 'clutches': [], 'clutch_unknown_reason': reason}

    if Counter(sides.values()) != {2: 5, 3: 5}:
        return unknown('开局存活名单不完整')
    alive = set(sides)
    candidates = {}
    for tick, group in groupby(deaths, key=lambda e: e['tick']):
        batch = list(group)
        victims = [e.get('user_steamid') for e in batch]
        if len(victims) != len(set(victims)) or any(v not in alive for v in victims):
            return unknown('死亡记录缺失或重复')
        for e in batch:
            a, v = e.get('attacker_steamid'), e['user_steamid']
            if e.get('user_team_num') != sides[v]:
                return unknown('阵营记录不一致')
            # Grenades can kill after their thrower dies. Only validate identity/team.
            if a not in (None, '', '0', v) and (a not in sides or e.get('attacker_team_num') != sides[a]):
                return unknown('攻击者状态不明')
        # No invented ordering: the whole tick is one simultaneous state change.
        alive.difference_update(victims)
        for side in (2, 3):
            own = sorted(pid for pid in alive if sides[pid] == side)
            opponents = sorted(pid for pid in alive if sides[pid] != side)
            if len(own) == 1 and opponents and side not in candidates:
                candidates[side] = {'round_id': rid, 'player_id': own[0], 'team': side,
                                    'opponents': len(opponents), 'opponent_ids': opponents,
                                    'tick': tick, 'end_tick': round_info['end_tick']}
    final = {row['player_id']: row for row in end_states if row['player_id'] in sides}
    if any(pid not in final or final[pid].get('is_alive') is None for pid in sides):
        return unknown('缺少回合结束时的存活状态')
    if any(bool(final[pid]['is_alive']) != (pid in alive) for pid in sides):
        return unknown('存活状态与死亡记录不一致')
    winner = {'T': 2, 'CT': 3}.get(round_info.get('winner'), round_info.get('winner'))
    for side, row in candidates.items():
        row['outcome'] = ('won' if winner == side else 'lost') if winner in (2, 3) else 'unknown'
        row['survived'] = row['player_id'] in alive
        row['event_refs'] = [e['event_id'] for e in deaths if e['tick'] >= row['tick']]
    return {'duels': duels, 'multi_kills': multi, 'clutches': list(candidates.values()), 'clutch_unknown_reason': None}
