"""Local review annotations, keyed by demo + algorithm + evidence identity."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..core.common import DATA, fingerprint
from ..services.results import load_result

router=APIRouter(prefix='/api')


@contextmanager
def database():
    folder=DATA/'review';folder.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(folder/'annotations.sqlite3',timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS annotations (demo_hash TEXT, version TEXT, evidence_id TEXT, label TEXT NOT NULL, note TEXT NOT NULL, starred INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(demo_hash,version,evidence_id))')
    try:
        with con: yield con
    finally: con.close()


def result(jid):
    data=load_result(jid);module=data.get('modules',{}).get('combat_review')
    if not module:raise HTTPException(404,'该结果尚无交战复盘，请重新分析')
    return data,module


def annotation_identity(e):
    return fingerprint([e.get('algorithm_version','unknown'),e.get('parameter_snapshot',{})])


class Annotation(BaseModel):
    evidence_id: str=Field(min_length=1,max_length=300)
    label: Literal['unreviewed','problem','reasonable','uncertain']='unreviewed'
    note: str=Field(default='',max_length=4000)
    starred: bool=False


@router.get('/jobs/{jid}/combat-annotations')
def annotations(jid:str):
    data,module=result(jid);keys={(e['evidence_id'],annotation_identity(e)) for e in module['evidence']}
    with database() as con:rows=con.execute('SELECT * FROM annotations WHERE demo_hash=?',(data['demo']['demo_hash'],)).fetchall()
    return {'rows':[dict(r) for r in rows if (r['evidence_id'],r['version']) in keys]}


@router.put('/jobs/{jid}/combat-annotations')
def put_annotation(jid:str,body:Annotation):
    data,module=result(jid);e=next((e for e in module['evidence'] if e['evidence_id']==body.evidence_id),None)
    if not e:raise HTTPException(404,'没有对应复盘证据')
    row=dict(demo_hash=data['demo']['demo_hash'],version=annotation_identity(e),evidence_id=body.evidence_id,
        label=body.label,note=body.note,starred=int(body.starred),updated_at=datetime.now(timezone.utc).isoformat())
    with database() as con:
        con.execute('INSERT INTO annotations VALUES (:demo_hash,:version,:evidence_id,:label,:note,:starred,:updated_at) ON CONFLICT(demo_hash,version,evidence_id) DO UPDATE SET label=excluded.label,note=excluded.note,starred=excluded.starred,updated_at=excluded.updated_at',row)
    return row
