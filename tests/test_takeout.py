import json
import socket
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import takeout,live
from signaltube.webapp import create_app,ROOT

FIX=ROOT/'tests/fixtures'

def prepare(root,**kw):
    return takeout.prepare('lee',FIX/'subscriptions.csv',kw.get('history',FIX/'watch-history.json'),root)

def test_preview_no_writes_and_import_dedup(tmp_path):
    root=tmp_path/'real'
    plan=prepare(root)
    assert not root.exists()
    assert plan['report']['events_added']==7 and plan['report']['event_duplicates']==1
    with pytest.raises(ValueError):takeout.commit(plan,'wrong')
    assert not root.exists()
    result=takeout.commit(plan,plan['preview_id'])
    assert result['resulting_events']==7
    assert (root/'lee.sqlite3').stat().st_mode & 0o777==0o600
    assert root.stat().st_mode & 0o777==0o700
    plan=prepare(root);assert plan['report']['events_added']==0
    takeout.commit(plan,plan['preview_id'])
    plan=takeout.prepare('lee',None,FIX/'history-overlap.json',root)
    assert plan['report']['events_added']==1
    takeout.commit(plan,plan['preview_id'])
    assert takeout.overview('lee',root)['summary']['events']==8

def test_changed_files_and_database_refuse_stale_confirmation(tmp_path):
    file=tmp_path/'history.json';file.write_text((FIX/'watch-history.json').read_text())
    root=tmp_path/'real';plan=prepare(root,history=file)
    file.write_text('[]')
    with pytest.raises(ValueError,match='changed'):takeout.commit(plan,plan['preview_id'])
    assert not (root/'lee.sqlite3').exists()
    a=prepare(root);b=prepare(root);takeout.commit(a,a['preview_id'])
    with pytest.raises(ValueError,match='changed'):takeout.commit(b,b['preview_id'])

def test_atomic_pair_rollback(tmp_path):
    root=tmp_path/'real';plan=prepare(root)
    with pytest.raises(RuntimeError):takeout.commit(plan,plan['preview_id'],fail_after=2)
    with sqlite3.connect(root/'lee.sqlite3') as db:
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]==0
    plan=prepare(root);takeout.commit(plan,plan['preview_id'])
    plan=takeout.prepare('lee',None,FIX/'history-overlap.json',root)
    with pytest.raises(RuntimeError):takeout.commit(plan,plan['preview_id'],fail_after=2)
    assert takeout.overview('lee',root)['summary']['events']==7

def test_unsubscribed_creator_missing_video_and_unrelated_activity(tmp_path):
    cid='UC'+'Z'*22
    rows=[{'title':'Watched Example','titleUrl':'https://www.youtube.com/shorts/ABCDEF12345','time':'2026-10-01T10:00:00-05:00','subtitles':[{'name':'Other creator','url':'https://www.youtube.com/channel/'+cid}]},
          {'title':'Watched unavailable video','time':'2026-10-02T15:00:00Z'},
          {'title':'Searched for something','time':'2026-10-03T15:00:00Z'},
          {'title':'Watched invalid time','time':'bad'}]
    p=tmp_path/'history.json';p.write_text(json.dumps(rows))
    root=tmp_path/'real';plan=takeout.prepare('lee',None,p,root)
    assert plan['report']['events_added']==2
    assert plan['report']['non_watch_rows_skipped']==1 and plan['report']['invalid_rows']==1
    takeout.commit(plan,plan['preview_id']);data=takeout.overview('lee',root)
    assert data['creators'][0]['name']=='Other creator' and data['creators'][0]['subscribed']==0
    assert data['summary']['unavailable']==1 and data['summary']['unresolved']==1

def test_json_streaming_and_invalid_format(tmp_path):
    p=tmp_path/'history.json'
    p.write_text(json.dumps([{'title':'Watched '+('a'*70000),'time':'2026-10-01T00:00:00Z'}]))
    assert len(list(takeout.json_rows(p)))==1
    for content in ('[{},]','[{}','[]{}','<html>hello</html>','{}'):
        p.write_text(content)
        with pytest.raises(ValueError):list(takeout.json_rows(p))

def test_profiles_and_history_first(tmp_path):
    root=tmp_path/'real'
    a=takeout.prepare('lee',None,FIX/'watch-history.json',root);takeout.commit(a,a['preview_id'])
    assert takeout.overview('lee',root)['summary']['subscriptions']==0
    a=takeout.prepare('lee',FIX/'subscriptions.csv',None,root);takeout.commit(a,a['preview_id'])
    data=takeout.overview('lee',root)
    assert data['summary']['subscriptions']==3 and data['summary']['events']==7
    b=takeout.prepare('second',None,FIX/'history-overlap.json',root);takeout.commit(b,b['preview_id'])
    assert takeout.overview('second',root)['summary']['events']==2
    assert takeout.overview('lee',root)['summary']['events']==7
    with pytest.raises(ValueError):takeout.profile_path('../outside',root)
    with pytest.raises(ValueError):takeout.profile_path('synthetic-demo',root)

def test_offline_and_separate_ui(tmp_path):
    root=tmp_path/'real'
    def denied(*a,**k):raise AssertionError('Network/key use attempted')
    with patch.object(socket.socket,'connect',denied),patch.object(live,'read_key',denied):
        plan=prepare(root);takeout.commit(plan,plan['preview_id'])
        app=create_app(tmp_path/'demo.sqlite3',token='t',live_state=tmp_path/'live',takeout_root=root)
        with TestClient(app,base_url='http://127.0.0.1:8765') as c:
            c.get('/?token=t')
            html=c.get('/takeout?profile=lee').text
            assert 'Hangar Notebook' in html and 'PRIVATE' in html
            assert 'No real data imported' in c.get('/takeout?profile=empty').text
            assert c.get('/takeout?profile=../escape').status_code==400
            assert 'Your library is empty' in c.get('/').text
    assert not (root/'empty.sqlite3').exists()
    assert live.status(tmp_path/'live')['used']==0
    with pytest.raises(ValueError):create_app(root/'lee.sqlite3',live_state=tmp_path/'live',takeout_root=root)
