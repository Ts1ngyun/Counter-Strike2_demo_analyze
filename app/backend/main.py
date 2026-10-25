from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
import csv,io,json,hashlib,uuid,html,os,threading
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import FileResponse,Response,HTMLResponse
from fastapi.staticfiles import StaticFiles
from .core import jobs
from .core.common import APP,DATA,read_json,dumps,clean
from .core.registry import discover
from .core.pipeline import validated_config
from .core.context import AnalysisContext,TABLES
from .services.results import load_result

@asynccontextmanager
async def lifespan(app):
    scheduler=jobs.Scheduler();scheduler.start();app.state.scheduler=scheduler
    yield
    scheduler.close()
app=FastAPI(title='CS2 Demo Evidence Lab',lifespan=lifespan)

@app.middleware('http')
async def local_only(request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost','testserver'):return Response('仅允许本机访问',status_code=403)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin');site=request.headers.get('sec-fetch-site')
        if site=='cross-site' or origin and urlparse(origin).netloc!=request.headers.get('host'):return Response('拒绝跨站写入',status_code=403)
    return await call_next(request)

def require_job(jid):
    j=jobs.get(jid)
    if not j:raise HTTPException(404,'任务不存在')
    return j
def result_of(jid):
    return load_result(jid)
def public_job(j):
    out={k:v for k,v in j.items() if k not in ('source','result','config')}
    if j['result']:
        summary=Path(j['result']).with_name('summary.json')
        if summary.exists():out.update(read_json(summary))
    return out

@app.get('/api/health')
def health():return {'ok':True,'local_only':True,'version':'1.0.0'}
@app.post('/api/shutdown')
def shutdown():
    app.state.scheduler.close()
    threading.Timer(.3,lambda:os._exit(0)).start()
    return {'stopped':True}
@app.get('/api/modules')
def modules():return list(discover().values())
@app.get('/api/jobs')
def get_jobs():return [public_job(j) for j in jobs.list_jobs()]
@app.post('/api/upload')
async def upload(file:UploadFile=File(...),config:str=Form('{}')):
    try:cfg=validated_config(json.loads(config))
    except Exception as e:raise HTTPException(422,str(e))
    name=Path((file.filename or 'demo.dem').replace('\\','/')).name
    if not name.lower().endswith('.dem'):raise HTTPException(400,'请选择 .dem 原始文件')
    uploads=DATA/'uploads';uploads.mkdir(parents=True,exist_ok=True);temp=uploads/(uuid.uuid4().hex+'.part');hasher=hashlib.sha256();total=0
    try:
        with temp.open('wb') as dest:
            while chunk:=await file.read(4*1024*1024):
                if total==0 and chunk[:8]!=b'PBDEMS2\0':raise HTTPException(400,'魔数不是 PBDEMS2')
                total+=len(chunk)
                if total>8*1024**3:raise HTTPException(413,'单文件上限 8 GiB')
                hasher.update(chunk);dest.write(chunk)
        if total<16:raise HTTPException(400,'文件为空或已截断')
        digest=hasher.hexdigest();target=uploads/(digest+'.dem');duplicate=target.exists()
        if duplicate:temp.unlink()
        else:temp.replace(target)
        j=jobs.create(digest,name,target,cfg);return {**public_job(j),'duplicate':duplicate,'uploaded_bytes':total}
    finally:
        if temp.exists():temp.unlink()
        await file.close()
@app.post('/api/jobs/{jid}/cancel')
def cancel_job(jid:str):
    require_job(jid);jobs.cancel(jid);return {'ok':True}
@app.post('/api/jobs/{jid}/retry')
def retry(jid:str,config:dict|None=None):
    j=require_job(jid)
    try:cfg=validated_config(config if config is not None else json.loads(j['config']))
    except Exception as e:raise HTTPException(422,str(e))
    return public_job(jobs.create(j['demo_hash'],j['filename'],j['source'],cfg))
@app.get('/api/jobs/{jid}/result')
def result(jid:str):
    r=result_of(jid)
    # Project without mutating the shared read-only result cache.
    modules={}
    for mid,m in r['modules'].items():
        modules[mid]={**{k:v for k,v in m.items() if k not in ('evidence','metrics')},'evidence_count':len(m.get('evidence',[])),
            'metrics':[{**metric,'evidence_count':len(metric['evidence_refs']),'evidence_refs':metric['evidence_refs'][:5]} for metric in m.get('metrics',[])]}
    return {**r,'modules':modules}
@app.get('/api/jobs/{jid}/evidence/{module}')
def evidence(jid:str,module:str,player:str|None=None,round_id:str|None=None,weapon:str|None=None,judgement:str|None=None,pose:str|None=None,team:str|None=None,distance:str|None=None,metric_id:str|None=None,weapon_set:str|None=None,analysis_mode:str|None=None,attack_input_status:str|None=None,offset:int=0,limit:int=50):
    r=result_of(jid);m=r['modules'].get(module)
    if m is None:raise HTTPException(404,'无该模块结果')
    rows=m['evidence']
    if metric_id:
        refs=set(x for metric in m['metrics'] if metric['metric_id']==metric_id and (not player or metric['scope'].get('player_id')==player) and (not weapon_set or metric['scope'].get('weapon_set',weapon_set)==weapon_set) and (not analysis_mode or metric['scope'].get('analysis_mode',analysis_mode)==analysis_mode) for x in metric['evidence_refs']);rows=[e for e in rows if e['evidence_id'] in refs]
    if weapon_set:rows=[e for e in rows if weapon_set in e.get('weapon_sets',['all'])]
    if analysis_mode:rows=[e for e in rows if e.get('analysis_mode','experimental_geometry')==analysis_mode]
    if attack_input_status:rows=[e for e in rows if e.get('attack_input_status')==attack_input_status]
    for field,value in [('player_id',player),('round_id',round_id),('weapon',weapon),('judgement',judgement),('self_pose',pose),('team',team),('distance_bucket',distance)]:
        if value:rows=[e for e in rows if str(e.get(field))==value]
    return {'total':len(rows),'rows':rows[max(0,offset):max(0,offset)+min(max(1,limit),200)]}
@app.get('/api/jobs/{jid}/inspect/{table}')
def inspect(jid:str,table:str,player:str|None=None,start:int|None=None,end:int|None=None,round_id:str|None=None,limit:int=50,offset:int=0):
    r=result_of(jid)
    if table=='fields':return r['fields']
    if table=='capabilities':return r['capabilities']
    if table=='raw_fields':return read_json(Path(r['facts_path'])/'raw_fields.json')
    if table not in TABLES:raise HTTPException(400,'未知数据表')
    df=AnalysisContext(r['facts_path']).query(table,player=player,start=start,end=end,round_id=round_id,limit=min(max(1,limit),200),offset=max(0,offset))
    return json.loads(df.to_json(orient='records'))
@app.get('/api/jobs/{jid}/export/{format}')
def export(jid:str,format:str):
    r=result_of(jid)
    if format=='json':return Response(dumps(r),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{jid}.json"'})
    if format=='csv':
        output=io.StringIO();keys=['module_id','metric_id','scope','value','unit','numerator','denominator','eligible_count','evaluated_count','unknown_count','coverage','quality','algorithm_version','config_hash','parameter_snapshot','limitations','evidence_refs'];writer=csv.DictWriter(output,fieldnames=keys);writer.writeheader()
        for module in r['modules'].values():
            for m in module['metrics']:writer.writerow({k:dumps(m.get(k)) if isinstance(m.get(k),(dict,list)) else m.get(k) for k in keys})
        return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{jid}.csv"'})
    if format=='html':
        parts=['<!doctype html><meta charset="utf-8"><title>CS2 离线证据报告</title><style>body{font:15px system-ui;background:#101827;color:#dfebed;margin:40px}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #456}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}</style><h1>CS2 Demo 离线证据报告</h1>',f'<p>SHA256 {r["demo"]["demo_hash"]}</p>']
        for mid,m in r['modules'].items():
            parts.append('<h2>'+html.escape(mid)+' · '+m['status']+'</h2><table><tr><th>指标</th><th>范围</th><th>值</th><th>覆盖率</th><th>质量</th></tr>')
            for x in m['metrics']:parts.append('<tr>'+''.join('<td>'+html.escape(dumps(x.get(k)))+'</td>' for k in ['metric_id','scope','value','coverage','quality'])+'</tr>')
            parts.append('</table><details><summary>全部原始证据、参数和版本</summary><pre>'+html.escape(dumps(m))+'</pre></details>')
        parts.append('<details><summary>文件、能力、配置、性能</summary><pre>'+html.escape(dumps({k:v for k,v in r.items() if k!='modules'}))+'</pre></details>')
        return HTMLResponse(''.join(parts),headers={'Content-Disposition':f'attachment; filename="{jid}.html"'})
    raise HTTPException(400,'只支持 json/csv/html')
@app.post('/api/aggregate')
def aggregate(body:dict):
    groups={};seen=set()
    for jid in body.get('job_ids',[]):
        r=result_of(jid)
        if r['demo']['demo_hash'] in seen:continue
        seen.add(r['demo']['demo_hash'])
        for mid,module in r['modules'].items():
            for m in module['metrics']:
                if m['aggregation'] not in ('ratio_of_sums','sum'):continue
                key=dumps([mid,m['metric_id'],m['scope'],m['parameter_snapshot'],m['algorithm_version']]);g=groups.setdefault(key,{**m,'value':0,'numerator':0,'denominator':0,'eligible_count':0,'evaluated_count':0,'unknown_count':0,'excluded_count':0,'coverage':None,'demo_count':0,'unavailable_demos':0,'evidence_refs':[]})
                g['demo_count']+=1;g['evidence_refs'].append({'job_id':jid,'refs':m['evidence_refs']})
                for k in ['eligible_count','evaluated_count','unknown_count','excluded_count']:g[k]+=m[k]
                g['coverage']=g['evaluated_count']/g['eligible_count'] if g['eligible_count'] else None
                if m['value'] is None:g['unavailable_demos']+=1
                if m['aggregation']=='ratio_of_sums':
                    g['numerator']+=m['numerator'] or 0;g['denominator']+=m['denominator'] or 0
                    g['value']=g['numerator']/g['denominator'] if g['denominator'] else None
                    if m['numerator'] is None and m['denominator']:g['quality']='unknown'
                    if g['quality']=='unknown':g['value']=None
                else:
                    if g['unavailable_demos']:g['value']=None
                    elif m['value'] is not None:g['value']+=m['value']
    return {'distinct_demos':len(seen),'metrics':list(groups.values()),'limitations':['相同哈希只合并一次；仅相同参数/版本；分位数不平均，需导出样本重算']}
@app.get('/api/storage')
def storage():
    return {'root':str(DATA),'groups':{name:sum(p.stat().st_size for p in (DATA/name).rglob('*') if p.is_file()) for name in ['uploads','facts','module_cache','results']},'policy':'清理应用内原始副本后，高频事实/证据仍可复查；无法补抽缺失字段。外部原始文件与旧 demo_output 永不删除。'}
@app.delete('/api/uploads/{digest}')
def delete_upload(digest:str):
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise HTTPException(400,'非法哈希')
    if any(j['demo_hash']==digest and j['status'] in ('queued','running') for j in jobs.list_jobs()):raise HTTPException(409,'该文件仍有运行任务')
    path=DATA/'uploads'/(digest+'.dem');path.unlink(missing_ok=True);return {'deleted_app_copy':True,'facts_retained':True}

from .routers.profiles import router as profiles_router
app.include_router(profiles_router)
from .routers.replay import router as replay_router
from .routers.combat import router as combat_router
app.include_router(replay_router)
app.include_router(combat_router)

DIST=APP/'frontend/dist'
if DIST.exists():app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
