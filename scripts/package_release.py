"""Bundle only reviewed public installer assets; run after uv build."""
from pathlib import Path
import hashlib
import tarfile
import tomllib
import zipfile

root=Path(__file__).resolve().parents[1]
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
tag=version.replace('b','-beta.')
wheel=root/'dist'/f'signaltube-{version}-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    names=archive.namelist()
    assert 'signaltube/web/templates/setup.html' in names
    assert 'signaltube/desktop.svg' in names
    assert 'signaltube/demo/watch-history.json' in names
    assert not any('/var/' in n or '/secrets/' in n or n.endswith(('.sqlite3','.key','.log')) for n in names)
folder=f'signaltube-desktop-{tag}'
bundle=root/'dist'/f'{folder}-linux.tar.gz'
files={wheel:wheel.name,root/'packaging/install.py':'install.py'}
for name in ['README.md','DESKTOP-PACKAGING.md','API-SETUP.md','TESTING.md','RECOVERY.md','CHANGELOG.md','LICENSE']:
    files[root/name]=name
with tarfile.open(bundle,'w:gz') as archive:
    for source,name in files.items(): archive.add(source,arcname=f'{folder}/{name}')
assets=[bundle,wheel,root/'dist'/f'signaltube-{version}.tar.gz']
(root/'dist/SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))
print('\n'.join(str(p) for p in assets))
