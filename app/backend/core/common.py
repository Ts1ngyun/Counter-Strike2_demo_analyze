from pathlib import Path
import hashlib, json, math, os, time
import numpy as np

APP = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('CS2_DATA_DIR', APP / 'data')).resolve()
VERSION = '1.1.0'
PROVIDERS_VERSION = 'experimental-1'

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, Path): return str(x)
    return x

def dumps(x): return json.dumps(clean(x), ensure_ascii=False, allow_nan=False, sort_keys=True)
def save(path, x):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp'); tmp.write_text(dumps(x), encoding='utf-8'); tmp.replace(path)
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def fingerprint(x): return hashlib.sha256(dumps(x).encode()).hexdigest()
def hash_file(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def ratio(n,d): return n / d if d else None
def wrap(x): return (x + 180) % 360 - 180
def check_cancel(path):
    if path and Path(path).exists(): raise InterruptedError('用户取消')

def metric(module, mid, value, scope=None, unit='count', n=None,d=None, eligible=None,unknown=0,excluded=0,
           quality='derived',method='',limitations=None,evidence=None, **extra):
    evaluated = extra.pop('evaluated_count', d if d is not None else (max(0,eligible-unknown) if eligible is not None else 1))
    eligible = eligible if eligible is not None else evaluated + unknown
    return dict(module_id=module,metric_id=mid,scope=scope or {},value=clean(value),unit=unit,
        aggregation='ratio_of_sums' if d is not None else 'sum',numerator=n,denominator=d,
        sample_unit=extra.pop('sample_unit','round' if module=='basic_stats' else 'window'),
        eligible_count=eligible,evaluated_count=evaluated,unknown_count=unknown,excluded_count=excluded,
        coverage=ratio(evaluated,eligible),method=method,quality=quality,limitations=limitations or [],
        evidence_refs=evidence or [],**extra)
