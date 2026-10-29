"""Local database; source events and personal annotations remain separate."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

CATEGORIES = ['Aviation and aerospace', 'Gaming', 'Law enforcement', 'Boating and maritime',
              'AI and machine learning', 'Linux and computing', 'Technology and hardware',
              'Science and engineering', 'Other / uncategorised']

@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()

def initialise(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS channels (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
          tracked INTEGER NOT NULL DEFAULT 1,
          category TEXT NOT NULL DEFAULT 'Other / uncategorised', pinned INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS videos (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, channel_id TEXT,
          synthetic INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events (
          profile TEXT NOT NULL, video_id TEXT NOT NULL REFERENCES videos(id),
          time TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'watch',
          PRIMARY KEY(profile, video_id, time, kind));
        CREATE TABLE IF NOT EXISTS annotations (
          video_id TEXT PRIMARY KEY REFERENCES videos(id),
          state TEXT NOT NULL CHECK(state IN ('unreviewed','reviewed','saved','dismissed','marked watched')));
        CREATE TABLE IF NOT EXISTS imports (
          id INTEGER PRIMARY KEY, kind TEXT NOT NULL, imported_at TEXT NOT NULL,
          report TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        PRAGMA user_version=1;
        ''')
    path.chmod(0o600)
