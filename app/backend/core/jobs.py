import sqlite3,json,time,uuid,threading,multiprocessing,os
from pathlib import Path
from .common import DATA,dumps,read_json

def connect():
    DATA.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DATA/'jobs.sqlite',timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL')
    c.executescript('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, demo_hash TEXT, filename TEXT, source TEXT, status TEXT, stage TEXT, detail TEXT, config TEXT, result TEXT, error TEXT, created REAL, updated REAL); CREATE TABLE IF NOT EXISTS module_runs(job_id TEXT,module_id TEXT,status TEXT,cache_key TEXT,error TEXT,PRIMARY KEY(job_id,module_id));')
    return c
def update(job_id,**values):
    values['updated']=time.time()
    with connect() as c:c.execute('UPDATE jobs SET '+','.join(k+'=?' for k in values)+' WHERE id=?',list(values.values())+[job_id])
def get(job_id):
    with connect() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    return dict(row) if row else None
def list_jobs():
    with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC')]
def create(demo_hash,filename,source,config):
    jid=uuid.uuid4().hex
    with connect() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(jid,demo_hash,filename,str(source),'queued','排队','等待独立工作进程',dumps(config),None,None,time.time(),time.time()))
    return get(jid)
def module_run(jid,mid,status,key=None,error=None):
    with connect() as c:c.execute('INSERT OR REPLACE INTO module_runs VALUES(?,?,?,?,?)',(jid,mid,status,key,error))
def cancel_path(jid):return DATA/'cancellation'/jid
def cancel(jid):
    j=get(jid)
    if not j:raise KeyError(jid)
    if j['status'] in ('queued','running'):
        path=cancel_path(jid);path.parent.mkdir(parents=True,exist_ok=True);path.touch()
        if j['status']=='queued':update(jid,status='cancelled',stage='已取消',detail='未开始解析')
        else:update(jid,detail='正在取消；原生解析无法中断时将在 2 秒内结束工作进程')

class Scheduler:
    def __init__(self):self.stop=threading.Event();self.running={};self.concurrency=max(1,min(2,int(os.getenv('CS2_WORKERS','1'))))
    def start(self):
        with connect() as c:c.execute("UPDATE jobs SET status='failed',error='上次应用异常退出；可重试',stage='已中断' WHERE status='running'")
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def loop(self):
        from .pipeline import worker
        spawn=multiprocessing.get_context('spawn')
        while not self.stop.wait(.25):
            for jid,process in list(self.running.items()):
                if cancel_path(jid).exists() and time.time()-cancel_path(jid).stat().st_mtime>2 and process.is_alive():
                    process.terminate();process.join(3);update(jid,status='cancelled',stage='已取消',detail='工作进程已结束；未完成缓存不发布')
                if not process.is_alive():
                    process.join();j=get(jid)
                    if j['status']=='running':update(jid,status='failed',stage='失败',error=f'工作进程退出码 {process.exitcode}')
                    self.running.pop(jid)
            for j in reversed(list_jobs()):
                if len(self.running)>=self.concurrency:break
                if j['status']=='queued':
                    update(j['id'],status='running',stage='准备')
                    proc=spawn.Process(target=worker,args=(j['id'],),daemon=True);proc.start();self.running[j['id']]=proc
    def close(self):
        self.stop.set();self.thread.join(2)
        for jid,p in self.running.items():
            if p.is_alive():p.terminate();p.join(3)
            update(jid,status='cancelled',stage='应用停止',detail='可重试；已完成缓存保留')
