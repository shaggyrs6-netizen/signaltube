import hashlib
import json
import socket
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import live,library,history
from signaltube.storage import initialise
from signaltube.webapp import create_app,load_demo

@pytest.fixture
def seeded(tmp_path):
    state=tmp_path/'live';now=time.time()
    with live.database(state) as db:
        with db:
            db.execute('INSERT INTO quota VALUES(?,9)',(live.quota_day(now),))
            for i,(handle,_,_) in enumerate(live.CHANNELS):
                for n in range(14):
                    vid=f'ITEM{i:01}{n:06}'
                    db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(vid,handle,f'Video {i} {n}',f'2026-10-{n+1:02}T12:00:00+00:00',now,now,1))
    return state

def test_saved_and_review_are_independent(seeded):
    vid='ITEM0000000'
    library.video_save(seeded,{'video':vid,'action':'save'})
    library.video_save(seeded,{'video':vid,'action':'update','review':'reviewed','categories':'Personal, Aviation'})
    library.preferences_save(seeded,{'view':'saved'})
    data=library.library_data(seeded)
    assert data['total']==1 and data['videos'][0]['saved'] and data['videos'][0]['review']=='reviewed'
    library.video_save(seeded,{'video':vid,'action':'dismiss'})
    assert library.library_data(seeded)['total']==1
    library.preferences_save(seeded,{'view':'inbox'})
    assert library.library_data(seeded)['total']==41
    library.video_save(seeded,{'video':vid,'action':'restore'})
    assert library.library_data(seeded)['total']==42

def test_categories_overrides_pins_and_filters(seeded):
    library.creator_save(seeded,{'handle':'MentourPilot','categories':'Flying, Engineering','favourite':'1','pinned':'1'})
    library.preferences_save(seeded,{'category':'Flying','favourites':'1','start':'2026-10-03','end':'2026-10-05','sort':'oldest'})
    data=library.library_data(seeded)
    assert data['total']==3 and data['videos'][0]['published'].startswith('2026-10-03')
    vid=data['videos'][0]['id'];library.video_save(seeded,{'video':vid,'action':'update','review':'unreviewed','categories':'Custom'})
    assert library.library_data(seeded)['total']==2
    library.creator_save(seeded,{'handle':'MentourPilot','categories':'Renamed','pinned':'1'})
    library.preferences_save(seeded,{'category':'Custom'})
    assert library.library_data(seeded)['total']==1
    library.preferences_save(seeded,{'sort':'favourites'})
    assert library.library_data(seeded)['videos'][0]['handle']=='MentourPilot'

def test_expiry_preserves_only_personal_choices(seeded):
    library.video_save(seeded,{'video':'ITEM0000000','action':'save'})
    with live.database(seeded) as db:
        with db:db.execute('UPDATE uploads SET fetched=0')
    data=library.library_data(seeded)
    assert data['counts']['all']==0 and data['unavailable_saved']==1
    with library.personal(seeded) as db:
        row=db.execute('SELECT * FROM video_preferences').fetchone()
        assert row['fingerprint']==hashlib.sha256(b'ITEM0000000').hexdigest()
        assert row['saved']==1
        assert 'title' not in row.keys()

def test_validation_and_query_pagination(seeded):
    with pytest.raises(ValueError):library.preferences_save(seeded,{'start':'2026-10-31','end':'2026-10-01'})
    with pytest.raises(ValueError):library.creator_save(seeded,{'handle':'unknown'})
    with pytest.raises(ValueError):library.video_save(seeded,{'video':'ITEM9999999','action':'save'})
    with pytest.raises(ValueError):library.categories(','.join(str(i) for i in range(9)))
    library.preferences_save(seeded,{'query':'Video 1','sort':'oldest'})
    assert library.library_data(seeded)['total']==14
    assert len(library.library_data(seeded,page=2)['videos'])==2
    library.preferences_save(seeded,{'reset':'1'})
    assert library.library_data(seeded)['total']==42

def test_ui_persistence_no_network_and_no_quota_change(seeded,tmp_path):
    def blocked(*a,**k):raise AssertionError('Unexpected network/key access')
    demo=tmp_path/'demo.sqlite3'
    def app():return create_app(demo,token='t',live_state=seeded)
    with patch.object(socket.socket,'connect',blocked),patch.object(live,'read_key',blocked):
        with TestClient(app(),base_url='http://127.0.0.1:8765') as c:
            c.get('/?token=t')
            headers={'Origin':'http://127.0.0.1:8765'}
            assert c.post('/live/video',data={'csrf':'t','video':'ITEM0000000','action':'save'},headers=headers).status_code==200
            assert c.post('/live/view',data={'csrf':'t','view':'saved'},headers=headers).status_code==200
            assert c.post('/live/filters',data={'csrf':'t','view':'saved','density':'compact'},headers=headers).status_code==200
            assert c.post('/creators/save',data={'csrf':'t','handle':'MentourPilot','categories':'<script>alert(1)</script>'},headers=headers).status_code==200
            assert '&lt;script&gt;' in c.get('/creators').text
            assert c.post('/live/video',data={'csrf':'wrong','video':'ITEM0000000','action':'dismiss'},headers=headers).status_code==400
        with TestClient(app(),base_url='http://127.0.0.1:8765') as c:
            c.get('/?token=t')
            html=c.get('/live').text
            assert '1 matching' in html and 'live-grid compact' in html and 'Unsave' in html
            assert c.get('/history').status_code==200
    assert live.status(seeded)['used']==9

def test_imported_history_is_not_upload_analytics(tmp_path):
    db=tmp_path/'demo.sqlite3';initialise(db);load_demo(db)
    data=history.report(db)
    assert data['summary']['events']==7
    assert data['months']==[{'month':'2026-10','events':7}]
    assert data['no_records'][0]['name']=='Orbital Workshop'
    assert [c['events'] for c in data['channels']]==[4,2,0]
