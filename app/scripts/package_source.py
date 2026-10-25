"""Build a portable source handoff (stdlib only; never includes runtime data)."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

APP = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.gitignore', 'README.md', 'requirements.lock', 'setup.cmd',
              'setup.ps1', 'start.cmd', 'start.ps1', 'stop.cmd', 'stop.ps1'}
SOURCE_DIRS = {'backend', 'tests', 'module_template'}
EXCLUDED_PARTS = {'__pycache__', 'node_modules', '.venv', 'data', '.pytest_cache',
                  '.git', '.npm-cache', '.pip-cache'}


def included(path):
    rel = path.relative_to(APP)
    if any(p in EXCLUDED_PARTS for p in rel.parts) or path.is_symlink():
        return False
    if path.suffix in {'.pyc', '.pyo', '.dem'}:
        return False
    if len(rel.parts) == 1:
        return rel.name in ROOT_FILES
    if rel.parts[0] in SOURCE_DIRS:
        return path.suffix in {'.py', '.json', '.yaml', '.yml', '.md'} or rel.name == '.gitkeep'
    if rel.parts[0] == 'docs':
        return path.suffix == '.md' or rel.name in {'test-results.txt','ui-evidence.png','revision-ui-stop.png','revision-validation.json','ui-appearance-light.png','ui-appearance-dark.png','replay-ui-map.png','review-ui-flash.png','review-ui-combat.png','review-ui-profiles.png','review-v3-validation.json','flash-validation.json'}
    if rel.parts[0] == 'scripts':
        return path.suffix == '.py' and rel.name != 'probe.py'
    if rel.parts[0] == 'frontend':
        return (rel.parts[1] in {'src', 'dist', 'public'} or
                (len(rel.parts) == 2 and rel.name in {
                    'package.json', 'package-lock.json', 'tsconfig.json',
                    'vite.config.ts', 'index.html'}))
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=APP.parent / 'deliverables')
    args = parser.parse_args()
    if not (APP / 'frontend/dist/index.html').is_file():
        raise SystemExit('Build frontend first: cd frontend && npm run build')
    files = sorted(p for p in APP.rglob('*') if p.is_file() and included(p))
    names = {p.relative_to(APP).as_posix() for p in files}
    required = ROOT_FILES | {'backend/main.py', 'frontend/dist/index.html',
                            'docs/PARTNER_HANDOFF.md', 'docs/MODULE_HANDOFF_TEMPLATE.md'}
    if missing := required - names:
        raise SystemExit(f'Missing required files: {sorted(missing)}')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = args.output_dir / f'CS2-Demo-Lab-source-{stamp}.zip'
    entries = []
    with ZipFile(target, 'x', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = 'app/' + path.relative_to(APP).as_posix()
            body = path.read_bytes()
            archive.writestr(name, body)
            entries.append({'path': name, 'bytes': len(body),
                            'sha256': hashlib.sha256(body).hexdigest()})
        archive.writestr('app/SOURCE_MANIFEST.json', json.dumps({
            'format_version': 1, 'created_utc': stamp,
            'package_kind': 'source; install dependencies before running',
            'files': entries,
        }, ensure_ascii=False, indent=2))
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        for entry in entries:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(target.resolve()), 'bytes': target.stat().st_size,
                      'files': len(entries), 'sha256': digest}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
