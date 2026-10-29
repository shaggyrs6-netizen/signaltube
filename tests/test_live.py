import concurrent.futures
import socket
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from signaltube import live,theme
from signaltube.webapp import create_app

KEY='AIza'+'x'*35
NOW=1793217600.0
@pytest.fixture
def state(tmp_path):
    path=tmp_path/'live';live.store_key(KEY,path);return path

class Fake:
    def __init__(self):self.calls=[];self.title='An upload';self.extra=False;self.fail=None
    def __call__(self,endpoint,params,key):
        self.calls.append((endpoint,params));assert key==KEY
        if self.fail:raise self.fail
        if endpoint=='channels':
            i=[c[0] for c in live.CHANNELS].index(params['forHandle'][1:])
            return {'items':[{'id':'UC'+str(i)*22,'contentDetails':{'relatedPlaylists':{'uploads':'UU'+str(i)*22}},'snippet':{'title':'Channel '+str(i)}}]}
        i=int(params['playlistId'][2])
        entries=[{'snippet':{'title':self.title},'contentDetails':{'videoId':f'PUBLIC{i:05}', 'videoPublishedAt':'2026-10-01T12:00:00Z'}}]
        if self.extra:entries.append({'snippet':{'title':'New upload'},'contentDetails':{'videoId':f'NEWVID{i:05}','videoPublishedAt':'2026-10-28T12:00:00Z'}})
        return {'items':entries}

def test_baseline_dedup_changes_and_cooldown(state):
    f=Fake();live.refresh(state,f,NOW)
    d=live.status(state,NOW);assert d['used']==6 and len(d['videos'])==3
    assert all(v['baseline'] for v in d['videos'])
    with pytest.raises(live.LiveError):live.refresh(state,f,NOW+5)
    assert len(f.calls)==6
    f.title='Updated title';f.extra=True;live.refresh(state,f,NOW+901)
    d=live.status(state,NOW+901)
    assert d['used']==9 and len(d['videos'])==6
    assert sum(not v['baseline'] for v in d['videos'])==3
    assert d['videos'][-1]['title']=='Updated title'
    live.refresh(state,f,NOW+1802);assert len(live.status(state,NOW+1802)['videos'])==6

def test_quota_persists_and_no_overspend(state):
    f=Fake();day=live.quota_day(NOW)
    with live.database(state) as db:
        with db:db.execute('INSERT INTO quota VALUES(?,?)',(day,95))
    with pytest.raises(live.LiveError,match='cap'):live.refresh(state,f,NOW)
    assert not f.calls and live.status(state,NOW)['used']==95
    with live.database(state) as db:
        with db:db.execute('UPDATE quota SET used=94')
    live.refresh(state,f,NOW);assert live.status(state,NOW)['used']==100
    with pytest.raises(live.LiveError):live.refresh(state,f,NOW+901)
    assert len(f.calls)==6

def test_midnight_pacific(state):
    before=datetime(2026,10,28,23,59,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()
    with live.database(state) as db:
        with db:db.execute('INSERT INTO quota VALUES(?,?)',(live.quota_day(before),100))
    assert live.status(state,before)['used']==100
    assert live.status(state,before+61)['used']==0
    assert live.reset_at(before)==before+60

def test_crash_reservation_and_concurrency(state):
    def crash(*args):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):live.refresh(state,crash,NOW)
    assert live.status(state,NOW)['used']==6
    def run(_):
        try:return live.refresh(state,Fake(),NOW+901)
        except live.LiveError:return 'blocked'
    with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(run,range(2)))
    assert results.count('blocked')==1
    assert live.status(state,NOW+901)['used']==12

def test_failures_preserve_cache_and_reserve_units(state):
    f=Fake();live.refresh(state,f,NOW);f.fail=live.LiveError('Rate limited',3600)
    with pytest.raises(live.LiveError):live.refresh(state,f,NOW+901)
    d=live.status(state,NOW+901)
    assert len(d['videos'])==3 and d['used']==9
    assert d['control']['next_at']==NOW+4501

def test_expiry_does_not_touch_demo(state,tmp_path):
    from signaltube.webapp import load_demo
    from signaltube.storage import initialise
    from signaltube.ranking import snapshot
    demo=tmp_path/'demo.sqlite3';initialise(demo);load_demo(demo)
    live.refresh(state,Fake(),NOW)
    assert live.status(state,NOW+live.TTL)['videos']==[]
    assert all(c['source'] is None for c in live.status(state,NOW+live.TTL)['channels'])
    assert snapshot(demo)['summary']['events']==7

def test_key_permissions_and_no_overwrite(state):
    assert live.key_path(state).stat().st_mode & 0o777==0o600
    assert live.key_path(state).parent.stat().st_mode & 0o777==0o700
    with pytest.raises(live.LiveError):live.store_key(KEY,state)
    assert live.read_key(state)==KEY
    live.key_path(state).chmod(0o644)
    with pytest.raises(live.LiveError):live.read_key(state)

def test_missing_key_consumes_nothing(tmp_path):
    with pytest.raises(live.LiveError):live.refresh(tmp_path,Fake(),NOW)
    assert live.status(tmp_path,NOW)['used']==0

def test_api_transport_no_secrets_or_redirect(monkeypatch):
    class Opener:
        def open(self,req,timeout):
            assert KEY not in req.full_url
            assert req.get_header('X-goog-api-key')==KEY
            assert req.full_url.startswith('https://www.googleapis.com/youtube/v3/channels?')
            raise urllib.error.HTTPError(req.full_url,403,'secret '+KEY,{},None)
    monkeypatch.setattr(live.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(live.LiveError) as error:live.request_api('channels',{'part':'snippet','forHandle':'@MentourPilot'},KEY)
    assert KEY not in str(error.value)
    with pytest.raises(live.LiveError):live.request_api('search',{},KEY)
    assert live.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example') is None

def test_http_rate_limit_and_timeout(monkeypatch):
    class Opener:
        def open(self,*a,**kw):raise urllib.error.HTTPError('x',429,'',{'Retry-After':'3600'},None)
    monkeypatch.setattr(live.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(live.LiveError) as error:live.request_api('channels',{},KEY)
    assert error.value.retry_after==3600
    class Timeout:
        def open(self,*a,**kw):raise TimeoutError(KEY)
    monkeypatch.setattr(live.urllib.request,'build_opener',lambda *a:Timeout())
    with pytest.raises(live.LiveError) as error:live.request_api('channels',{},KEY)
    assert KEY not in str(error.value)

def test_malformed_batch_not_committed(state):
    def malformed(*args):return {'items':[{}]}
    with pytest.raises(live.LiveError):live.refresh(state,malformed,NOW)
    d=live.status(state,NOW);assert d['used']==6 and not d['videos']

def test_ui_is_offline_and_secret_free(tmp_path,monkeypatch):
    state=tmp_path/'live';live.store_key(KEY,state)
    def blocked(*a,**k):raise AssertionError('Unexpected external request')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    app=create_app(tmp_path/'demo.sqlite3',token='session',live_state=state)
    with TestClient(app,base_url='http://127.0.0.1:8765') as c:
        c.get('/?token=session')
        for url in ['/live','/privacy','/theme.css','/static/theme.js']:
            r=c.get(url);assert r.status_code==200;assert KEY not in r.text
        assert c.post('/live/refresh',data={'csrf':'bad'},headers={'Origin':'http://127.0.0.1:8765'}).status_code==400
        assert c.post('/live/refresh',data={'csrf':'session'},headers={'Origin':'https://evil.example'}).status_code==403

@pytest.mark.parametrize('bg,fg,accent',[('#ffffff','#eeeeee','#ffffaa'),('#10131b','#101010','#111111'),('#191f23','#dedbd2','#88b9b0')])
def test_theme_contrast(tmp_path,bg,fg,accent):
    p=tmp_path/'colors.toml';p.write_text(f'background="{bg}"\nforeground="{fg}"\naccent="{accent}"')
    d=theme.palette(p)
    assert theme.contrast(d['text'],d['bg'])>=4.5
    assert theme.contrast(d['muted'],d['bg'])>=4.5
    assert theme.contrast(d['accent'],d['bg'])>=4.5
    assert theme.contrast(d['line'],d['bg'])>=3

def test_theme_live_change_and_fallback(tmp_path):
    p=tmp_path/'colors.toml';assert theme.palette(p)['source']=='Fallback palette'
    p.write_text('background="#ffffff"\nforeground="#111111"\naccent="#333333"')
    a=theme.css(p);assert 'color-scheme:light' in a
    p.write_text('background="#111111"\nforeground="#ffffff"\naccent="#bbbbbb"')
    assert 'color-scheme:dark' in theme.css(p) and theme.css(p)!=a
    p.write_text('background="</style><script>bad</script>"')
    assert theme.palette(p)['source']=='Fallback palette'

def test_day_rollover_during_batch_reserves_next_day(state,monkeypatch):
    before=datetime(2026,10,28,23,59,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()
    clock=[before]
    monkeypatch.setattr(live.time,'time',lambda:clock[0])
    fake=Fake()
    def crossing(*args):
        result=fake(*args)
        clock[0]=before+61
        return result
    live.refresh(state,crossing)
    with live.database(state) as db:
        counts=dict(db.execute('SELECT day,used FROM quota'))
    assert counts[live.quota_day(before)]==6
    assert counts[live.quota_day(before+61)]==5


def test_day_rollover_cannot_exceed_next_day_budget(state,monkeypatch):
    before=datetime(2026,10,28,23,59,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()
    with live.database(state) as db:
        with db:db.execute('INSERT INTO quota VALUES(?,?)',(live.quota_day(before+61),99))
    clock=[before];monkeypatch.setattr(live.time,'time',lambda:clock[0]);fake=Fake()
    def crossing(*args):
        result=fake(*args);clock[0]=before+61;return result
    with pytest.raises(live.LiveError):live.refresh(state,crossing)
    assert len(fake.calls)==1
    assert live.status(state,before+61)['used']==99

def test_retry_after_full_day_is_not_shortened(state):
    f=Fake();f.fail=live.LiveError('Rate limit',86400)
    with pytest.raises(live.LiveError):live.refresh(state,f,NOW)
    assert live.status(state,NOW)['control']['next_at']==NOW+86400


def test_auth_or_quota_error_pauses_until_reset(state):
    f=Fake();f.fail=live.LiveError('Request rejected',reset_day=True)
    with pytest.raises(live.LiveError):live.refresh(state,f,NOW)
    assert live.status(state,NOW)['control']['next_at']==live.reset_at(NOW)
