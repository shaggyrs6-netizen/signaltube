from unittest.mock import patch
from fastapi.testclient import TestClient
from signaltube.webapp import create_app
from signaltube import live,library,shortlist,takeout


def test_preview_is_authenticated_and_independent_of_user_data(tmp_path):
    c=TestClient(create_app(tmp_path/'demo.sqlite3',token='test',live_state=tmp_path/'state'),base_url='http://127.0.0.1:8765')
    assert c.get('/preview').status_code==401
    c.get('/?token=test')
    with patch.object(live,'status',side_effect=AssertionError('No live data')),patch.object(library,'personal',side_effect=AssertionError('No personal database')),patch.object(takeout,'overview',side_effect=AssertionError('No history')),patch.object(shortlist,'build',side_effect=AssertionError('No ranking')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
        page=c.get('/preview')
        assert page.status_code==200
        assert 'Fictional videos and counts' in page.text
        assert '/theme.css' in page.text
        assert '<form' not in page.text and 'youtube.com' not in page.text
        assert 'retained for 30 days' in page.text
        assert c.get('/static/prototype.js').status_code==200
    assert c.post('/preview',headers={'origin':'http://127.0.0.1:8765'}).status_code==405
