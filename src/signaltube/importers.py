"""Explicit file imports only. Never follows links or opens an archive."""
import csv
import io
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
from .storage import connect

MAX_BYTES = 20 * 1024 * 1024
CHANNEL = re.compile(r'UC[A-Za-z0-9_-]{22}\Z')
VIDEO = re.compile(r'[A-Za-z0-9_-]{11}\Z')

def read_file(path):
    with open(path, 'rb') as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('File exceeds the Phase 1A limit of 20 MiB. No records imported.')
    return data.decode('utf-8-sig')

def channel_id(url):
    u = urlsplit(url)
    if u.scheme not in ('http', 'https') or u.netloc not in ('www.youtube.com', 'youtube.com'):
        return None
    value = u.path.removeprefix('/channel/').rstrip('/')
    return value if u.path.startswith('/channel/') and CHANNEL.fullmatch(value) else None

def video_id(url):
    u = urlsplit(url)
    if u.scheme not in ('http', 'https') or u.netloc not in ('www.youtube.com', 'youtube.com') or u.path != '/watch':
        return None
    value = parse_qs(u.query).get('v', [''])[0]
    return value if VIDEO.fullmatch(value) else None

def utc_time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp has no timezone')
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds')

def import_file(path, db_path, kind, profile='synthetic-demo', synthetic=True, fail_after=None):
    if kind not in ('subscriptions', 'history'):
        raise ValueError('Supported formats: subscription CSV and history JSON.')
    if not profile.strip() or len(profile) > 100:
        raise ValueError('A profile label of 1–100 characters is required.')
    text = read_file(path)
    if kind == 'subscriptions':
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or {x.strip().casefold() for x in reader.fieldnames} != {'channel id', 'channel url', 'channel title'}:
            raise ValueError('Expected CSV headers: Channel Id, Channel Url, Channel Title.')
        rows = list(reader)
    else:
        try:
            rows = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError('Invalid JSON. No records imported.') from error
        if not isinstance(rows, list):
            raise ValueError('History must be a JSON list. No records imported.')
    report = dict(total=len(rows), added=0, duplicates=0, updated=0, unresolved=0, invalid=0, issues=[])
    with connect(db_path) as db:
        for number, row in enumerate(rows, 1):
            try:
                if not isinstance(row, dict):
                    raise ValueError('Expected a record object')
                if kind == 'subscriptions':
                    r = {k.strip().casefold(): v for k, v in row.items() if isinstance(k, str)}
                    cid, name = r['channel id'], r['channel title']
                    if not cid or not CHANNEL.fullmatch(cid) or channel_id(r['channel url']) != cid or not name:
                        raise ValueError('Missing or invalid channel ID, URL or title')
                    previous = db.execute('SELECT name FROM channels WHERE id=?', (cid,)).fetchone()
                    report['updated' if previous and previous['name'] != name else 'duplicates' if previous else 'added'] += 1
                    db.execute('INSERT INTO channels(id,name,url) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url',
                               (cid, name[:500], 'https://www.youtube.com/channel/' + cid))
                else:
                    vid = video_id(row.get('titleUrl', ''))
                    if not vid or not isinstance(row.get('title'), str) or not row['title'].startswith('Watched '):
                        raise ValueError('Expected a Watched event with a YouTube video URL')
                    stamp = utc_time(row['time'])
                    subtitles = row.get('subtitles', [])
                    cid = next((channel_id(s.get('url','')) for s in subtitles if isinstance(s,dict) and channel_id(s.get('url',''))), None)
                    if cid is None or not db.execute('SELECT 1 FROM channels WHERE id=?', (cid,)).fetchone():
                        report['unresolved'] += 1
                    db.execute('INSERT INTO videos(id,title,channel_id,synthetic) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,channel_id=coalesce(excluded.channel_id,videos.channel_id)',
                               (vid, row['title'][8:][:1000], cid, int(synthetic)))
                    cursor = db.execute('INSERT OR IGNORE INTO events(profile,video_id,time) VALUES(?,?,?)', (profile,vid,stamp))
                    report['added' if cursor.rowcount else 'duplicates'] += 1
            except (ValueError, TypeError, KeyError, AttributeError):
                report['invalid'] += 1
                if len(report['issues']) < 50:
                    report['issues'].append(f'Row {number}: missing, invalid or unsupported fields.')
            if fail_after == number:
                raise RuntimeError('Simulated interruption')
        db.execute('INSERT INTO imports(kind,imported_at,report) VALUES(?,?,?)',
                   (kind, datetime.now(timezone.utc).isoformat(), json.dumps(report)))
    return report
