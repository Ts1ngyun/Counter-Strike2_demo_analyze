from pathlib import Path
import duckdb
from .common import read_json
from ..providers import Providers

TABLES={'commands','players','rounds','events','player_states','weapon_states','shots','bursts','engagements','movement'}
class AnalysisContext:
    """Read-only, bounded queries. No parser objects escape the adapter."""
    def __init__(self,root):
        self.root=Path(root); self.meta=read_json(self.root/'demos.json')
        self.capabilities=read_json(self.root/'capabilities.json'); self.fields=read_json(self.root/'fields.json')
        self.providers=Providers(self.meta)
    def query(self,table,player=None,start=None,end=None,round_id=None,limit=None,offset=0):
        if table not in TABLES: raise ValueError('未知事实表')
        paths=sorted((self.root/table).glob('*.parquet'))
        if not paths:
            import pandas as pd
            return pd.DataFrame()
        cond=[]; args=[]
        for field,val,op in [('player_id',player,'='),('tick',start,'>='),('tick',end,'<='),('round_id',round_id,'=')]:
            if val is not None: cond.append('"'+field+'" '+op+' ?'); args.append(val)
        sql='SELECT * FROM read_parquet(?, union_by_name=true)'
        if cond: sql+=' WHERE '+' AND '.join(cond)
        if limit is not None: sql+=' LIMIT ? OFFSET ?'; args += [int(limit),int(offset)]
        with duckdb.connect(':memory:') as con:
            con.execute("SET memory_limit='256MB'"); con.execute('SET threads=2')
            return con.execute(sql,[[str(p) for p in paths]]+args).df()
    def rounds(self): return self.query('rounds').to_dict('records')
