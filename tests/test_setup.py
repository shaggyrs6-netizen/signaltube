from fastapi.testclient import TestClient
from signaltube import live
from signaltube.webapp import create_app


def test_setup_is_local_guarded_and_linked(tmp_path,monkeypatch):
    def no_network(*a,**kw):
        raise AssertionError('Setup must not contact YouTube')
    monkeypatch.setattr(live,'request_api',no_network)
    monkeypatch.setattr(live,'refresh',no_network)
    with TestClient(create_app(tmp_path/'demo.db',token='test',live_state=tmp_path/'live'),base_url='http://127.0.0.1:8765') as c:
        assert c.get('/setup').status_code==401
        c.get('/?token=test')
        page=c.get('/setup')
        assert page.status_code==200
        assert '100-unit daily cap' in page.text
        assert 'does not buy more quota' in page.text
        assert 'Set YouTube API key' in page.text
        assert '/setup' in c.get('/watch').text
        assert not (tmp_path/'live/secrets/youtube.key').exists()
