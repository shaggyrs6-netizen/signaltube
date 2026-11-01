import json
import time
import pytest
from signaltube import live
from test_live import Fake,KEY,NOW

def expanded():
    return list(live.DEFAULT_CHANNELS)+[('UC'+str(i)*22,'Synthetic channel '+str(i),'Other') for i in range(10)]

class ExpandedFake(Fake):
    def __call__(self,endpoint,params,key):
        if endpoint=='channels' and 'id' in params:
            self.calls.append((endpoint,params))
            cid=params['id']
            return {'items':[{'id':cid,'contentDetails':{'relatedPlaylists':{'uploads':'UU'+cid[2:]}},'snippet':{'title':'Test creator'}}]}
        if endpoint=='playlistItems':
            self.calls.append((endpoint,params))
            return {'items':[]}
        return super().__call__(endpoint,params,key)

def test_13_channels_reservation_and_normal_refresh(tmp_path,monkeypatch):
    live.store_key(KEY,tmp_path)
    f=ExpandedFake();live.refresh(tmp_path,f,NOW) # existing three resolved
    monkeypatch.setattr(live,'CHANNELS',expanded())
    assert live.status(tmp_path,NOW)['next_budget']==23
    live.refresh(tmp_path,f,NOW+901)
    assert live.status(tmp_path,NOW+901)['used']==29
    assert len(f.calls)==29
    assert live.status(tmp_path,NOW+901)['next_budget']==13
    live.refresh(tmp_path,f,NOW+1802)
    assert live.status(tmp_path,NOW+1802)['used']==42
    assert len(f.calls)==42
    assert sum('id' in p for e,p in f.calls if e=='channels')==10

def test_expanded_cap_refuses_whole_batch(tmp_path,monkeypatch):
    live.store_key(KEY,tmp_path);monkeypatch.setattr(live,'CHANNELS',expanded())
    with live.database(tmp_path) as db:
        with db:db.execute('INSERT INTO quota VALUES(?,75)',(live.quota_day(NOW),))
    f=ExpandedFake()
    with pytest.raises(live.LiveError,match='cap'):live.refresh(tmp_path,f,NOW)
    assert not f.calls and live.status(tmp_path,NOW)['used']==75
    with live.database(tmp_path) as db:
        with db:db.execute('UPDATE quota SET used=74')
    live.refresh(tmp_path,f,NOW)
    assert len(f.calls)==26 and live.status(tmp_path,NOW)['used']==100

def test_configuration_validation_and_urls(tmp_path):
    p=tmp_path/'channels.json'
    assert live.load_channels(p)==live.DEFAULT_CHANNELS
    rows=[dict(key=k,name=n,category=c) for k,n,c in expanded()]
    p.write_text(json.dumps(rows));assert len(live.load_channels(p))==13
    assert '/channel/UC' in live.channel_url(rows[-1]['key'])
    assert '/@MentourPilot' in live.channel_url('MentourPilot')
    p.write_text(json.dumps(rows+[rows[0]]))
    with pytest.raises(ValueError):live.load_channels(p)
    p.write_text('[]')
    assert live.load_channels(p)==[]  # Users may remove all example channels.
