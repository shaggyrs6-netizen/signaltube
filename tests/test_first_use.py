import json
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import live,library,shortlist,subscriptions,images,dashboard
from signaltube.webapp import create_app

CID='UC'+'9'*22
VID='VIDEO123456'
KEY='AIza'+'x'*35

def response(endpoint,params,key):
    assert endpoint=='channels' and key==KEY
    return {'items':[{'id':CID,'snippet':{'title':'Synthetic channel','thumbnails':{'default':{'url':'https://yt3.ggpht.com/example'}}},'contentDetails':{'relatedPlaylists':{'uploads':'UU'+'9'*22}}}]}

def client(tmp_path):
    state=tmp_path/'state';root=tmp_path/'imports'
    c=TestClient(create_app(tmp_path/'demo.db',token='test',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765')
    c.get('/?token=test')
    return c,state,root

def post(c,path,**data):
    return c.post(path,data={'csrf':'test',**data},headers={'origin':'http://127.0.0.1:8765'})

def test_empty_onboarding_and_neutral_profile_no_network(tmp_path):
    with patch('socket.socket.connect',side_effect=AssertionError('No network')):
        c,state,root=client(tmp_path)
        page=c.get('/watch').text
        assert 'Try the demo' in page and 'Set up my channels' in page
        assert 'Collect uploads before building' in page
        assert 'name="use_history"' not in page and 'History profile' not in page
        assert 'value="lee"' not in page and 'Manage library' in page
        assert 'src="/images/' not in page
        assert shortlist.options_load(state,[],root)[0]['profile']=='local'
        assert live.status(state)['used']==0
        assert c.get('/subscriptions').status_code==200

@pytest.mark.parametrize('value',['https://evil.test/@name','https://www.youtube.com@evil.test/@name','https://www.youtube.com/watch?v=abc','https://youtube.com/@name?x=1','https://youtube.com/c/name','http://youtube.com/@name','file:///etc/passwd','@a/b','https://youtube.com:444/@name'])
def test_channel_input_rejects_arbitrary_urls(value):
    with pytest.raises(ValueError):subscriptions.parse_channel(value)

def test_lookup_confirm_budget_no_collection_and_duplicate(tmp_path):
    state=tmp_path/'state';root=tmp_path/'imports';live.store_key(KEY,state)
    now=time.time()
    with patch.object(live,'request_api',side_effect=response) as transport:
        key=subscriptions.resolve(state,'https://www.youtube.com/@Synthetic',now=now)
        assert key==CID and transport.call_count==1
        assert live.status(state)['used']==1
        assert len(live.current_channels(state))==3 and not live.status(state)['videos']
        plan=subscriptions.preview(state,'local',root,key,'add')
        assert plan['normal']==4 and plan['budget']==7 # Three uncached examples + resolved new channel.
        subscriptions.apply(state,'local',root,key,'add',plan['revision'])
        assert len(live.current_channels(state))==4 and transport.call_count==1
        assert subscriptions.resolve(state,'@Synthetic',now=now)==key
        with pytest.raises(ValueError,match='Tracking changed'):
            subscriptions.preview(state,'local',root,key,'add')
    with live.database(state) as db:
        assert db.execute("SELECT count(*) FROM media WHERE kind='avatar'").fetchone()[0]==1


def test_lookup_cap_failure_and_shared_lock(tmp_path):
    import fcntl
    state=tmp_path/'state';live.store_key(KEY,state);now=time.time()
    with live.database(state) as db:
        with db: db.execute('INSERT INTO quota VALUES(?,99)',(live.quota_day(now),))
    def failure(*args): raise live.LiveError('Synthetic failure')
    with pytest.raises(live.LiveError):subscriptions.resolve(state,'@Synthetic',transport=failure,now=now)
    assert live.status(state,now)['used']==100
    with patch.object(live,'request_api',side_effect=AssertionError('Must not send')):
        with pytest.raises(live.LiveError):subscriptions.resolve(state,'@Synthetic',now=now+901)
        with (state/'refresh.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with pytest.raises(live.LiveError,match='running'):subscriptions.resolve(state,'@Synthetic',now=now+901)


def test_existing_saved_options_preserved(tmp_path):
    c,state,root=client(tmp_path)
    shortlist.options_save(state,root,'lee','',False,True,[])
    assert shortlist.options_load(state,[],root)[0]['profile']=='lee'
    assert 'value="lee"' not in c.get('/watch').text # no pointless history controls on empty library


def seed(state,now):
    with live.database(state) as db:
        with db:
            db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(VID,'MentourPilot','Synthetic video','2026-10-01T00:00:00+00:00',now,now,1))
            db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?)',('MentourPilot',CID,'UU'+'9'*22,'Creator',now,now,now))
            images.remember(db,'thumbnail',VID,{'thumbnails':{'medium':{'url':'https://i.ytimg.com/vi/VIDEO123456/mqdefault.jpg'}}},now)
            images.remember(db,'avatar','MentourPilot',{'thumbnails':{'default':{'url':'https://yt3.ggpht.com/example'}}},now)


def test_optional_images_cache_expiry_and_local_mode(tmp_path):
    c,state,root=client(tmp_path);now=time.time();seed(state,now)
    fake=lambda url:(b'\xff\xd8\xffsynthetic','image/jpeg')
    with patch.object(images,'download',side_effect=fake) as download:
        assert c.get('/images/thumbnail/'+VID).status_code==404 and download.call_count==0
        post(c,'/watch/images',images='avatars',view='catchup')
        assert c.get('/images/thumbnail/'+VID).status_code==404
        assert c.get('/images/avatar/MentourPilot').status_code==200
        post(c,'/watch/images',images='thumbnails',view='catchup')
        for _ in range(2):assert c.get('/images/thumbnail/'+VID).status_code==200
        assert download.call_count==2
        page=c.get('/watch?view=catchup').text
        assert '/images/thumbnail/'+VID in page and '/images/avatar/MentourPilot' in page
        assert "img-src 'self'" in c.get('/watch').headers['content-security-policy']
        assert images.get(state,'thumbnail',VID,now=now+live.TTL+1) is None
        post(c,'/watch/images',images='local',view='catchup')
        assert c.get('/images/avatar/MentourPilot').status_code==404
        assert download.call_count==2 and live.status(state)['used']==0

@pytest.mark.parametrize('url',['http://i.ytimg.com/a','https://i.ytimg.com.evil.test/a','https://user:password@i.ytimg.com/a','https://127.0.0.1/a','https://i.ytimg.com:444/a','https://i.ytimg.com/a\nX:foo','file:///etc/passwd'])
def test_image_allowlist(url):
    assert not images.valid_url(url)


def test_expired_saved_entry_visible_removable_and_undoable(tmp_path):
    c,state,root=client(tmp_path);now=time.time();seed(state,now)
    dashboard.video_action(state,VID,'save')
    with live.database(state) as db:
        with db:db.execute('UPDATE uploads SET fetched=0')
    html=c.get('/watch?view=saved').text
    assert 'Unavailable saved item' in html and 'Synthetic video' not in html
    assert 'may not restore older items' in html
    fp=library.fingerprint(VID)
    assert post(c,'/watch/unavailable',fingerprint=fp).status_code==200
    assert dashboard.page(state,root,'saved')['unavailable_saved']==0
    receipt=dashboard.page(state,root)['undo']['token']
    dashboard.undo(state,receipt)
    assert dashboard.page(state,root,'saved')['unavailable_saved']==1


def test_cooldown_disables_refresh_and_images_survive_app_recreation(tmp_path):
    c,state,root=client(tmp_path);seed(state,time.time());live.store_key(KEY,state)
    with live.database(state) as db:
        with db:db.execute('UPDATE control SET next_at=?',(time.time()+480,))
    html=c.get('/watch').text
    assert 'Refresh available in 8 minutes' in html
    assert 'disabled>Refresh from YouTube' in html
    post(c,'/watch/images',images='avatars',view='watch')
    recreated=TestClient(create_app(tmp_path/'demo.db',token='again',live_state=state,takeout_root=root),base_url='http://127.0.0.1:8765')
    recreated.get('/?token=again')
    assert 'Images · channel avatars' in recreated.get('/watch').text


def test_http_lookup_requires_confirmation_csrf_and_zero_channel_support(tmp_path):
    c,state,root=client(tmp_path);live.store_key(KEY,state)
    assert c.post('/subscriptions/resolve',data={'channel':'@Synthetic'}).status_code==403
    with patch.object(live,'request_api',side_effect=response) as api:
        html=post(c,'/subscriptions/resolve',channel='@Synthetic',profile='local').text
        assert 'Track Synthetic channel?' in html and 'Apply tracking change' in html
        assert len(live.current_channels(state))==3 and api.call_count==1
    (state/'tracked-channels.json').write_text('[]')
    assert live.current_channels(state)==[]
    with pytest.raises(live.LiveError,match='Choose a channel'):live.refresh(state)


def test_download_validation_no_credentials_and_bounded_read(monkeypatch):
    from email.message import Message
    class Response:
        def __init__(self,body,mime):
            self.body=body;self.headers=Message();self.headers['Content-Type']=mime
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):
            assert limit==images.MAX_BYTES+1
            return self.body[:limit]
    class Opener:
        body=b'\xff\xd8\xfftest';mime='image/jpeg'
        def open(self,request,timeout):
            assert timeout==8
            assert set(k.lower() for k,_ in request.header_items())=={'user-agent','accept'}
            return Response(self.body,self.mime)
    opener=Opener()
    monkeypatch.setattr(images.urllib.request,'build_opener',lambda *args:opener)
    assert images.download('https://i.ytimg.com/test')[1]=='image/jpeg'
    for body,mime in [(b'<svg/>','image/svg+xml'),(b'<html>bad</html>','image/png'),(b'\xff\xd8\xff'+b'x'*images.MAX_BYTES,'image/jpeg')]:
        opener.body=body;opener.mime=mime
        with pytest.raises(ValueError):images.download('https://i.ytimg.com/test')


def test_resolved_channel_refresh_initial_baseline_and_image_urls(tmp_path):
    state=tmp_path/'state';live.store_key(KEY,state);now=time.time()
    key=subscriptions.resolve(state,'@Synthetic',transport=response,now=now)
    (state/'tracked-channels.json').write_text(json.dumps([dict(key=key,name='Synthetic channel',category='Test')]))
    def uploads(endpoint,params,key):
        assert endpoint=='playlistItems' # Resolved channel details are reused, no extra API cost.
        return {'items':[{'snippet':{'title':'First baseline','thumbnails':{'medium':{'url':'https://i.ytimg.com/test'}}},'contentDetails':{'videoId':VID,'videoPublishedAt':'2026-10-01T00:00:00Z'}}]}
    live.refresh(state,transport=uploads,now=now)
    status=live.status(state,now)
    assert status['used']==2 and status['videos'][0]['baseline']==1
    assert ('thumbnail',VID) in status['media'] and ('avatar',key) in status['media']
    assert status['channels'][0]['source']['baseline']==now


def test_partial_coverage_is_not_reported_as_all_fresh(tmp_path):
    c,state,root=client(tmp_path);now=time.time();seed(state,now)
    assert dashboard.page(state,root)['fresh_channels']==1
    assert '1 of 3 channels updated' in c.get('/watch').text
    assert 'Use remembered options' in c.get('/watch?notice=refresh').text
    with live.database(state) as db:
        with db:db.execute('UPDATE sources SET success=?',(now-90000,))
    assert dashboard.page(state,root)['fresh_channels']==0
