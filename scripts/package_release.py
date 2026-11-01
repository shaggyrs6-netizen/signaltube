"""Bundle only reviewed public installer assets; run after uv build."""
from pathlib import Path
import argparse
import shutil
import hashlib
import tarfile
import tomllib
import zipfile

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dist-dir',type=Path,default=root/'dist',help='Directory containing the built wheel and source archive')
out=parser.parse_args().dist_dir.resolve()
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
tag=version.replace('b','-beta.')
wheel=out/f'signaltube-{version}-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    names=archive.namelist()
    assert 'signaltube/web/templates/setup.html' in names
    assert 'signaltube/desktop.svg' in names
    assert 'signaltube/demo/watch-history.json' in names
    assert not any('/var/' in n or '/secrets/' in n or n.endswith(('.sqlite3','.key','.log')) for n in names)
folder=f'signaltube-desktop-{tag}'
bundle=out/f'{folder}-linux.tar.gz'
files={wheel:wheel.name,root/'packaging/install.py':'install.py'}
for name in ['README.md','DESKTOP-PACKAGING.md','API-SETUP.md','TESTING.md','RECOVERY.md','CHANGELOG.md','LICENSE']:
    files[root/name]=name
if (root/'BETA-ACCEPTANCE.md').exists():files[root/'BETA-ACCEPTANCE.md']='BETA-ACCEPTANCE.md'
files[root/'assets/signaltube-cover.png']='assets/signaltube-cover.png'
files[root/'assets/signaltube-thumbnails.png']='assets/signaltube-thumbnails.png'
with tarfile.open(bundle,'w:gz') as archive:
    for source,name in files.items(): archive.add(source,arcname=f'{folder}/{name}')
screenshot=out/'signaltube-thumbnails.png'
shutil.copyfile(root/'assets/signaltube-thumbnails.png',screenshot)
assets=[bundle,wheel,out/f'signaltube-{version}.tar.gz',screenshot]
(out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))
print('\n'.join(str(p) for p in assets))
