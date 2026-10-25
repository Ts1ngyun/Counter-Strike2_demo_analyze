import argparse,json,shutil
from pathlib import Path
from .core.common import hash_file,DATA,dumps
from .core.pipeline import worker,validated_config
from .core import jobs

def main():
    p=argparse.ArgumentParser();p.add_argument('demo');p.add_argument('--modules',default='');p.add_argument('--players',default='');p.add_argument('--config');a=p.parse_args()
    source=Path(a.demo).resolve();digest=hash_file(source);config=json.loads(Path(a.config).read_text()) if a.config else {}
    if a.modules:config['modules']=a.modules.split(',')
    if a.players:config['players']=a.players.split(',')
    cfg=validated_config(config);j=jobs.create(digest,source.name,source,cfg);jobs.update(j['id'],status='running')
    print('job_id='+j['id'],flush=True);worker(j['id']);result=jobs.get(j['id']);print(dumps(result),flush=True)
    if result['status']=='failed':raise SystemExit(1)
if __name__=='__main__':main()
