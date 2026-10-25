from pathlib import Path
import importlib, json
import yaml
from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1] / 'modules'
MANIFEST_SCHEMA = {'type':'object','required':['id','version','contract_version','status','enabled','requires','feature_dependencies','metric_ids','views'],
 'properties':{'id':{'type':'string','pattern':'^[a-z][a-z0-9_]+$'},'contract_version':{'const':1},'status':{'enum':['active','planned']},'enabled':{'type':'boolean'},'requires':{'type':'object'},'feature_dependencies':{'type':'array'},'metric_ids':{'type':'array'},'views':{'type':'array'}}}

def capability_expr(expr, capabilities):
    if not expr: return True
    if isinstance(expr,str): return capabilities.get(expr,{}).get('usable',False)
    if 'all_of' in expr: return all(capability_expr(e,capabilities) for e in expr['all_of'])
    if 'any_of' in expr: return any(capability_expr(e,capabilities) for e in expr['any_of'])
    raise ValueError('未知能力表达式')

def topo(graph):
    result=[]; visiting=set(); done=set()
    def visit(n):
        if n in visiting: raise ValueError('循环依赖: '+n)
        if n not in graph: raise ValueError('缺少依赖: '+n)
        if n in done: return
        visiting.add(n)
        for dep in graph[n]: visit(dep)
        visiting.remove(n); done.add(n); result.append(n)
    for n in graph: visit(n)
    return result

def discover(root=ROOT):
    modules={}
    for folder in sorted(root.iterdir()):
        if not (folder/'module.yaml').exists(): continue
        m=yaml.safe_load((folder/'module.yaml').read_text(encoding='utf-8')); validate(m,MANIFEST_SCHEMA)
        m['parameters_schema_body']=json.loads((folder/'parameters.schema.json').read_text(encoding='utf-8'))
        m['result_schema_body']=json.loads((folder/'result.schema.json').read_text(encoding='utf-8'))
        m['defaults']=yaml.safe_load((folder/'defaults.yaml').read_text(encoding='utf-8')) or {}
        if (folder/'metrics.json').exists():m['metric_definitions']=json.loads((folder/'metrics.json').read_text(encoding='utf-8'))
        if m['status']=='planned':
            assert m['enabled'] is False and not m['description'] and not m['metric_ids']
            assert not m['parameters_schema_body'].get('properties') and not m['result_schema_body'].get('properties')
        modules[m['id']]=m
    topo({**{'shots':[],'movement':['shots'],'bursts':['shots'],'engagements':['bursts']},**{k:v['feature_dependencies'] for k,v in modules.items()}})
    return dict(sorted(modules.items(),key=lambda kv:(kv[1].get('order',99),kv[0])))

class Analyzer:
    def __init__(self, manifest): self.manifest=manifest
    def describe(self): return self.manifest
    def validate(self,context,parameters):
        validate(parameters,self.manifest['parameters_schema_body'])
        return {'valid':True,'requirements_met':capability_expr(self.manifest['requires'].get('capabilities'),context.capabilities)}
    def plan(self,context,parameters): return {'tables':self.manifest['requires'].get('tables',[]),'features':self.manifest['feature_dependencies']}
    def analyze(self,context,parameters,cancellation,progress):
        fn=importlib.import_module('backend.modules.'+self.manifest['id']+'.analyzer').analyze
        return fn(context,parameters,cancellation,progress)
