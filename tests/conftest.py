import pytest
from signaltube import live

@pytest.fixture(autouse=True)
def isolated_tracking_list(monkeypatch):
    # Regression fixtures use three synthetic channels, not the user's private list.
    monkeypatch.setattr(live,'CHANNELS',list(live.DEFAULT_CHANNELS))
