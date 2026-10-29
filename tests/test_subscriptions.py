import fcntl
import re
import socket
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import live, takeout, subscriptions, library
from signaltube.webapp import create_app, ROOT

@pytest.fixture
def setup(tmp_path):
    state=tmp_path/'state';root=tmp_path/'takeout'
    plan=takeout.prepare('lee',ROOT/'tests/fixtures/subscriptions.csv',ROOT/'tests/fixtures/watch-history.json',root)
    takeout.commit(plan,plan['preview_id'])
    rows,status=subscriptions.catalogue(state,'lee',root)
    candidate=next(r for r in rows if not r['tracked'])
    return state,root,candidate

def test_preview_apply_persistence_no_network(setup):
    state,root,c=setup
    with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        plan=subscriptions.preview(state,'lee',root,c['key'],'add')
        assert plan['normal']==4 and plan['budget']==8
        assert len(live.current_channels(state))==3
        subscriptions.apply(state,'lee',root,c['key'],'add',plan['revision'])
        assert len(live.current_channels(state))==4
        assert (state/'tracked-channels.json').stat().st_mode & 0o777 == 0o600
        assert live.status(state)['used']==0
        assert len(library.library_data(state)['channels'])==4
        with pytest.raises(ValueError):subscriptions.apply(state,'lee',root,c['key'],'add',plan['revision'])
        remove=subscriptions.preview(state,'lee',root,c['key'],'remove')
        subscriptions.apply(state,'lee',root,c['key'],'remove',remove['revision'])
        assert len(live.current_channels(state))==3
        assert takeout.overview('lee',root)['summary']['events']==7

def test_stale_quota_lock_and_budget_warning(setup):
    state,root,c=setup
    plan=subscriptions.preview(state,'lee',root,c['key'],'add')
    with live.database(state) as db:
        with db:db.execute('INSERT INTO quota VALUES(?,99)',(plan['day'],))
    with pytest.raises(ValueError,match='changed'):subscriptions.apply(state,'lee',root,c['key'],'add',plan['revision'])
    plan=subscriptions.preview(state,'lee',root,c['key'],'add')
    assert plan['budget']>plan['remaining']
    with (state/'refresh.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='running'):subscriptions.apply(state,'lee',root,c['key'],'add',plan['revision'])
    subscriptions.apply(state,'lee',root,c['key'],'add',plan['revision'])
    live.store_key('AIza'+'x'*35,state)
    with pytest.raises(live.LiveError,match='cap'):
        live.refresh(state,transport=lambda *a:pytest.fail('No API request allowed'))
    assert live.status(state)['used']==99

def test_web_preview_required_and_profile_search(setup,tmp_path):
    state,root,c=setup
    client=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765')
    client.get('/?token=test')
    headers={'origin':'http://127.0.0.1:8765'}
    fields=dict(csrf='test',profile='lee',key=c['key'],action='add')
    with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        page=client.get('/subscriptions?profile=lee&show=untracked')
        assert page.status_code==200 and c['name'] in page.text and '/theme.css' in page.text
        assert client.post('/subscriptions/apply',data=fields,headers=headers).status_code==400
        assert client.post('/subscriptions/preview',data={**fields,'csrf':'bad'},headers=headers).status_code==400
        assert client.post('/subscriptions/preview',data=fields).status_code==403
        page=client.post('/subscriptions/preview',data=fields,headers=headers)
        assert page.status_code==200 and 'next refresh units' in page.text
        for key in ('revision','signature'):
            fields[key]=re.search('name="'+key+'" value="([^"]+)"',page.text)[1]
        response=client.post('/subscriptions/apply',data=fields,headers=headers)
        assert response.status_code==200 and 'Tracking saved locally' in response.text
        assert live.status(state)['used']==0
        assert client.get('/subscriptions?profile=demo').status_code==400
        assert client.get('/subscriptions?query=zzzzzzzzzz').status_code==200

def test_test_channel_can_be_readded_and_alias_does_not_duplicate(setup):
    state,root,c=setup
    plan=subscriptions.preview(state,'lee',root,'MentourPilot','remove')
    subscriptions.apply(state,'lee',root,'MentourPilot','remove',plan['revision'])
    plan=subscriptions.preview(state,'lee',root,'MentourPilot','add')
    subscriptions.apply(state,'lee',root,'MentourPilot','add',plan['revision'])
    import sqlite3
    with sqlite3.connect(root/'lee.sqlite3') as db:
        db.execute('INSERT INTO creators VALUES(?,?,1)',('UCwpHKudUkP5tNgmMdexB3ow','Mentour'))
    rows,_=subscriptions.catalogue(state,'lee',root)
    matches=[r for r in rows if r['key'] in ('MentourPilot','UCwpHKudUkP5tNgmMdexB3ow')]
    assert len(matches)==1 and matches[0]['tracked'] and matches[0]['imported']
