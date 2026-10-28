"""Read-only cached result access; consumers must not mutate returned objects."""
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException
from ..core import jobs
from ..core.common import read_json


@lru_cache(maxsize=2)
def _read(path: str, modified: int, size: int):
    return without_retired_impact(read_json(path))


def without_retired_impact(result):
    """Hide retired metrics in historical reports without rewriting their files."""
    basic = result.get('modules', {}).get('basic_stats')
    if not basic:
        return result
    keep = lambda metrics: [m for m in metrics if m.get('metric_id') != 'impact']
    details = basic.get('details', {})
    projected = {**basic, 'metrics': keep(basic.get('metrics', []))}
    if 'round_stats' in details:
        projected['details'] = {**details, 'round_stats': [
            {**row, 'metrics': keep(row.get('metrics', []))} for row in details['round_stats']]}
    return {**result, 'modules': {**result['modules'], 'basic_stats': projected}}


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
