"""Opt-in images from API-provided URLs. No cookies, keys, redirects or arbitrary proxy."""
import hashlib
import time
import urllib.parse
import urllib.request
from . import live, library

HOSTS = {'i.ytimg.com', 'yt3.ggpht.com', 'yt3.googleusercontent.com'}
MAX_BYTES = 512 * 1024
MODES = ('local', 'avatars', 'thumbnails')


def valid_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        return False
    try:
        u = urllib.parse.urlsplit(url)
        return (u.scheme == 'https' and u.hostname in HOSTS and not u.username
                and not u.password and u.port in (None, 443) and not u.fragment)
    except ValueError:
        return False


def remember(db, kind, resource, snippet, now):
    thumbnails = snippet.get('thumbnails', {})
    url = ''
    if isinstance(thumbnails, dict):
        for size in (('default', 'medium') if kind == 'avatar' else ('medium', 'default')):
            candidate = thumbnails.get(size, {})
            if isinstance(candidate, dict) and valid_url(candidate.get('url')):
                url = candidate['url']; break
    # Missing or changed URLs must not leave an older image indefinitely.
    db.execute('DELETE FROM media WHERE kind=? AND resource=?', (kind, resource))
    if url:
        db.execute('INSERT INTO media VALUES(?,?,?,?)', (kind, resource, url, now))


def mode(state):
    with library.personal(state) as db:
        row = db.execute("SELECT value FROM library_preferences WHERE key='images'").fetchone()
    return row['value'] if row and row['value'] in MODES else 'local'


def save_mode(state, value):
    if value not in MODES:
        raise ValueError('Choose local artwork, channel avatars or video thumbnails.')
    with library.personal(state) as db:
        db.execute("INSERT INTO library_preferences VALUES('images',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (value,))


def download(url):
    if not valid_url(url):
        raise ValueError('Image source is not allowed.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), live.NoRedirect())
    req = urllib.request.Request(url, headers={'User-Agent': 'SignalTube', 'Accept': 'image/jpeg,image/png,image/webp'})
    with opener.open(req, timeout=8) as response:
        body = response.read(MAX_BYTES + 1)
        mime = response.headers.get_content_type()
    signatures = {'image/jpeg': body.startswith(b'\xff\xd8\xff'), 'image/png': body.startswith(b'\x89PNG\r\n\x1a\n'),
                  'image/webp': body.startswith(b'RIFF') and body[8:12] == b'WEBP'}
    if len(body) > MAX_BYTES or not signatures.get(mime):
        raise ValueError('Unsupported or oversized image.')
    return body, mime


def get(state, kind, resource, transport=None, now=None):
    now = time.time() if now is None else now
    selected = mode(state)
    if kind not in ('avatar', 'thumbnail') or selected == 'local' or (kind == 'thumbnail' and selected != 'thumbnails'):
        return None
    channels = {k for k, _, _ in live.current_channels(state)}
    with live.database(state) as db:
        live.prune(db, now)
        if kind == 'avatar':
            allowed = resource in channels and db.execute('SELECT 1 FROM sources WHERE handle=?', (resource,)).fetchone()
        else:
            row = db.execute('SELECT handle FROM uploads WHERE id=?', (resource,)).fetchone()
            allowed = row and row['handle'] in channels
        if not allowed: return None
        media = db.execute('SELECT * FROM media WHERE kind=? AND resource=?', (kind, resource)).fetchone()
        if not media: return None
        digest = hashlib.sha256(media['url'].encode()).hexdigest()
        cached = db.execute('SELECT body,mime FROM image_cache WHERE digest=? AND expires>?', (digest, now)).fetchone()
        if cached: return bytes(cached['body']), cached['mime']
        body, mime = (transport or download)(media['url'])
        if len(body) > MAX_BYTES: raise ValueError('Oversized image.')
        with db:
            db.execute('INSERT OR REPLACE INTO image_cache VALUES(?,?,?,?)', (digest, body, mime, min(now + 86400, media['fetched'] + live.TTL)))
            # At most 64 images / 32 MiB of payload; browser receives no remote URL.
            db.execute('DELETE FROM image_cache WHERE digest NOT IN (SELECT digest FROM image_cache ORDER BY expires DESC,digest LIMIT 64)')
        return body, mime
