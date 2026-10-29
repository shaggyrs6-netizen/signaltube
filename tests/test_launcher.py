import os
import socket
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from signaltube import launcher,live
from signaltube.webapp import create_app


def test_owner_only_persistent_session(tmp_path):
    token=launcher.session_token(tmp_path)
    assert launcher.session_token(tmp_path)==token
    path=tmp_path/'session.token'
    assert path.stat().st_mode & 0o777==0o600
    path.chmod(0o644)
    with pytest.raises(ValueError,match='owner-only'):launcher.session_token(tmp_path)


def test_locked_help_unlock_and_restart(tmp_path):
    token=launcher.session_token(tmp_path)
    def app():return create_app(tmp_path/'demo.sqlite3',token=launcher.session_token(tmp_path),live_state=tmp_path/'live')
    with TestClient(app(),base_url='http://127.0.0.1:8765') as c:
        assert c.get('/local-status').status_code==401
        assert './run.sh' in c.get('/creators').text
        r=c.get('/?token='+token)
        assert str(r.url).endswith('/watch')
        cookie=c.cookies.get('signaltube_session')
        assert c.get('/local-status').json()['app']=='signaltube'
    with TestClient(app(),base_url='http://127.0.0.1:8765') as c:
        c.cookies.set('signaltube_session',cookie)
        assert c.get('/creators').status_code==200


def test_reuse_does_not_spawn_refresh_or_open_when_suppressed(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(live,'STATE',tmp_path)
    monkeypatch.setattr(launcher,'session_token',lambda:'test')
    monkeypatch.setattr(launcher,'running',lambda *a:dict(app='signaltube',pid=os.getpid()))
    with patch.object(launcher.subprocess,'Popen',side_effect=AssertionError('must reuse')),patch.object(live,'refresh',side_effect=AssertionError('no refresh')),patch.object(launcher.webbrowser,'open',side_effect=AssertionError('no browser')):
        launcher.manage('launch',tmp_path/'demo',open_browser=False)
    assert 'SignalTube is ready' in capsys.readouterr().out


def test_occupied_port_not_killed_or_spawned(tmp_path,monkeypatch):
    monkeypatch.setattr(live,'STATE',tmp_path)
    monkeypatch.setattr(launcher,'session_token',lambda:'test')
    monkeypatch.setattr(launcher,'running',lambda *a:None)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));sock.listen()
        with patch.object(launcher.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with pytest.raises(ValueError,match='occupied'):launcher.manage('launch',tmp_path/'demo',sock.getsockname()[1],False)
