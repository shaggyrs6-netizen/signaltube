"""Actual child-process restarts with fictional data; API-key access prohibited."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from signaltube import live

SERVER = '''
import sys
from pathlib import Path
from signaltube import live
from signaltube.webapp import create_app
import uvicorn
state=Path(sys.argv[1]);port=int(sys.argv[2])
live.CHANNELS=[('UC'+'A'*22,'Fictional restart creator','Testing')]
def blocked(*args,**kwargs):raise AssertionError('No API key access allowed in restart test')
live.read_key=blocked
uvicorn.run(create_app(state/'demo.sqlite3',token='restart-test',port=port,live_state=state,takeout_root=state/'takeout'),host='127.0.0.1',port=port,access_log=False,log_level='error')
'''


def test_real_process_restart_save_watched_dismiss_undo(tmp_path):
    state=tmp_path/'state';now=time.time();vid='TEST0000001'
    with live.database(state) as db:
        with db:
            db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(vid,'UC'+'A'*22,'Fictional restart video',datetime.fromtimestamp(now-3600,timezone.utc).isoformat(),now,now,1))
            db.execute('INSERT INTO quota VALUES(?,45)',(live.quota_day(now),))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    process=None;generations=[];build_time=None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path):
        req=urllib.request.Request(base+path,headers={'Cookie':'signaltube_session=restart-test'})
        with opener.open(req,timeout=3) as r:return r.read().decode()
    def post(path,**fields):
        req=urllib.request.Request(base+path,data=urllib.parse.urlencode(dict(csrf='restart-test',**fields)).encode(),headers={'Cookie':'signaltube_session=restart-test','Origin':base,'Content-Type':'application/x-www-form-urlencoded'})
        with opener.open(req,timeout=3) as r:return r.read().decode()
    def start():
        nonlocal process
        process=subprocess.Popen([sys.executable,'-c',SERVER,str(state),str(port)],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:raise AssertionError('Synthetic server exited')
            try:
                info=json.loads(get('/local-status'))
                generations.append(info['pid']);return
            except OSError:time.sleep(.05)
        raise AssertionError('Synthetic server did not become ready')
    def restart():
        process.terminate();process.wait(timeout=10);start()
    def prefs():
        import sqlite3
        with sqlite3.connect(state/'personal.sqlite3') as db:
            row=db.execute('SELECT saved,review,categories FROM video_preferences').fetchone()
            plan=db.execute('SELECT generated,fingerprints FROM watch_plan').fetchone()
            undo=db.execute('SELECT token FROM watch_undo').fetchone()
        return row,plan,undo[0] if undo else None
    def act(action):post('/watch/action',video=vid,action=action)
    try:
        start()
        post('/watch/build',profile='test')
        _,initial_plan,_=prefs()
        act('save');token=prefs()[2];restart()
        assert prefs()[0]==(1,'unreviewed',None) and prefs()[2]==token
        assert 'Fictional restart video' in get('/watch?view=saved')
        post('/watch/undo',undo_token=token);restart()
        assert prefs()[0] is None and prefs()[2] is None
        act('save');act('watched');token=prefs()[2];restart()
        assert prefs()[0]==(1,'marked watched',None) and prefs()[2]==token
        assert 'Nothing matches this view' in get('/watch?view=catchup')
        assert 'Fictional restart video' in get('/watch?view=saved')
        post('/watch/undo',undo_token=token);restart()
        assert prefs()[0]==(1,'unreviewed',None)
        act('dismiss');token=prefs()[2];restart()
        assert prefs()[0]==(1,'dismissed',None) and prefs()[2]==token
        assert 'Nothing eligible remains' in get('/watch')
        post('/watch/undo',undo_token=token);restart()
        assert prefs()[0]==(1,'unreviewed',None) and prefs()[2] is None
        assert 'START HERE' in get('/watch')
        assert prefs()[1]==initial_plan # No automatic regeneration across visits/restarts.
        with live.database(state) as db:
            assert db.execute('SELECT used FROM quota').fetchone()[0]==45
            assert db.execute('SELECT count(*) FROM uploads').fetchone()[0]==1
        assert len(generations)==7 and len(set(generations))==7
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=10)
