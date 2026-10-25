"""Read-only cached result access; consumers must not mutate returned objects."""
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException
from ..core import jobs
from ..core.common import read_json


@lru_cache(maxsize=2)
def _read(path: str, modified: int, size: int):
    return read_json(path)


def load_result(jid: str):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404, '任务不存在')
    if not job.get('result'):
        raise HTTPException(409, '结果尚未就绪')
    path = Path(job['result'])
    if not path.is_file():
        raise HTTPException(410, '任务结果文件已不存在')
    stat = path.stat()
    return _read(str(path), stat.st_mtime_ns, stat.st_size)
