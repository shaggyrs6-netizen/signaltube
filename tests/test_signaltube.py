import json
import socket
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from signaltube.storage import initialise,connect,CATEGORIES
from signaltube.importers import import_file, utc_time
from signaltube.ranking import snapshot
from signaltube.webapp import create_app,load_demo,ROOT

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'test.sqlite3';initialise(path);return path

@pytest.fixture
def client(db):
    app=create_app(db,token='test-secret',live_state=db.parent/'live')
    with TestClient(app,base_url='http://127.0.0.1:8765') as c:
        c.get('/?token=test-secret')
        yield c

def post(c,path,**fields):
    return c.post(path,data={'csrf':'test-secret',**fields},headers={'Origin':'http://127.0.0.1:8765'})

def test_demo_counts_and_reimport(db):
    reports=load_demo(db)
    assert reports[1]['added']==7 and reports[1]['duplicates']==1 and reports[1]['invalid']==1
    data=snapshot(db)
    assert data['summary']['events']==7 and data['summary']['unresolved']==1
    assert [(c['name'],c['events']) for c in data['channels']]==[('Hangar Notebook',4),('The Quiet Terminal',2),('Orbital Workshop',0)]
    load_demo(db)
    assert snapshot(db)['summary']['events']==7
    report=import_file(ROOT/'tests/fixtures/history-overlap.json',db,'history')
    assert report['added']==1 and report['duplicates']==1
    assert snapshot(db)['channels'][0]['events']==5

def test_atomic_interruption(db):
    load_demo(db)
    with pytest.raises(RuntimeError):
        import_file(ROOT/'tests/fixtures/history-overlap.json',db,'history',fail_after=2)
    assert snapshot(db)['summary']['events']==7
    assert len(snapshot(db)['imports'])==2
    import_file(ROOT/'tests/fixtures/history-overlap.json',db,'history')
    assert snapshot(db)['summary']['events']==8

def test_annotations_categories_and_filters_persist(db,client):
    load_demo(db)
    assert post(client,'/category',channel='UC'+'A'*22,category=CATEGORIES[0]).status_code==200
    assert post(client,'/annotation',video='DEMO_A00001',state='saved').status_code==200
    post(client,'/filters',category=CATEGORIES[0],start='2026-10-01',end='2026-10-08',state='saved')
    load_demo(db)
    with TestClient(create_app(db,token='new',live_state=db.parent/'live'),base_url='http://127.0.0.1:8765') as other:
        other.get('/?token=new')
        html=other.get('/').text
    assert 'Why wings bend' in html and 'Linux without the clutter' not in html
    assert '3 events in this period' in html
    assert snapshot(db,category=CATEGORIES[0],state='saved')['total']==1

def test_invalid_formats_and_utc(db,tmp_path):
    p=tmp_path/'bad.json';p.write_text('{bad')
    with pytest.raises(ValueError):import_file(p,db,'history')
    assert snapshot(db)['summary']['events']==0
    assert utc_time('2026-10-01T10:00:00-05:00')==utc_time('2026-10-01T15:00:00Z')
    with pytest.raises(ValueError):utc_time('2026-10-01T15:00:00')

def test_security(client,db):
    load_demo(db)
    assert client.get('/',headers={'Host':'evil.example'}).status_code==400
    assert client.post('/demo',data={'csrf':'test-secret'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/demo',data={'csrf':'wrong'},headers={'Origin':'http://127.0.0.1:8765'}).status_code==400
    assert post(client,'/annotation',video='DEMO_A00001',state='invented').status_code==400
    assert post(client,'/filters',start='2026-10-10',end='2026-10-01').status_code==400
    assert client.get('/static/../../storage.py').status_code==404
    client.cookies.clear()
    assert client.get('/').status_code==401

def test_html_escape_and_no_remote_assets(client,db):
    load_demo(db)
    with connect(db) as conn:conn.execute('UPDATE videos SET title=? WHERE id=?',('<script>alert(1)</script>','DEMO_A00001'))
    response=client.get('/')
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text
    assert '<script>' not in response.text
    assert 'https://' not in response.text
    assert "connect-src 'none'" in response.headers['content-security-policy']
    assert response.headers['referrer-policy']=='same-origin'

def test_offline_import_and_dashboard(db,client,monkeypatch):
    def blocked(*args,**kwargs):raise AssertionError('Outbound network attempted')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    monkeypatch.setattr(socket,'create_connection',blocked)
    load_demo(db)
    assert client.get('/').status_code==200
    assert post(client,'/filters',category='',start='',end='',state='').status_code==200
    assert client.get('/static/app.css').status_code==200

def test_empty_and_zero_matches(client,db):
    assert 'Your library is empty' in client.get('/').text
    load_demo(db)
    post(client,'/filters',start='2030-01-01')
    assert 'No matches for these filters' in client.get('/').text

def test_different_profiles_keep_events(db):
    load_demo(db)
    import_file(ROOT/'tests/fixtures/watch-history.json',db,'history',profile='second-synthetic-profile')
    assert snapshot(db)['summary']['events']==14

def test_history_before_subscriptions_reconciles(db):
    import_file(ROOT/'tests/fixtures/watch-history.json',db,'history')
    assert snapshot(db)['summary']['unresolved']==7
    import_file(ROOT/'tests/fixtures/subscriptions.csv',db,'subscriptions')
    assert snapshot(db)['summary']['unresolved']==1

def test_same_day_boundary(db):
    load_demo(db)
    assert snapshot(db,start='2026-10-01',end='2026-10-01')['channels'][0]['events']==1

def test_uncategorised_includes_unresolved(db):
    load_demo(db)
    assert snapshot(db,category='Other / uncategorised')['total']==4

def test_pagination_and_invalid_rows(db,tmp_path):
    records=[{'title':'Watched synthetic '+str(i),'titleUrl':f'https://www.youtube.com/watch?v=DEMO_{i:06}',
              'time':'2026-10-01T00:00:00Z'} for i in range(15)]
    records += [{'title':'Watched unsafe','titleUrl':'https://evil.example/watch?v=DEMO_000001','time':'2026-10-01T00:00:00Z'}]
    p=tmp_path/'many.json';p.write_text(json.dumps(records))
    report=import_file(p,db,'history')
    assert report['added']==15 and report['invalid']==1
    assert len(snapshot(db)['videos'])==12
    assert len(snapshot(db,page=2)['videos'])==3
    assert snapshot(db,page=999)['page']==2
