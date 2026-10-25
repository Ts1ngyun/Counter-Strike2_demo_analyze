"""Versioned result validation shared by every module."""
from jsonschema import Draft202012Validator

METRIC_SCHEMA={
 'type':'object','required':['module_id','metric_id','scope','value','unit','aggregation','numerator','denominator','sample_unit','eligible_count','evaluated_count','unknown_count','excluded_count','coverage','method','quality','limitations','parameter_snapshot','algorithm_version','identities','config_hash','evidence_refs'],
 'properties':{'module_id':{'type':'string'},'metric_id':{'type':'string'},'scope':{'type':'object','properties':{'player_id':{'type':'string','pattern':'^[0-9]+$'}}},'value':{'type':['number','null']},'quality':{'enum':['observed','derived','estimated','unknown']},'eligible_count':{'type':'number','minimum':0},'evaluated_count':{'type':'number','minimum':0},'unknown_count':{'type':'number','minimum':0},'excluded_count':{'type':'number','minimum':0},'coverage':{'type':['number','null'],'minimum':0,'maximum':1},'evidence_refs':{'type':'array','items':{'type':'string'}}}}
EVIDENCE_SCHEMA={'type':'object','required':['evidence_id','demo_hash','round_id','player_id','tick','start_time','end_time','native_resolution_seconds','subtick','source_sequence','raw_field_paths','reason','parameter_snapshot','algorithm_version'],'properties':{'demo_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'},'player_id':{'type':'string'},'source_sequence':{'type':['number','null']},'raw_field_paths':{'type':'array'}}}
metric_validator=Draft202012Validator(METRIC_SCHEMA)
evidence_validator=Draft202012Validator(EVIDENCE_SCHEMA)
