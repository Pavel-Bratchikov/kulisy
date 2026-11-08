#!/usr/bin/env python3
"""Build an allowlisted source archive, excluding local data and secrets."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent.parent
output = root / 'artifacts' / 'kulisy-server.tar.gz'
output.parent.mkdir(exist_ok=True)
entries = ['manage.py', 'config', 'events', 'tickets', 'scanning', 'budget', 'reporting',
           'templates', 'static', 'scripts', 'deploy', '.github', 'Dockerfile', 'compose.yaml',
           'compose.proxy.yaml', 'Caddyfile', '.env.example', '.dockerignore', '.gitignore',
           'requirements.txt', 'requirements-dev.txt', 'tests', 'README.md', 'DEPLOY.md']
def clean(info):
    parts = Path(info.name).parts
    if info.issym() or info.islnk() or '__pycache__' in parts or info.name.endswith(('.pyc', '.pyo')):
        return None
    if any(part.startswith('.env') and part != '.env.example' for part in parts):
        return None
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    return info
with tarfile.open(output, 'w:gz') as archive:
    for entry in entries:
        archive.add(root / entry, arcname='kulisy/' + entry, filter=clean)
print(f'Готово: {output} ({output.stat().st_size // 1024} КБ)')
