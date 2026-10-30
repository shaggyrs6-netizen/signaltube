import os
import subprocess
import sys
import pytest
from signaltube.desktop import is_local

def test_navigation_boundary():
    assert is_local('http://127.0.0.1:1234/watch',1234)
    for url in ['https://127.0.0.1:1234/', 'http://127.0.0.1:1235/', 'http://127.0.0.1.evil:1234/', 'http://user@127.0.0.1:1234/', 'file:///etc/passwd','javascript:alert(1)','http://127.0.0.1:bad/']:
        assert not is_local(url,1234)

def test_isolated_data_reaches_every_store(tmp_path):
    env=dict(os.environ,SIGNALTUBE_DATA_DIR=str(tmp_path),PYTHONPATH=str(__import__("pathlib").Path("src").resolve()))
    subprocess.run([sys.executable,'-c',"from signaltube import live,takeout; from signaltube.paths import STATE; assert live.STATE==STATE; assert takeout.ROOT==STATE/'takeout'"],env=env,check=True)

def test_packaged_demo_available(tmp_path):
    from signaltube.webapp import load_demo
    from signaltube.storage import initialise
    db=tmp_path/'demo.db';initialise(db)
    assert len(load_demo(db))==2

@pytest.mark.parametrize("custom", [False, True])
def test_installer_and_removal_preserve_data(tmp_path, custom):
    from pathlib import Path
    import json
    import zipfile
    root=Path(__file__).resolve().parents[1]
    tools=tmp_path/'bin';tools.mkdir()
    uv=tools/'uv'
    uv.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nb=Path(os.environ["FAKE_BIN"])\nif sys.argv[1:3]==["tool","dir"]: print(b)\nelif sys.argv[1:3]==["tool","install"]: (b/"signaltube-desktop").touch()\n')
    uv.chmod(0o755)
    wheel=tmp_path/'candidate.whl'
    with zipfile.ZipFile(wheel,'w') as z:z.writestr('signaltube/desktop.svg','<svg/>')
    data=tmp_path/'data'; config=tmp_path/'config'
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],FAKE_BIN=str(tools),XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(config))
    cmd=[sys.executable,str(root/'packaging/install.py')]
    library=tmp_path/'existing library'; library.mkdir(mode=0o700)
    extra=['--data-dir',str(library)] if custom else []
    subprocess.run(cmd+[str(wheel),'--autostart']+extra,env=env,check=True)
    assert '--background' in (config/'autostart/signaltube.desktop').read_text()
    assert ('Exec=env' if custom else 'Exec="') in (data/'applications/signaltube.desktop').read_text()
    assert ('SIGNALTUBE_DATA_DIR=' in (data/'applications/signaltube.desktop').read_text()) == custom
    private=data/'signaltube';private.mkdir();(private/'library').write_text('keep')
    # Never overwrite an existing installation or edited desktop entry.
    assert subprocess.run(cmd+[str(wheel)],env=env,capture_output=True).returncode!=0
    desktop=data/'applications/signaltube.desktop'; original=desktop.read_text();desktop.write_text(original+'# user edit\n')
    assert subprocess.run(cmd+['--uninstall'],env=env,capture_output=True).returncode!=0
    assert desktop.exists()
    desktop.write_text(original)
    subprocess.run(cmd+['--uninstall'],env=env,check=True)
    assert not desktop.exists()
    assert (private/'library').read_text()=='keep'
