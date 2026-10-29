import json
import sqlite3
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import live,library,shortlist
from signaltube.webapp import create_app

@pytest.fixture
def sample(tmp_path,monkeypatch):
    now=time.time();state=tmp_path/'live';root=tmp_path/'takeout';root.mkdir()
    channels=[('UC'+str(i)*22,f'Creator {i}','Gaming' if i<3 else f'Topic {i}') for i in range(7)]
    monkeypatch.setattr(live,'CHANNELS',channels)
    with live.database(state) as db:
        with db:
            db.execute('INSERT INTO quota VALUES(?,32)',(live.quota_day(now),))
            for i,(key,name,cat) in enumerate(channels):
                for n in range(2):
                    db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(f'VID{i:07}{n}',key,f'Video {i}/{n}',__import__('datetime').datetime.fromtimestamp(now-3600-n,__import__('datetime').timezone.utc).isoformat(),now,now,1))
    with sqlite3.connect(root/'lee.sqlite3') as db:
        db.executescript('CREATE TABLE events(video_id TEXT,creator_id TEXT,time TEXT);CREATE TABLE videos(id TEXT,creator_id TEXT);')
        db.executemany('INSERT INTO events VALUES(?,?,?)',[(f'old{i}',channels[5][0],'2026-10-20T00:00:00Z') for i in range(100)])
        db.execute('INSERT INTO events VALUES(?,?,?)',('VID00000060',channels[6][0],'2026-10-20T00:00:00Z'))
    return state,root,now,channels


def test_five_unique_deterministic_explained_no_network(sample):
    state,root,now,channels=sample
    with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch.object(live,'read_key',side_effect=AssertionError('No key access')):
        data=shortlist.build(state,root,now=now)
        again=shortlist.build(state,root,now=now)
    assert data==again
    assert len(data['picks'])==5 and len(data['alternatives'])==2
    assert len({v['handle'] for v in data['picks']+data['alternatives']})==7
    for v in data['picks']+data['alternatives']:
        assert v['score']==sum(r['points'] for r in v['reasons'])-v['adjustment']
    assert data['picks'][0]['handle']==channels[5][0]
    assert data['excluded']['history']==1
    assert data['quota']==32 and live.status(state)['used']==32


def test_preferences_exclusions_and_diversity(sample):
    state,root,now,channels=sample
    library.creator_save(state,dict(handle=channels[0][0],categories='Gaming',favourite='1',pinned='1'))
    library.video_save(state,dict(video='VID00000000',action='dismiss'))
    library.video_save(state,dict(video='VID00000010',action='update',review='marked watched'))
    data=shortlist.build(state,root,category='Topic 4',now=now)
    assert data['picks'][0]['handle']==channels[0][0]
    assert data['picks'][0]['id']=='VID00000001'
    assert data['excluded']['local_state']==2
    assert any(r['label']=='Your chosen category: Topic 4' for v in data['picks'] for r in v['reasons'])
    chosen=data['picks']+data['alternatives']
    assert all(v['id'] not in ('VID00000000','VID00000010','VID00000060') for v in chosen)
    assert sum(v['adjustment']>0 for v in chosen)>=2


def test_missing_history_disabled_history_and_empty(sample):
    state,root,now,_=sample
    assert shortlist.build(state,root,profile='missing',now=now)['history_available'] is False
    data=shortlist.build(state,root,use_history=False,exclude_history=False,now=now)
    assert data['excluded']['history']==0 and data['history_available'] is None
    assert not any('imported watch' in r['label'] for v in data['picks'] for r in v['reasons'])
    with pytest.raises(ValueError):shortlist.build(state,root,profile='../demo')
    with pytest.raises(ValueError):shortlist.build(state,root,category='made up')
    with live.database(state) as db:
        with db:db.execute('DELETE FROM uploads')
    assert shortlist.build(state,root,now=now)['picks']==[]


def test_web_manual_build_guard_and_escaping(sample,tmp_path):
    state,root,now,_=sample
    with live.database(state) as db:
        with db:db.execute("UPDATE uploads SET title='<script>bad</script>'")
    client=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765')
    client.get('/?token=test')
    with patch.object(shortlist,'build',side_effect=AssertionError('GET must not build')):
        page=client.get('/shortlist')
        assert page.status_code==200 and 'Nothing generated yet' in page.text
    headers={'origin':'http://127.0.0.1:8765'}
    fields=dict(csrf='test',profile='lee',use_history='1',exclude_history='1')
    assert client.post('/shortlist/build',data=fields).status_code==403
    assert client.post('/shortlist/build',data={**fields,'csrf':'bad'},headers=headers).status_code==400
    with patch('socket.socket.connect',side_effect=AssertionError('No network')):
        page=client.post('/shortlist/build',data=fields,headers=headers)
    assert page.status_code==200 and 'Your 5 picks' in page.text
    assert '&lt;script&gt;' in page.text and '<script>bad' not in page.text
    assert '/theme.css' in page.text and '32/100' in page.text
    assert live.status(state)['used']==32

def test_video_override_saved_and_small_pool(sample):
    state,root,now,channels=sample
    library.video_save(state,dict(video='VID00000000',action='save'))
    library.video_save(state,dict(video='VID00000000',action='update',review='reviewed',categories='Personal focus'))
    with live.database(state) as db:
        with db:db.execute('DELETE FROM uploads WHERE handle!=?',(channels[0][0],))
    data=shortlist.build(state,root,category='Personal focus',now=now)
    assert len(data['picks'])==1 and data['alternatives']==[]
    assert data['picks'][0]['id']=='VID00000000'
    assert data['picks'][0]['categories']==['Personal focus']
    assert any(r['label']=='Saved for later' for r in data['picks'][0]['reasons'])


def test_expired_and_future_items_not_recommended(sample):
    state,root,now,_=sample
    with live.database(state) as db:
        with db:
            db.execute("UPDATE uploads SET published='2099-01-01T00:00:00+00:00' WHERE id='VID00000000'")
            db.execute("UPDATE uploads SET fetched=0 WHERE id='VID00000010'")
    data=shortlist.build(state,root,now=now)
    assert data['excluded']['invalid_date']==1
    assert all(v['id'] not in ('VID00000000','VID00000010') for v in data['picks']+data['alternatives'])

def test_options_save_without_generation_survives_restart(sample,tmp_path):
    state,root,_,_=sample
    def client():
        c=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765')
        c.get('/?token=test');return c
    c=client();headers={'origin':'http://127.0.0.1:8765'}
    fields=dict(csrf='test',profile='another',category='Gaming',exclude_history='1')
    with patch.object(shortlist,'build',side_effect=AssertionError('No generation')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
        assert c.post('/shortlist/options',data=fields).status_code==403
        assert c.post('/shortlist/options',data={**fields,'csrf':'bad'},headers=headers).status_code==400
        assert c.post('/shortlist/options',data=fields,headers=headers).status_code==200
        c=client();page=c.get('/shortlist')
        assert 'Nothing generated yet' in page.text
        assert 'value="another"' in page.text and 'value="Gaming" selected' in page.text
        opts,_=shortlist.options_load(state,['Gaming'])
        assert opts==dict(profile='another',category='Gaming',use_history=False,exclude_history=True)
        assert c.post('/shortlist/options',data={**fields,'profile':'../bad'},headers=headers).status_code==400
        assert shortlist.options_load(state,['Gaming'])[0]==opts
    assert live.status(state)['used']==32


def test_build_remembers_unchecked_options_and_missing_category(sample,tmp_path):
    state,root,_,_=sample
    c=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765');c.get('/?token=test')
    headers={'origin':'http://127.0.0.1:8765'}
    assert c.post('/shortlist/build',data=dict(csrf='test',profile='lee',category='Gaming'),headers=headers).status_code==200
    opts,notice=shortlist.options_load(state,[])
    assert opts==dict(profile='lee',category='',use_history=False,exclude_history=False)
    assert 'no longer available' in notice
    with patch.object(shortlist,'build',side_effect=AssertionError('GET must not build')):
        assert 'Nothing generated yet' in c.get('/shortlist').text
