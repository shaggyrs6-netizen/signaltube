import json
import time
from datetime import datetime,timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import live,library,dashboard,shortlist
from signaltube.webapp import create_app

@pytest.fixture
def data(tmp_path,monkeypatch):
    state=tmp_path/'state';now=time.time()
    monkeypatch.setattr(live,'CHANNELS',[('UC'+str(i)*22,f'Creator {i}',f'Topic {i}') for i in range(8)])
    with live.database(state) as db:
        with db:
            db.execute('INSERT INTO quota VALUES(?,45)',(live.quota_day(now),))
            for i,(key,_,_) in enumerate(live.CHANNELS):
                db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(f'VID{i:08}',key,'Video '+str(i),datetime.fromtimestamp(now-3600-i,timezone.utc).isoformat(),now,now,1))
    return state,tmp_path/'takeout'


def test_manual_plan_references_survive_and_no_get_build(data):
    state,root=data;options=dict(profile='local',category='',use_history=False,exclude_history=False)
    assert dashboard.page(state,root)['generated'] is None
    dashboard.build_plan(state,root,options)
    with library.personal(state) as db:
        row=dict(db.execute('SELECT * FROM watch_plan').fetchone())
        assert 'Video' not in row['fingerprints'] and 'VID' not in row['fingerprints']
        assert all(len(fp)==64 for fp in json.loads(row['fingerprints']))
    with patch.object(shortlist,'build',side_effect=AssertionError('No build on GET')),patch.object(live,'read_key',side_effect=AssertionError('No key')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
        first=dashboard.page(state,root)
        assert len(first['picks'])==5 and len(first['alternatives'])==3
        dashboard.video_action(state,first['picks'][0]['id'],'watched')
        again=dashboard.page(state,root)
        assert len(again['picks'])==4 and len(again['alternatives'])==3
        assert again['generated']==first['generated'] and again['unavailable_plan']==1
    assert live.status(state)['used']==45


def test_actions_undo_preserves_categories_and_independent_saved(data):
    state,root=data;vid='VID00000000'
    library.video_save(state,dict(video=vid,action='update',review='reviewed',categories='Custom'))
    dashboard.video_action(state,vid,'save')
    assert dashboard.page(state,root,'saved')['saved_count']==1
    dashboard.video_action(state,vid,'watched')
    page=dashboard.page(state,root,'saved');assert page['saved_count']==1
    token=page['undo']['token'];dashboard.undo(state,token)
    with library.personal(state) as db:
        row=db.execute('select * from video_preferences where fingerprint=?',(library.fingerprint(vid),)).fetchone()
        assert row['saved']==1 and row['review']=='reviewed' and json.loads(row['categories'])==['Custom']
    with pytest.raises(ValueError):dashboard.undo(state,token)


def test_undo_cannot_overwrite_newer_or_legacy_edits(data):
    state,root=data;vid='VID00000000'
    dashboard.video_action(state,vid,'dismiss');old=dashboard.page(state,root)['undo']['token']
    dashboard.video_action(state,vid,'save')
    with pytest.raises(ValueError):dashboard.undo(state,old)
    token=dashboard.page(state,root)['undo']['token']
    library.video_save(state,dict(video=vid,action='restore'))
    with pytest.raises(ValueError):dashboard.undo(state,token)
    assert dashboard.page(state,root)['pending']==8


def test_expired_untracked_hidden_and_undo_without_metadata(data,monkeypatch):
    state,root=data;vid='VID00000000'
    dashboard.build_plan(state,root,dict(profile='local',category='',use_history=False,exclude_history=False))
    dashboard.video_action(state,vid,'save');token=dashboard.page(state,root)['undo']['token']
    with live.database(state) as db:
        with db:db.execute('UPDATE uploads SET fetched=0 WHERE id=?',(vid,))
    page=dashboard.page(state,root,'saved')
    assert page['unavailable_saved']==1 and page['unavailable_plan']==1
    with pytest.raises(ValueError):dashboard.video_action(state,vid,'watched')
    dashboard.undo(state,token)
    assert dashboard.page(state,root,'saved')['unavailable_saved']==0
    monkeypatch.setattr(live,'CHANNELS',live.CHANNELS[:2])
    assert len(dashboard.page(state,root)['picks'])==1


def test_web_csrf_filter_pagination_and_restart(data,tmp_path):
    state,root=data
    def client():
        c=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765');c.get('/?token=test');return c
    c=client();h={'origin':'http://127.0.0.1:8765'}
    assert 'Ready to build your five' in c.get('/watch').text
    assert '8' in c.get('/watch?view=catchup').text
    f=dict(csrf='test',profile='local')
    assert c.post('/watch/build',data=f).status_code==403
    assert c.post('/watch/build',data={**f,'csrf':'bad'},headers=h).status_code==400
    assert c.post('/watch/build',data=f,headers=h).status_code==200
    c=client()
    with patch.object(shortlist,'build',side_effect=AssertionError('No automatic build')),patch.object(live,'refresh',side_effect=AssertionError('No refresh')):
        assert 'START HERE' in c.get('/watch').text
        fields=dict(csrf='test',view='catchup',video='VID00000000',action='dismiss',query='Video 0')
        page=c.post('/watch/action',data=fields,headers=h)
        assert page.status_code==200 and 'Nothing matches this view' in page.text
        assert c.post('/watch/action',data={**fields,'csrf':'bad'},headers=h).status_code==400
        assert c.get('/watch?view=bad').status_code==400
        token=dashboard.page(state,root)['undo']['token']
        assert c.post('/watch/undo',data=dict(csrf='test',undo_token=token),headers=h).status_code==200
    assert live.status(state)['used']==45
