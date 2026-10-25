"""Regressions found by independent flash-agent review of personal archives."""
import copy
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.routers import profiles


def saved_result(job_id='old'):
    metric = {'module_id': 'test', 'metric_id': 'rate', 'scope': {'player_id': '111'},
              'value': .5, 'unit': 'ratio', 'aggregation': 'ratio_of_sums', 'numerator': 1, 'denominator': 2,
              'algorithm_version': '1', 'parameter_snapshot': {}, 'eligible_count': 2, 'evaluated_count': 2,
              'unknown_count': 0, 'identities': {'provider': 'provider-v1', 'module_code': {'analyzer.py': 'abc'},
              'common_code': 'common-v1', 'features': {'code': 'features-v1', 'version': '1', 'facts': {'demo_hash': 'a' * 64}},
              'facts': {'demo_hash': 'a' * 64, 'normalization': '1', 'parser': {'name': 'parser', 'version': '1'}, 'adapter_code': 'adapter-v1'}}}
    return {'job_id': job_id, 'demo': {'demo_hash': 'a' * 64, 'header': {'map_name': 'test'}},
            'players': [{'player_id': '111', 'name': 'Player'}], 'rounds': [],
            'modules': {'test': {'status': 'succeeded', 'metrics': [metric], 'evidence': []}}}


def test_identical_resave_preserves_provenance_but_retargets_live_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, 'DATA', tmp_path)
    monkeypatch.setattr(profiles, 'load_result', saved_result)
    app = FastAPI(); app.include_router(profiles.router)
    with TestClient(app) as client:
        pid = client.post('/api/profiles', json={'name': 'Archive'}).json()['id']
        def save(job):
            return client.post(f'/api/profiles/{pid}/entries', json={'job_id': job, 'player_ids': ['111']}).json()['entries'][0]
        entry = save('old')
        new = save('new')
        assert new['action'] == 'already_saved' and new['revision'] == 1
        detail = client.get(f'/api/profiles/{pid}/entries/{entry["id"]}').json()
        assert detail['snapshot']['source_job_id'] == 'old'
        assert detail['current_job_id'] == 'new'


@pytest.mark.parametrize('path,value', [
    (('module_code', 'analyzer.py'), 'changed'),
    (('common_code',), 'changed'),
    (('features', 'code'), 'changed'),
    (('features', 'version'), '2'),
    (('facts', 'adapter_code'), 'changed'),
    (('facts', 'normalization'), '2'),
    (('facts', 'parser', 'version'), '2'),
])
def test_implementation_changes_split_series_even_if_declared_version_matches(path, value):
    snapshot = profiles.player_snapshot(saved_result(), '111')
    metric = snapshot['modules']['test']['metrics'][0]
    changed = copy.deepcopy(metric)
    target = changed['identities']
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert profiles.metric_key('test', metric, snapshot) != profiles.metric_key('test', changed, snapshot)


def test_different_demo_hash_does_not_split_same_implementation():
    snapshot = profiles.player_snapshot(saved_result(), '111')
    metric = snapshot['modules']['test']['metrics'][0]
    changed = copy.deepcopy(metric)
    changed['identities']['facts']['demo_hash'] = 'b' * 64
    changed['identities']['features']['facts']['demo_hash'] = 'b' * 64
    assert profiles.metric_key('test', metric, snapshot) == profiles.metric_key('test', changed, snapshot)
