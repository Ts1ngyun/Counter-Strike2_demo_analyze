"""Distribution must never capture user demos, caches or installed runtimes."""
import importlib.util
from pathlib import Path
import pytest
from backend.version import APP_VERSION
from backend.main import health, app

spec=importlib.util.spec_from_file_location('packager',Path(__file__).parents[1]/'scripts/package_source.py')
packager=importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


@pytest.mark.parametrize('relative',[
    'data/uploads/private.dem','frontend/public/private.DEM','docs/ui-redesign-private.DEM',
    'data/profiles.sqlite','data/results/report.json','.venv/config.json',
    'frontend/node_modules/package.json','backend/__pycache__/main.pyc',
    'docs/ui-redesign-log.log','frontend/public/archive.ZIP',
])
def test_private_or_generated_files_excluded(relative):
    assert not packager.included(packager.APP/relative)


def test_release_identity_and_required_files():
    assert APP_VERSION=='1.0.1'
    assert health()['version']==app.version==APP_VERSION
    assert 'VERSION' in packager.ROOT_FILES
    assert packager.OUTER_FILES=={'START.cmd','STOP.cmd','使用说明.txt'}
    assert all((packager.APP.parent/name).is_file() for name in packager.OUTER_FILES)
    assert packager.included(packager.APP/'backend/version.py')
    assert packager.included(packager.APP/'docs/STATIC_MATCH_HIGHLIGHTS.md')
