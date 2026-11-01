"""Explicit local tracking changes. No transport or automatic refresh."""
import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from . import live, takeout


# Public identities verified during the original three-channel API baseline.
# Retain alias matching even when expiring API metadata is gone.
TEST_IDENTITIES={'UCxQKHvKbmSzGMvUrVtJYnUA':'LearnLinuxTV',
                 'UCwpHKudUkP5tNgmMdexB3ow':'MentourPilot',
                 'UCbfYPyITQ-7l4upoX8nvctg':'TwoMinutePapers'}

def catalogue(state, profile, root):
    data=takeout.overview(profile,root)
    channels=live.current_channels(state)
    status=live.status(state)
    with live.database(state) as db:
        identities={**TEST_IDENTITIES,**{r['channel_id']:r['handle'] for r in db.execute('SELECT * FROM sources')}}
    tracked={k:(n,c) for k,n,c in channels}
    with live.database(state) as db:
        resolved=[dict(r) for r in db.execute('SELECT handle,title FROM sources')]
    rows={}
    for c in data['creators'] if data else []:
        if not c['subscribed']:continue
        key=identities.get(c['id'],c['id'])
        rows[key]=dict(key=key,name=c['name'],events=c['events'],last=c['last'],tracked=key in tracked,imported=True)
    for c in resolved:
        if c['handle'] not in rows:rows[c['handle']]=dict(key=c['handle'],name=c['title'],events=None,last=None,tracked=c['handle'] in tracked,imported=False)
    for key,name,category in live.DEFAULT_CHANNELS:
        if key not in rows:rows[key]=dict(key=key,name=name,events=None,last=None,tracked=key in tracked,imported=False)
    for key,(name,category) in tracked.items():
        if key not in rows:rows[key]=dict(key=key,name=name,events=None,last=None,tracked=True,imported=False)
    return sorted(rows.values(),key=lambda r:(not r['tracked'],-(r['events'] or 0),r['name'].casefold())),status


def preview(state,profile,root,key,action):
    rows,status=catalogue(state,profile,root)
    row=next((r for r in rows if r['key']==key),None)
    if row is None or action not in ('add','remove'):raise ValueError('Unknown subscription or action.')
    if row['tracked'] != (action=='remove'):raise ValueError('Tracking changed. Reload the subscription manager.')
    channels=live.current_channels(state)
    proposed=[c for c in channels if c[0]!=key]
    if action=='add':proposed.append((key,row['name'],'Other / uncategorised'))
    if not 0<=len(proposed)<=50:raise ValueError('Keep between 0 and 50 tracked channels, within the 100-unit cold-start budget.')
    with live.database(state) as db:
        cached={r['handle'] for r in db.execute('SELECT * FROM sources')}
    budget=live.refresh_budget(cached,proposed)
    plan=dict(profile=profile,key=key,url=live.channel_url(key),action=action,name=row['name'],channels=proposed,before=channels,
              used=status['used'],day=live.quota_day(time.time()),budget=budget,
              normal=len(proposed),cold=2*len(proposed),remaining=live.CAP-status['used'])
    plan['revision']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    return plan


def apply(state,profile,root,key,action,revision):
    state=Path(state)
    fd=os.open(state/'refresh.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('A refresh is running. Preview the change again when it finishes.') from None
        plan=preview(state,profile,root,key,action)
        if plan['revision']!=revision:raise ValueError('Tracking or quota changed. Preview this change again.')
        fd,name=tempfile.mkstemp(prefix='.tracking-',dir=state)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump([dict(key=k,name=n,category=c) for k,n,c in plan['channels']],f)
                f.flush();os.fsync(f.fileno())
            os.replace(name,state/'tracked-channels.json')
        finally:
            if os.path.exists(name):os.unlink(name)
    return plan


def parse_channel(value):
    """Accept identity only; never fetch a pasted URL."""
    import re
    from urllib.parse import urlsplit, unquote
    value = value.strip()
    if len(value) > 300: raise ValueError('Channel address is too long.')
    if value.startswith(('https://', 'http://')):
        url = urlsplit(value)
        if url.scheme != 'https' or url.hostname not in ('youtube.com', 'www.youtube.com', 'm.youtube.com') or url.username or url.password or url.port not in (None, 443) or url.query or url.fragment:
            raise ValueError('Use a YouTube channel URL or @handle, without extra parameters.')
        path = unquote(url.path).strip('/')
        value = path[8:] if path.startswith('channel/') else path
    if live.ID.fullmatch(value): return {'id': value}
    if value.startswith('@') and re.fullmatch(r'[\w.\-·]{3,100}', value[1:], re.UNICODE):
        return {'forHandle': value}
    raise ValueError('Paste an @handle or https://www.youtube.com/channel/UC… address. Video links and older /c/ links are not supported.')


def resolve(state, value, transport=None, now=None):
    """One explicitly requested API lookup, shared lock and conservative daily ledger."""
    from . import images
    identity = parse_channel(value)
    state = Path(state); state.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = time.time() if now is None else now
    fd = os.open(state/'refresh.lock', os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise live.LiveError('Another YouTube request is running. Try again when it finishes.') from None
        key = live.read_key(state)
        with live.database(state) as db:
            live.prune(db, now)
            db.execute('BEGIN IMMEDIATE')
            control = db.execute('SELECT * FROM control').fetchone()
            if now < control['next_at']:
                db.rollback(); raise live.LiveError('YouTube requests are paused. Wait for the refresh time shown on Watch next.')
            day = live.quota_day(now)
            used = db.execute('SELECT used FROM quota WHERE day=?', (day,)).fetchone()
            if used and used['used'] >= live.CAP:
                db.rollback(); raise live.LiveError('Daily 100-unit cap reached. No request sent.')
            db.execute('INSERT INTO quota VALUES(?,1) ON CONFLICT(day) DO UPDATE SET used=used+1', (day,))
            db.commit()  # Failed and interrupted lookups also keep their reservation.
            try:
                raw = (transport or live.request_api)('channels', {'part':'snippet,contentDetails', **identity}, key)
                if len(raw['items']) != 1: raise ValueError('No single public channel matched. Check the address.')
                item = raw['items'][0]; cid = item['id']; title = item['snippet']['title']
                playlist = item['contentDetails']['relatedPlaylists']['uploads']
                import re
                if not live.ID.fullmatch(cid) or not isinstance(title,str) or not title.strip() or not re.fullmatch(r'[A-Za-z0-9_-]{10,100}',playlist):
                    raise ValueError('Invalid channel details returned.')
                if identity.get('id',cid) != cid: raise ValueError('Channel identity did not match.')
                # Preserve an existing alias so the same creator cannot be tracked twice.
                old = db.execute('SELECT handle FROM sources WHERE channel_id=?', (cid,)).fetchone()
                handle = old['handle'] if old else TEST_IDENTITIES.get(cid,cid)
                with db:
                    db.execute('''INSERT INTO sources VALUES(?,?,?,?,?,NULL,NULL) ON CONFLICT(handle) DO UPDATE SET
                        channel_id=excluded.channel_id,playlist=excluded.playlist,title=excluded.title,fetched=excluded.fetched''',
                        (handle,cid,playlist,title[:500],now))
                    images.remember(db,'avatar',handle,item['snippet'],now)
                return handle
            except live.LiveError as exc:
                with db: db.execute('UPDATE control SET next_at=?,message=?', (live.reset_at(now) if exc.reset_day else now+max(900,exc.retry_after),str(exc)))
                raise
            except (KeyError, TypeError, IndexError):
                raise ValueError('Unexpected channel details. No tracking change made.') from None
