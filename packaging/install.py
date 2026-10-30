#!/usr/bin/env python3
"""Explicit per-user install. No sudo, data migration or login startup by default."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

MARKER = '# Managed by SignalTube desktop installer\n'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('wheel',type=Path,nargs='?')
    p.add_argument('--data-dir',type=Path,help='Reuse an existing private SignalTube data folder without copying it')
    p.add_argument('--autostart',action='store_true',help='Opt in to tray startup at login')
    p.add_argument('--uninstall',action='store_true',help='Remove app commands and owned desktop entries; retain personal data')
    args=p.parse_args()
    uv=shutil.which('uv')
    if not uv: p.error('Install uv first: https://docs.astral.sh/uv/getting-started/installation/')
    data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    desktop=data/'applications/signaltube.desktop'
    auto=config/'autostart/signaltube.desktop'
    icon=data/'icons/hicolor/scalable/apps/signaltube.svg'
    receipt=data/'signaltube-install.json'
    if args.uninstall:
        if not receipt.exists(): p.error('No installer receipt; refusing to remove unknown files.')
        saved=json.loads(receipt.read_text())
        for path in [desktop,auto,icon]:
            if path.exists() and (path.is_symlink() or path.read_text()!=saved.get(str(path))):
                p.error(f'File changed or not owned by this installer; preserving it: {path}')
        subprocess.run([uv,'tool','uninstall','signaltube'],check=True)
        for path in [desktop,auto,icon]:
            if path.exists(): path.unlink()
        receipt.unlink()
        print('App removed. Personal data and API key retained in the SignalTube data folder.')
        return
    if not args.wheel or not args.wheel.is_file(): p.error('Supply the locally built SignalTube wheel.')
    for path in [desktop,auto,icon,receipt]:
        if path.exists() or path.is_symlink(): p.error(f'Existing file preserved: {path}. Use a reviewed upgrade procedure.')
    selected = args.data_dir.expanduser().absolute() if args.data_dir else None
    if selected and (not selected.is_dir() or selected.is_symlink() or selected.stat().st_uid != os.getuid() or selected.stat().st_mode & 0o077):
        p.error('Existing data folder must be owned by you, not a symlink, and mode 700.')
    with zipfile.ZipFile(args.wheel) as z:
        icon_text=z.read('signaltube/desktop.svg').decode()
    subprocess.run([uv,'tool','install','--python','>=3.12',str(args.wheel.resolve())+'[desktop]'],check=True)
    bindir=Path(subprocess.check_output([uv,'tool','dir','--bin'],text=True).strip())
    executable=bindir/'signaltube-desktop'
    if not executable.exists(): raise RuntimeError('Desktop command not installed')
    # Desktop Exec quoting, including literal percent escaping.
    quoted='"'+str(executable).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
    if selected:
        value='SIGNALTUBE_DATA_DIR='+str(selected)
        value=value.replace('\\','\\\\').replace(chr(34),'\\'+chr(34)).replace('`','\\`').replace('$','\\$').replace('%','%%')
        quoted='env '+chr(34)+value+chr(34)+' '+quoted
    entry=MARKER+'[Desktop Entry]\nType=Application\nName=SignalTube\nComment=Less looking. More watching.\nExec='+quoted+'\nIcon=signaltube\nTerminal=false\nCategories=AudioVideo;Video;\nStartupNotify=true\n'
    contents={str(desktop):entry,str(icon):icon_text}
    if args.autostart: contents[str(auto)]=entry.replace('Exec='+quoted,'Exec='+quoted+' --background')
    for name,text in contents.items():
        path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    receipt.write_text(json.dumps(contents,indent=2)+'\n')
    print('Installed. Open SignalTube from your app menu. Login startup: '+str(args.autostart))

if __name__=='__main__': main()
