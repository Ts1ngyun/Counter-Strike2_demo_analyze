"""Explicit multi-player local archives; selected-player snapshots survive job cleanup."""
import json
import sqlite3
import time
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from ..core.common import DATA, dumps, fingerprint, read_json
from ..services.results import load_result

router = APIRouter(prefix='/api/profiles', tags=['personal archives'])

# Aggregate headings describe a category; per-clip durations/counts belong to occurrences.
PATTERN_LABELS = {
    'reload_death': '死亡前相邻采样正在换弹',
    'utility_death': '死亡前相邻采样手持道具',
    'multiple_attackers': '受到多名敌人伤害',
    'moving_first_shot': '片段首枪地速高于参考阈值',
    'blind_event': '片段内出现致盲事件',
    'traded': '队友完成补枪',
}


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / 'profiles.sqlite', timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''
      CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,note TEXT NOT NULL,created REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,demo_hash TEXT NOT NULL,
        player_id TEXT NOT NULL,job_id TEXT NOT NULL,saved REAL NOT NULL,revision INTEGER NOT NULL,
        signature TEXT NOT NULL,snapshot TEXT NOT NULL,hidden INTEGER NOT NULL DEFAULT 0,
        UNIQUE(profile_id,demo_hash,player_id));
      CREATE TABLE IF NOT EXISTS revisions(entry_id TEXT NOT NULL,revision INTEGER NOT NULL,saved REAL NOT NULL,
        snapshot TEXT NOT NULL,PRIMARY KEY(entry_id,revision));
    ''')
    if 'summary' not in {r['name'] for r in con.execute('PRAGMA table_info(entries)')}:
        con.execute('ALTER TABLE entries ADD COLUMN summary TEXT')
        con.commit()
    return con


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    note: str = Field(default='', max_length=2000)


class SaveInput(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    player_ids: list[str] = Field(min_length=1, max_length=64)


class VisibilityInput(BaseModel):
    hidden: bool


def require_profile(con, profile_id):
    row = con.execute('SELECT * FROM profiles WHERE id=?', (profile_id,)).fetchone()
    if not row:
        raise HTTPException(404, '存档不存在')
    return dict(row)


def player_snapshot(result, player_id):
    player = next((p for p in result['players'] if str(p['player_id']) == player_id), None)
    if not player:
        raise HTTPException(422, '所选 SteamID 不在这场比赛中')
    modules = {}
    for mid, module in result['modules'].items():
        metrics = [m for m in module.get('metrics', []) if m.get('scope', {}).get('player_id') == player_id]
        evidence = [e for e in module.get('evidence', []) if e.get('player_id') == player_id]
        modules[mid] = {'status': module.get('status'), 'metrics': metrics, 'evidence': evidence}
    if not any(m['metrics'] or m['evidence'] for m in modules.values()):
        raise HTTPException(422, '该玩家没有可保存的分析数据；请先为这个 ID 完成分析')
    # Deliberately omit full facts paths and unrelated players' metrics.
    annotations = []
    database = DATA / 'review' / 'annotations.sqlite3'
    if database.exists():
        keys = {(e['evidence_id'], fingerprint([e.get('algorithm_version','unknown'),e.get('parameter_snapshot',{})]))
                for e in modules.get('combat_review', {}).get('evidence', [])}
        con = sqlite3.connect(database)
        con.row_factory = sqlite3.Row
        try:
            annotations = [dict(r) for r in con.execute('SELECT * FROM annotations WHERE demo_hash=?', (result['demo']['demo_hash'],))
                           if (r['evidence_id'], r['version']) in keys]
        finally:
            con.close()
    bookmark_path = DATA / 'replay' / (result['demo']['demo_hash'] + '.json')
    all_bookmarks = read_json(bookmark_path).get('bookmarks', []) if bookmark_path.exists() else []
    bookmarks = [b for b in all_bookmarks if b.get('player_id') == player_id]
    shared_bookmarks = [b for b in all_bookmarks if b.get('player_id') in (None, '')]
    return {'format_version': 1, 'contract_version': result.get('contract_version', 1),
            'player': player, 'demo_hash': result['demo']['demo_hash'],
            'map_name': result['demo'].get('header', {}).get('map_name'),
            'patch_version': result['demo'].get('header', {}).get('patch_version'),
            'tick_seconds': result['demo'].get('tick_seconds'), 'rounds': result.get('rounds', []),
            'modules': modules, 'source_job_id': result.get('job_id'), 'review_annotations':annotations,'bookmarks':bookmarks,'shared_bookmarks':shared_bookmarks,
            'limitations': ['保存的是所选玩家的指标与证据快照；2D 回放仍需要原任务事实缓存。',
                            '存档时间不是比赛发生时间；不同 SteamID、参数和算法版本不混合统计。']}


def compact_summary(snapshot):
    """Keep trend reads independent of the size of archived high-frequency curves."""
    modules = {}
    for mid, module in snapshot['modules'].items():
        metrics = []
        for metric in module['metrics']:
            item = {k:v for k,v in metric.items() if k not in ('evidence_refs','identities','definition','limitations','method')}
            item['definition'] = {'title':metric.get('definition',{}).get('title')}
            item['comparison_key'] = metric_key(mid, metric, snapshot)
            metrics.append(item)
        evidence = [{k:e.get(k) for k in ('evidence_id','tags','algorithm_version','parameter_snapshot','tick','round_id','reason')}
                    for e in module.get('evidence',[]) if mid == 'combat_review']
        modules[mid] = {'metrics':metrics,'evidence':evidence}
    return {**{k:snapshot.get(k) for k in ('player','map_name','patch_version','contract_version')},'modules':modules}


@router.get('')
def list_profiles():
    with connect() as con:
        profiles = [dict(r) for r in con.execute('SELECT * FROM profiles ORDER BY created DESC')]
        for profile in profiles:
            rows = con.execute('SELECT demo_hash,player_id FROM entries WHERE profile_id=? AND hidden=0', (profile['id'],)).fetchall()
            profile.update(player_count=len({r['player_id'] for r in rows}), match_count=len({r['demo_hash'] for r in rows}), entry_count=len(rows))
    return profiles


@router.post('')
def create_profile(body: ProfileInput):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, '请输入存档名称')
    profile = {'id': uuid.uuid4().hex, 'name': name, 'note': body.note, 'created': time.time()}
    with connect() as con:
        con.execute('INSERT INTO profiles VALUES(:id,:name,:note,:created)', profile)
    return profile


@router.patch('/{profile_id}')
def rename_profile(profile_id: str, body: ProfileInput):
    if not body.name.strip():
        raise HTTPException(422, '请输入存档名称')
    with connect() as con:
        require_profile(con, profile_id)
        con.execute('UPDATE profiles SET name=?,note=? WHERE id=?', (body.name.strip(), body.note, profile_id))
        return require_profile(con, profile_id)


@router.post('/{profile_id}/entries')
def save_players(profile_id: str, body: SaveInput):
    player_ids = list(dict.fromkeys(body.player_ids))
    if any(not p.isascii() or not p.isdecimal() or p == '0' for p in player_ids):
        raise HTTPException(422, 'SteamID 必须为非零十进制字符串')
    result = load_result(body.job_id)
    snapshots = [(pid, player_snapshot(result, pid)) for pid in player_ids]
    outcome = []
    with connect() as con:
        require_profile(con, profile_id)
        con.execute('BEGIN IMMEDIATE')
        for pid, snapshot in snapshots:
            stable = {k: v for k, v in snapshot.items() if k != 'source_job_id'}
            signature = fingerprint(stable)
            previous = con.execute('SELECT * FROM entries WHERE profile_id=? AND demo_hash=? AND player_id=?',
                                   (profile_id, snapshot['demo_hash'], pid)).fetchone()
            now = time.time()
            if previous and previous['signature'] == signature:
                con.execute('UPDATE entries SET hidden=0,job_id=? WHERE id=?', (body.job_id, previous['id']))
                outcome.append({'player_id': pid, 'id': previous['id'], 'action': 'already_saved', 'revision': previous['revision']})
                continue
            entry_id = previous['id'] if previous else uuid.uuid4().hex
            revision = previous['revision'] + 1 if previous else 1
            encoded = dumps(snapshot)
            summary = dumps(compact_summary(snapshot))
            if previous:
                con.execute('UPDATE entries SET job_id=?,saved=?,revision=?,signature=?,snapshot=?,summary=?,hidden=0 WHERE id=?',
                            (body.job_id, now, revision, signature, encoded, summary, entry_id))
            else:
                con.execute('INSERT INTO entries(id,profile_id,demo_hash,player_id,job_id,saved,revision,signature,snapshot,hidden,summary) VALUES(?,?,?,?,?,?,?,?,?,0,?)',
                            (entry_id, profile_id, snapshot['demo_hash'], pid, body.job_id, now, revision, signature, encoded, summary))
            con.execute('INSERT INTO revisions VALUES(?,?,?,?)', (entry_id, revision, now, encoded))
            outcome.append({'player_id': pid, 'id': entry_id, 'action': 'updated' if previous else 'saved', 'revision': revision})
    return {'entries': outcome, 'message': '只收录已选择的玩家；同场同 ID 只计一次，重算版本保留历史快照。'}


def metric_key(mid, metric, snapshot):
    identities = metric.get('identities', {})
    facts = identities.get('facts') or {}
    features = identities.get('features') or {}
    implementation = {k: identities.get(k) for k in ('module_code','common_code','manifest_hash','contract')}
    implementation['facts'] = {k: facts.get(k) for k in ('parser','normalization','adapter_code')}
    implementation['features'] = {k: features.get(k) for k in ('version','code','provider')}
    return fingerprint([mid, metric['metric_id'], metric.get('scope', {}), metric.get('algorithm_version'),
                        metric.get('parameter_snapshot', {}), identities.get('provider'), snapshot.get('contract_version'),implementation])


def summarize(rows, map_name=None, player_id=None):
    entries, groups, players, patterns = [], {}, {}, {}
    for row in rows:
        snapshot = json.loads(row['summary'])
        pid = row['player_id']
        players[pid] = snapshot['player'].get('name') or pid
        if player_id and pid != player_id or map_name and snapshot.get('map_name') != map_name:
            continue
        entry = {k: row[k] for k in ['id', 'player_id', 'demo_hash', 'job_id', 'saved', 'revision', 'hidden']}
        entry.update(map_name=snapshot.get('map_name'), player_name=players[pid], patch_version=snapshot.get('patch_version'))
        entries.append(entry)
        for mid, module in snapshot['modules'].items():
            if mid == 'combat_review':
                seen = set()
                for evidence in module.get('evidence', []):
                    if evidence.get('evidence_id') in seen:
                        continue
                    seen.add(evidence.get('evidence_id'))
                    for tag in {t['code']: t for t in evidence.get('tags', []) if t.get('code')}.values():
                        key = fingerprint([pid, tag['code'], evidence.get('algorithm_version'), evidence.get('parameter_snapshot')])
                        pattern = patterns.setdefault(key, {'key':key,'player_id':pid,'player_name':players[pid],
                            'code':tag['code'],'label':PATTERN_LABELS.get(tag['code'],tag['code']),'quality':tag.get('quality','derived'),
                            'algorithm_version':evidence.get('algorithm_version'),'occurrences':[]})
                        pattern['occurrences'].append({**entry,'evidence_id':evidence.get('evidence_id'),
                            'tick':evidence.get('tick'),'round_id':evidence.get('round_id'),'reason':evidence.get('reason'),
                            'label':tag.get('label',tag['code'])})
            for metric in module['metrics']:
                key = metric['comparison_key']
                group = groups.setdefault(key, {'key': key, 'module_id': mid, 'metric_id': metric['metric_id'],
                    'title': metric.get('definition', {}).get('title') or metric['metric_id'], 'scope': metric.get('scope', {}),
                    'unit': metric.get('unit'), 'algorithm_version': metric.get('algorithm_version'),
                    'parameter_snapshot': metric.get('parameter_snapshot', {}), 'aggregation': metric.get('aggregation'),
                    'points': [], 'value': None, 'numerator': 0, 'denominator': 0,
                    'eligible_count': 0, 'evaluated_count': 0, 'unknown_count': 0, 'unavailable_matches': 0})
                point = {**entry, 'value': metric.get('value'), 'coverage': metric.get('coverage'), 'quality': metric.get('quality'),
                         'numerator': metric.get('numerator'), 'denominator': metric.get('denominator')}
                group['points'].append(point)
                for count in ['eligible_count', 'evaluated_count', 'unknown_count']:
                    group[count] += metric.get(count) or 0
                if metric.get('value') is None:
                    group['unavailable_matches'] += 1
                if metric.get('aggregation') == 'ratio_of_sums':
                    group['numerator'] += metric.get('numerator') or 0
                    group['denominator'] += metric.get('denominator') or 0
    for group in groups.values():
        group['match_count'] = len(group['points'])
        group['coverage'] = group['evaluated_count']/group['eligible_count'] if group['eligible_count'] else None
        if group['aggregation'] == 'ratio_of_sums':
            invalid = any(p['value'] is None and (p['denominator'] or 0) > 0 for p in group['points'])
            group['value'] = group['numerator']/group['denominator'] if group['denominator'] and not invalid else None
        elif group['aggregation'] == 'sum' and not group['unavailable_matches']:
            group['value'] = sum(p['value'] for p in group['points'])
        # Quantiles and medians are deliberately not averaged across matches.
        group['points'].sort(key=lambda point: point['saved'])
    for pattern in patterns.values():
        pattern['count'] = len(pattern['occurrences'])
        pattern['match_count'] = len({p['demo_hash'] for p in pattern['occurrences']})
    return {'entries': entries, 'players': [{'player_id': pid, 'name': name} for pid, name in players.items()],
            'patterns': sorted(patterns.values(), key=lambda p: (-p['match_count'], -p['count'], p['player_id'])),
            'series': list(groups.values()), 'distinct_demos': len({e['demo_hash'] for e in entries}),
            'limitations': ['同一场同一 ID 只计最新保存版本；不同 ID、算法版本和参数各自分组。',
                            '比率用总分子 / 总分母；中位数和分位数只显示逐场趋势，不平均。',
                            '趋势按保存时间排序，不代表比赛实际日期。']}


@router.get('/{profile_id}')
def get_profile(profile_id: str, player_id: str | None = None, map_name: str | None = None, include_hidden: bool = False):
    with connect() as con:
        profile = require_profile(con, profile_id)
        # Migrate older archives lazily, one snapshot at a time.
        for row in con.execute('SELECT id FROM entries WHERE profile_id=? AND summary IS NULL', (profile_id,)).fetchall():
            old = con.execute('SELECT snapshot FROM entries WHERE id=?', (row['id'],)).fetchone()
            con.execute('UPDATE entries SET summary=? WHERE id=?', (dumps(compact_summary(json.loads(old['snapshot']))),row['id']))
        rows = con.execute('SELECT id,profile_id,demo_hash,player_id,job_id,saved,revision,hidden,summary FROM entries WHERE profile_id=?'+('' if include_hidden else ' AND hidden=0')+' ORDER BY saved', (profile_id,)).fetchall()
    active = [r for r in rows if not r['hidden']]
    payload = summarize(active, map_name, player_id)
    payload['hidden_entries'] = [{k: r[k] for k in ['id','player_id','demo_hash','saved','revision']} for r in rows if r['hidden']]
    return {**profile, **payload}


@router.get('/{profile_id}/entries/{entry_id}')
def get_entry(profile_id: str, entry_id: str, revision: int | None = Query(default=None, ge=1)):
    with connect() as con:
        row = con.execute('SELECT * FROM entries WHERE profile_id=? AND id=?', (profile_id, entry_id)).fetchone()
        if not row:
            raise HTTPException(404, '存档条目不存在')
        revisions = [dict(r) for r in con.execute('SELECT revision,saved FROM revisions WHERE entry_id=? ORDER BY revision DESC', (entry_id,))]
        version = con.execute('SELECT snapshot FROM revisions WHERE entry_id=? AND revision=?', (entry_id, revision or row['revision'])).fetchone()
        if not version:
            raise HTTPException(404, '该历史版本不存在')
        return {'id': entry_id, 'current_job_id': row['job_id'], 'revision': revision or row['revision'], 'revisions': revisions, 'snapshot': json.loads(version['snapshot'])}


@router.patch('/{profile_id}/entries/{entry_id}')
def hide_entry(profile_id: str, entry_id: str, body: VisibilityInput):
    with connect() as con:
        cur = con.execute('UPDATE entries SET hidden=? WHERE profile_id=? AND id=?', (int(body.hidden), profile_id, entry_id))
        if not cur.rowcount:
            raise HTTPException(404, '存档条目不存在')
    return {'hidden': body.hidden}


@router.get('/{profile_id}/export/json')
def export_profile(profile_id: str):
    with connect() as con:
        profile = require_profile(con, profile_id)
        entries = []
        for row in con.execute('SELECT * FROM entries WHERE profile_id=? ORDER BY saved', (profile_id,)):
            entry = dict(row)
            entry['snapshot'] = json.loads(entry['snapshot'])
            entry['history'] = [{**dict(r), 'snapshot': json.loads(r['snapshot'])} for r in con.execute('SELECT revision,saved,snapshot FROM revisions WHERE entry_id=? ORDER BY revision', (row['id'],))]
            entries.append(entry)
    return Response(dumps({'format': 'cs2-personal-archive', 'format_version': 1, 'profile': profile, 'entries': entries}),
                    media_type='application/json', headers={'Content-Disposition': f'attachment; filename="archive-{profile_id}.json"'})
