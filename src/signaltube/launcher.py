"""On-demand local server; no login startup, scheduler or YouTube refresh."""
import fcntl
import json
import os
import secrets
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import webbrowser
from . import live


def session_token(state=live.STATE):
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=state/'session.token'
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ValueError('Local session file must be owner-only (mode 600).')
        token=f.read(128)
    if len(token)!=43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in token):
        raise ValueError('Invalid local session file. No credential was replaced.')
    return token


def running(token,port):
    req=urllib.request.Request(f'http://127.0.0.1:{port}/local-status',headers={'Cookie':'signaltube_session='+token})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=1) as response:
            data=json.loads(response.read(1024))
        return data if data.get('app')=='signaltube' and isinstance(data.get('pid'),int) and data['pid']>1 else None
    except (OSError,ValueError):return None


def manage(command,db,port=8765,open_browser=True):
    if not 1024<=port<=65535:raise ValueError('Use an unprivileged port from 1024 to 65535.')
    token=session_token()
    with (live.STATE/'launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current=running(token,port)
        if command=='status':
            print('SignalTube is running.' if current else 'SignalTube is stopped or this port belongs to another session.')
            return
        if command=='stop':
            if current:
                os.kill(current['pid'],signal.SIGTERM)
                for _ in range(50):
                    if not running(token,port):break
                    time.sleep(.1)
                else:raise ValueError('Server has not stopped yet; no force kill attempted.')
            print('SignalTube stopped.' if current else 'No matching SignalTube server to stop.')
            return
        if not current:
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1',port))==0:
                    raise ValueError('Port is occupied by another process or an older SignalTube session. Nothing stopped. Use another --port or stop that session first.')
            log=live.STATE/'server.log'
            fd=os.open(log,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'ab') as output:
                child=subprocess.Popen([sys.executable,'-m','signaltube.cli','--db',str(db),'serve','--port',str(port)],
                    cwd=live.ROOT,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
            for _ in range(50):
                current=running(token,port)
                if current:break
                if child.poll() is not None:break
                time.sleep(.1)
            if not current:raise ValueError('Server did not become ready. See var/server.log. No refresh was attempted.')
        url=f'http://127.0.0.1:{port}/?token={token}'
        print('SignalTube is ready. Open this private local launch link:\n'+url+'\nStop with: ./run.sh stop\nNo YouTube refresh was made.')
        if open_browser:
            if not webbrowser.open(url):print('Browser did not open automatically; use the launch link above.')
