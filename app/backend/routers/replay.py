"""Bounded, read-only fact playback and local, hash-scoped annotations."""
from pathlib import Path
from threading import Lock
import json, math, time, uuid
import duckdb
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from ..core import jobs
from ..core.common import DATA, clean, read_json, save
from ..services.results import load_result

router = APIRouter(prefix='/api')
_write_lock = Lock()
EVENTS = ('player_death','player_hurt','player_blind','flashbang_detonate',
          'grenade_thrown','bomb_planted','bomb_defused','bomb_exploded','bomb_dropped','bomb_pickup')

def _result(jid):
    j = jobs.get(jid)
    if not j: raise HTTPException(404, '任务不存在')
    if not j.get('result'): raise HTTPException(409, '任务尚未产生结果')
    path = Path(j['result']).resolve()
    if not path.is_relative_to(DATA.resolve()): raise HTTPException(400, '结果路径不在应用数据目录')
    r = load_result(jid)
    root = Path(r['facts_path']).resolve()
    if not root.is_relative_to((DATA/'facts').resolve()): raise HTTPException(400, '事实路径不在应用事实目录')
    return r, root

def _query(root, table, suffix='', args=None, columns='*'):
    paths = sorted((root/table).glob('*.parquet'))
    if not paths: return []
    with duckdb.connect(':memory:') as con:
        con.execute("SET memory_limit='256MB'")
        con.execute('SET threads=2')
        return json.loads(con.execute(f'SELECT {columns} FROM read_parquet(?, union_by_name=true) '+suffix,
                                     [[str(p) for p in paths]]+(args or [])).df().to_json(orient='records'))

def _round(r, round_id):
    found = next((x for x in r['rounds'] if x['round_id']==round_id), None)
    if not found: raise HTTPException(404, '回合不存在')
    return found

def _bounds(root):
    rows = _query(root, 'player_states', columns='min("X") x_min,max("X") x_max,min("Y") y_min,max("Y") y_max,min("Z") z_min,max("Z") z_max')
    if not rows or rows[0]['x_min'] is None: return None
    return rows[0]

@router.get('/jobs/{jid}/replay/meta')
def replay_meta(jid: str):
    r, root = _result(jid)
    present = _query(root, 'events', columns='DISTINCT event_name')
    return clean({'demo_hash':r['demo']['demo_hash'], 'map_name':r['demo'].get('header',{}).get('map_name'),
        'tick_seconds':r['demo'].get('tick_seconds'), 'patch_version':r['demo'].get('header',{}).get('patch_version'), 'rounds':r['rounds'], 'players':r['players'],
        'bounds':_bounds(root), 'event_types':[x['event_name'] for x in present if x['event_name'] in EVENTS],
        'map_mode':'world_coordinates', 'limitations':['状态为 tick 末观测；降采样回放不做位置插值，不能重建玩家屏幕。',
        '默认世界坐标图不包含墙体、遮挡或楼层校准。可导入本地底图和世界坐标范围。',
        '仅展示事实中已有的炸弹/投掷事件；没有弹体轨迹时不推测飞行路线。']})

@router.get('/jobs/{jid}/replay/frames')
def replay_frames(jid: str, round_id: str, start: int|None=None, end: int|None=None,
                  step: int=Query(8,ge=1,le=128)):
    r, root = _result(jid); rnd = _round(r,round_id)
    lo=int(rnd['start_tick']); hi=int(rnd.get('end_tick') or rnd.get('next_tick') or lo)
    start=max(lo, start if start is not None else lo); end=min(hi,end if end is not None else hi)
    if start>end: raise HTTPException(422,'时间范围无效')
    # Bound both time span and response. Adaptive sampling keeps an entire round <= 1601 frames.
    if end-start>100000: raise HTTPException(422,'单次回放范围过长，请指定较短 tick 区间')
    step=max(step,math.ceil((end-start+1)/1600))
    columns='tick,player_id,name,"X","Y","Z",yaw,health,is_alive,team_num,active_weapon_name,round_id'
    states = _query(root,'player_states',
        'WHERE round_id=? AND tick BETWEEN ? AND ? AND ((tick-?) % ?=0 OR tick=?) ORDER BY tick,player_id LIMIT 32021',
        [round_id,start,end,start,step,end], columns)
    events = _query(root,'events', 'WHERE round_id=? AND tick BETWEEN ? AND ? AND event_name IN ('+
        ','.join('?' for _ in EVENTS)+') ORDER BY tick,event_name,event_index LIMIT 5001',
        [round_id,start,end,*EVENTS])
    if len(states)>32020 or len(events)>5000: raise HTTPException(422,'数据超出回放上限，请缩短 tick 范围')
    # Keep payloads small; raw event body remains available in the inspector.
    event_fields=('tick','event_id','event_name','round_id','player_id','user_name','user_steamid',
        'attacker_name','attacker_steamid','assister_name','assistedflash','weapon','dmg_health','health',
        'headshot','blind_duration','site','x','y','z')
    events=[{k:e.get(k) for k in event_fields if e.get(k) is not None} for e in events]
    return {'start':start,'end':end,'step':step,'tick_seconds':r['demo'].get('tick_seconds'),
            'states':states,'events':events,'state_semantics':'observed_end_of_tick_no_interpolation'}

class Point(BaseModel):
    x: float = Field(ge=-1000000,le=1000000)
    y: float = Field(ge=-1000000,le=1000000)

class Bookmark(BaseModel):
    round_id: str = Field(min_length=1,max_length=40)
    tick: int = Field(ge=0)
    end_tick: int|None = Field(default=None,ge=0)
    player_id: str|None = Field(default=None,max_length=40)
    title: str = Field(default='',max_length=160)
    note: str = Field(default='',max_length=4000)
    lines: list[list[Point]] = Field(default_factory=list,max_length=40)

def _annotation_path(r):
    digest=r['demo']['demo_hash']
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise HTTPException(400,'非法文件哈希')
    return DATA/'replay'/(digest+'.json')

@router.get('/jobs/{jid}/replay/bookmarks')
def bookmarks(jid: str):
    r,_=_result(jid); path=_annotation_path(r)
    return read_json(path) if path.exists() else {'version':1,'demo_hash':r['demo']['demo_hash'],'bookmarks':[]}

@router.post('/jobs/{jid}/replay/bookmarks')
def add_bookmark(jid: str, body: Bookmark):
    r,_=_result(jid); rnd=_round(r,body.round_id)
    if not int(rnd['start_tick'])<=body.tick<=int(rnd.get('end_tick') or rnd.get('next_tick')):
        raise HTTPException(422,'书签 tick 不在所选回合')
    if body.end_tick is not None and not body.tick<=body.end_tick<=int(rnd.get('end_tick') or rnd.get('next_tick')):
        raise HTTPException(422,'片段结束 tick 无效')
    if body.player_id and body.player_id not in {str(x['player_id']) for x in r['players']}:
        raise HTTPException(422,'玩家不在此 demo 中')
    if sum(len(x) for x in body.lines)>4000: raise HTTPException(422,'绘图最多 4000 个点')
    with _write_lock:
        path=_annotation_path(r); data=read_json(path) if path.exists() else {'version':1,'demo_hash':r['demo']['demo_hash'],'bookmarks':[]}
        if len(data['bookmarks'])>=2000: raise HTTPException(422,'单场最多 2000 个书签')
        item={**body.model_dump(),'id':uuid.uuid4().hex,'created':time.time()}
        data['bookmarks'].append(item);save(path,data)
    return item

@router.delete('/jobs/{jid}/replay/bookmarks/{bookmark_id}')
def delete_bookmark(jid: str, bookmark_id: str):
    r,_=_result(jid)
    with _write_lock:
        path=_annotation_path(r); data=read_json(path) if path.exists() else {'bookmarks':[]}
        before=len(data['bookmarks']);removed=[x for x in data['bookmarks'] if x['id']==bookmark_id]
        data['bookmarks']=[x for x in data['bookmarks'] if x['id']!=bookmark_id]
        if len(data['bookmarks'])==before: raise HTTPException(404,'书签不存在')
        data.setdefault('trash',[]).extend({**x,'deleted_at':time.time()} for x in removed)
        save(path,data)
    return {'deleted':True}

@router.post('/jobs/{jid}/replay/bookmarks/{bookmark_id}/restore')
def restore_bookmark(jid: str, bookmark_id: str):
    r,_=_result(jid)
    with _write_lock:
        path=_annotation_path(r); data=read_json(path) if path.exists() else {'bookmarks':[],'trash':[]}
        found=next((x for x in data.get('trash',[]) if x['id']==bookmark_id),None)
        if not found: raise HTTPException(404,'回收记录中没有此书签')
        if len(data['bookmarks'])>=2000: raise HTTPException(422,'单场最多 2000 个书签')
        data['trash']=[x for x in data['trash'] if x['id']!=bookmark_id]
        found.pop('deleted_at',None);data['bookmarks'].append(found);save(path,data)
    return found
