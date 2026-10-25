import io,json,struct
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.adapters.demo.container import scan

client=TestClient(app)
def test_health():assert client.get('/api/health').json()['ok']
def test_bad_magic():assert client.post('/api/upload',files={'file':('bad.dem',b'wrong'*20,'application/octet-stream')}).status_code==400
def test_planned_upload_denied():assert client.post('/api/upload',data={'config':json.dumps({'modules':['role_analysis']})},files={'file':('x.dem',b'PBDEMS2\0'+b'\0'*10)}).status_code==422
def test_csrf():assert client.post('/api/aggregate',json={},headers={'Origin':'https://evil.invalid'}).status_code==403
def test_dns_rebinding():assert client.get('/api/health',headers={'Host':'evil.invalid'}).status_code==403
def test_truncated_container(tmp_path):
    p=tmp_path/'bad.dem';p.write_bytes(b'PBDEMS2\0'+struct.pack('<II',0,0)+bytes([7,1,20])+b'xx')
    with pytest.raises(ValueError,match='截断'):scan(p,tmp_path/'out')
def test_invalid_offset(tmp_path):
    p=tmp_path/'bad.dem';p.write_bytes(b'PBDEMS2\0'+struct.pack('<II',9999,0))
    with pytest.raises(ValueError,match='越界'):scan(p,tmp_path/'out')

def test_batch_uses_total_numerator_and_denominator(monkeypatch):
    from backend import main
    from backend.core.common import metric
    def fake(jid):
        n,d=(1,2) if jid=='a' else (9,10)
        m=metric('synthetic','rate',n/d,{'player_id':'1'},'ratio',n=n,d=d,eligible=d)
        m.update(parameter_snapshot={},algorithm_version='1')
        return {'demo':{'demo_hash':jid},'modules':{'synthetic':{'metrics':[m]}}}
    monkeypatch.setattr(main,'result_of',fake)
    r=client.post('/api/aggregate',json={'job_ids':['a','b','a']}).json()
    assert r['distinct_demos']==2
    m=r['metrics'][0]
    assert m['value']==10/12 and m['denominator']==12 and m['evaluated_count']==12
