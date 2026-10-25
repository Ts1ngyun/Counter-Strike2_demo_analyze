from pathlib import Path
import importlib.metadata,json,time,traceback,threading,shutil,os
import psutil
from jsonschema import validate
from .common import APP,DATA,VERSION,PROVIDERS_VERSION,save,read_json,fingerprint,check_cancel,dumps,hash_file
from .registry import discover,Analyzer,topo
from .context import AnalysisContext
from .contracts import metric_validator,evidence_validator
from . import jobs
from ..adapters.demo.parser import extract
from ..features.build import build,VERSION as FEATURE_VERSION

def validated_config(config):
    manifests=discover();selected=config.get('modules') or [k for k,v in manifests.items() if v['enabled']]
    if len(selected)!=len(set(selected)):raise ValueError('重复模块')
    for mid in list(selected):
        if mid not in manifests:raise ValueError('未知模块: '+mid)
    pending=list(selected)
    while pending:
        m=manifests[pending.pop()]
        for dep in m.get('module_dependencies',[]):
            if dep not in manifests or not manifests[dep]['enabled']:raise ValueError('模块依赖不可用: '+dep)
            if dep not in selected:selected.append(dep);pending.append(dep)
    order=topo({mid:manifests[mid].get('module_dependencies',[]) for mid in selected})
    selected=order
    parameters={}
    for mid in selected:
        if mid not in manifests or not manifests[mid]['enabled']:raise ValueError('模块不可运行: '+mid)
        parameters[mid]={**manifests[mid]['defaults'],**config.get('parameters',{}).get(mid,{})}
        validate(parameters[mid],manifests[mid]['parameters_schema_body'])
        if mid=='head_line' and parameters[mid]['window_start_ms']>=parameters[mid]['window_end_ms']:raise ValueError('头线窗口开始必须早于结束')
    players=config.get('players',[])
    if not isinstance(players,list) or any(not isinstance(x,str) or not x.isdecimal() for x in players):raise ValueError('SteamID 必须为十进制字符串列表')
    return {'modules':selected,'parameters':parameters,'players':players}

def worker(jid):
    j=jobs.get(jid);config=json.loads(j['config']);cancel=jobs.cancel_path(jid);started=time.perf_counter();peak=[0];done=threading.Event();rss=psutil.Process()
    def measure():
        while not done.wait(.05):
            try:peak[0]=max(peak[0],rss.memory_info().rss)
            except psutil.Error:pass
    monitor=threading.Thread(target=measure,daemon=True);monitor.start()
    def progress(stage,detail=''):check_cancel(cancel);jobs.update(jid,stage=stage,detail=detail)
    lock=None
    try:
        lock_dir=DATA/'locks';lock_dir.mkdir(parents=True,exist_ok=True)
        lock=open(lock_dir/(j['demo_hash']+'.lock'),'a+b')
        if lock.tell()==0:lock.write(b'0');lock.flush()
        while True:
            check_cancel(cancel)
            try:
                lock.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:progress('等待缓存锁','同一内容的另一任务正在写入共享缓存');time.sleep(.15)
        manifests=discover();config=validated_config(config)
        fields=sorted(set(f for mid in config['modules'] for f in manifests[mid].get('raw_fields',[])))
        parser={'name':'demoparser2','version':importlib.metadata.version('demoparser2')}
        adapter_hash=fingerprint({x:hash_file(APP/x) for x in ['backend/adapters/demo/parser.py','backend/adapters/demo/container.py','backend/core/field_catalog.py']})
        fact_identity={'demo_hash':j['demo_hash'],'parser':parser,'normalization':VERSION,'adapter_code':adapter_hash,'fields':fields}
        base=DATA/'facts'/j['demo_hash'];root=base/fingerprint(fact_identity)[:24]
        # Reuse a previously extracted superset, including known-unavailable requested fields.
        if base.exists():
            for candidate in sorted(base.iterdir()):
                if (candidate/'complete.json').exists():
                    identity=read_json(candidate/'complete.json')
                    if identity.get('parser')==parser and identity.get('normalization')==VERSION and identity.get('adapter_code')==adapter_hash and set(fields)<=set(identity.get('fields',[])):root=candidate;fact_identity=identity;break
        reused=(root/'complete.json').exists()
        if not reused:
            if not Path(j['source']).is_file():raise ValueError('本地应用副本已清理，且没有可复用事实缓存；请重新导入 demo')
            # New isolated attempt; aborted partial partitions never become a valid cache.
            if root.exists():shutil.rmtree(root)
            extract(j['source'],root,j['demo_hash'],fields,progress,cancel)
            save(root/'complete.json',fact_identity)
        context=AnalysisContext(root)
        provider_hash=fingerprint({'identities':context.providers.identities,'weapon_config':context.providers.weapons.data,'code':hash_file(APP/'backend/providers/__init__.py')})
        feature_identity={'facts':fact_identity,'version':FEATURE_VERSION,'provider':provider_hash,'code':hash_file(APP/'backend/features/build.py')}
        needs_features=any(manifests[mid]['feature_dependencies'] for mid in config['modules'])
        feature_error=None
        if needs_features and (not (root/'features_complete.json').exists() or read_json(root/'features_complete.json')!=feature_identity):
            try:
                for name in ['shots','bursts','engagements','movement']:
                    if (root/name).exists():shutil.rmtree(root/name)
                build(context,progress,cancel);save(root/'features_complete.json',feature_identity)
            except InterruptedError:raise
            except Exception as ex:feature_error=str(ex)
        results={};failures={}
        for mid in config['modules']:
            check_cancel(cancel);m=manifests[mid];params=config['parameters'][mid]
            identity={'facts':fact_identity,'features':feature_identity if m['feature_dependencies'] else None,'module':mid,'module_version':m['version'],'manifest_hash':fingerprint(m),'module_code':{str(p.relative_to(APP)):hash_file(p) for p in sorted((APP/f'backend/modules/{mid}').rglob('*.py'))},'common_code':hash_file(APP/'backend/core/common.py'),'parameters':params,'provider':provider_hash,'contract':1}
            key=fingerprint(identity);cached=DATA/'module_cache'/key/'result.json';jobs.module_run(jid,mid,'running',key)
            try:
                progress('模块分析',m['title'])
                if feature_error and m['feature_dependencies']:raise ValueError('依赖特征失败：'+feature_error)
                if cached.exists():result=read_json(cached);cache_hit=True
                else:
                    analyzer=Analyzer(m);report=analyzer.validate(context,params);analyzer.plan(context,params)
                    result=analyzer.analyze(context,params,cancel,progress) if report['requirements_met'] else {'status':'unsupported','metrics':[],'evidence':[],'details':{'reason':'依赖能力缺失'}}
                    validate(result,m['result_schema_body'])
                    for metric in result['metrics']:
                        metric.update(parameter_snapshot=params,algorithm_version=m['version'],identities=identity,config_hash=key,definition=m.get('metric_definitions',{}).get(metric['metric_id'],{}))
                        if metric['value'] is None:metric.setdefault('limitations',[]).append('无有效分母或所需能力不可用；不是 0 分')
                        metric_validator.validate(metric)
                    for evidence in result['evidence']:
                        evidence.update(demo_hash=j['demo_hash'],algorithm_version=m['version'],parameter_snapshot=params,native_resolution_seconds=context.meta['tick_seconds'],subtick=None,source_sequence=None,command_offset=None)
                        evidence.setdefault('start_time',evidence.get('tick',0)*context.meta['tick_seconds']);evidence.setdefault('end_time',evidence.get('end_tick',evidence.get('tick',0))*context.meta['tick_seconds'])
                        evidence.setdefault('sample_semantics','events within live round, freeze-end roster and end-of-tick survival; source event attachment is not pre-event state')
                        evidence.setdefault('rule',evidence['reason'])
                        evidence_validator.validate(evidence)
                    save(cached,result);cache_hit=False
                results[mid]={**result,'cache_hit':cache_hit};jobs.module_run(jid,mid,result['status'],key)
            except InterruptedError:raise
            except Exception as ex:
                failures[mid]=str(ex);jobs.module_run(jid,mid,'failed',key,str(ex));results[mid]={'status':'failed','metrics':[],'evidence':[],'error':str(ex),'traceback':traceback.format_exc()}
        if config['players']:
            for result in results.values():
                result['metrics']=[m for m in result['metrics'] if m['scope'].get('player_id') in config['players']]
                result['evidence']=[e for e in result['evidence'] if e.get('player_id') in config['players']]
        elapsed=time.perf_counter()-started
        output={'contract_version':1,'job_id':jid,'demo':context.meta,'facts_path':str(root),'capabilities':context.capabilities,'fields':context.fields,'players':context.query('players').to_dict('records'),'rounds':context.rounds(),'config':config,'modules':results,'performance':{'wall_seconds':elapsed,'peak_sampled_worker_rss_bytes':peak[0],'rss_sample_interval_ms':50,'facts_bytes':sum(f.stat().st_size for f in root.rglob('*') if f.is_file()),'facts_cache_hit':reused},'limitations':['仅验证一个真实 demo 的补丁/地图','未完成 TrueView 客户端预测重建','没有职业/段位对比基线']}
        destination=DATA/'results'/jid/'result.json';save(destination,output)
        save(destination.with_name('summary.json'),{'map_name':context.meta['header'].get('map_name'),'patch_version':context.meta['header'].get('patch_version')})
        jobs.update(jid,status='partial' if failures or any(v['status']!='succeeded' for v in results.values()) else 'succeeded',stage='完成',detail=f'{elapsed:.1f} 秒；'+('复用事实缓存' if reused else '完成原始文件解析'),result=str(destination),error=dumps(failures) if failures else None)
    except InterruptedError:jobs.update(jid,status='cancelled',stage='已取消',detail='合作式取消；未完成缓存未发布')
    except BaseException as ex:jobs.update(jid,status='failed',stage='失败',error=str(ex),detail=traceback.format_exc())
    finally:
        if lock:lock.close()
        done.set();monitor.join(1)
