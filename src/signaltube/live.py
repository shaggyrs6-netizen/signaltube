"""Bounded public API client. No account OAuth, proxies, search or automatic polling."""
import fcntl
import json
import os
import re
import secrets
import sqlite3
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
from .paths import STATE
PACIFIC = ZoneInfo('America/Los_Angeles')
CAP = 100
TTL = 30 * 86400
DEFAULT_CHANNELS = [('MentourPilot','Mentour Pilot','Aviation and aerospace'),
            ('LearnLinuxTV','Learn Linux TV','Linux and computing'),
            ('TwoMinutePapers','Two Minute Papers','AI and machine learning')]
ID = re.compile(r'UC[A-Za-z0-9_-]{22}\Z')
VID = re.compile(r'[A-Za-z0-9_-]{11}\Z')

def load_channels(path=STATE/'tracked-channels.json'):
    """Explicit private allowlist, reloaded for each operation. Never reads Takeout automatically."""
    if not path.exists():return list(DEFAULT_CHANNELS)
    with path.open('rb') as f:raw=f.read(65537)
    if len(raw)>65536:raise ValueError('Tracking configuration is too large.')
    rows=json.loads(raw)
    if not isinstance(rows,list) or not 0<=len(rows)<=50:
        raise ValueError('Tracking configuration must contain 0–50 channels.')
    result=[];keys=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid tracking entry.')
        key,name,category=(row.get(k) for k in ('key','name','category'))
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',key) or key in keys:
            raise ValueError('Invalid or duplicate tracking key.')
        if key.startswith('UC') and not ID.fullmatch(key):raise ValueError('Invalid channel ID.')
        if not all(isinstance(v,str) and v.strip() and len(v)<=200 for v in (name,category)):
            raise ValueError('Invalid tracking name or category.')
        keys.add(key);result.append((key,name,category))
    return result

CHANNELS=load_channels()

def current_channels(state=STATE):
    path=Path(state)/'tracked-channels.json'
    return load_channels(path) if path.exists() else list(CHANNELS)

def refresh_budget(cached, channels=None):
    channels=CHANNELS if channels is None else channels
    return len(channels)+sum(key not in cached for key,_,_ in channels)

def channel_url(key):
    return 'https://www.youtube.com/'+('channel/'+key if ID.fullmatch(key) else '@'+key)

class LiveError(Exception):
    def __init__(self, message, retry_after=900, reset_day=False):
        super().__init__(message)
        self.retry_after = retry_after
        self.reset_day = reset_day

@contextmanager
def database(state=STATE):
    state = Path(state)
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=state/'live.sqlite3'
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.close(fd)
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA secure_delete=ON')
    try:
        with db:
            db.executescript('''CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, used INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1), next_at REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT 'Not refreshed');
            INSERT OR IGNORE INTO control(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS sources(handle TEXT PRIMARY KEY, channel_id TEXT NOT NULL, playlist TEXT NOT NULL, title TEXT NOT NULL, fetched REAL NOT NULL, success REAL, baseline REAL);
            CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY,handle TEXT NOT NULL,title TEXT NOT NULL,published TEXT NOT NULL,first_seen REAL NOT NULL,fetched REAL NOT NULL,baseline INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS media(kind TEXT NOT NULL,resource TEXT NOT NULL,url TEXT NOT NULL,fetched REAL NOT NULL,PRIMARY KEY(kind,resource));
            CREATE TABLE IF NOT EXISTS image_cache(digest TEXT PRIMARY KEY,body BLOB NOT NULL,mime TEXT NOT NULL,expires REAL NOT NULL);
            PRAGMA user_version=1;''')
        yield db
    finally:
        db.close()

def prune(db, now):
    with db:
        db.execute('DELETE FROM uploads WHERE fetched<=?',(now-TTL,))
        db.execute('DELETE FROM sources WHERE fetched<=?',(now-TTL,))
        db.execute('DELETE FROM media WHERE fetched<=?',(now-TTL,))
        db.execute('DELETE FROM image_cache WHERE expires<=?',(now,))

def key_path(state=STATE):
    return Path(state)/'secrets'/'youtube.key'

def store_key(key,state=STATE):
    if not re.fullmatch(r'AIza[A-Za-z0-9_-]{30,100}',key):
        raise LiveError('That does not look like a standard Google API key. Nothing saved.')
    path=key_path(state)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    path.parent.chmod(0o700)
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    except FileExistsError:
        raise LiveError('A key already exists. It was not replaced. Request a deliberate key rotation.') from None
    with os.fdopen(fd,'w') as f:
        f.write(key+'\n')
    # No network calls. Existing keys are never silently replaced.

def read_key(state=STATE):
    try:
        fd=os.open(key_path(state),os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as f:
            info=os.fstat(f.fileno())
            if info.st_uid!=os.getuid() or info.st_mode & 0o077 or not stat.S_ISREG(info.st_mode):
                raise LiveError('Key file must be a regular owner-only file (mode 600).')
            key=f.read(256).strip()
        if not re.fullmatch(r'AIza[A-Za-z0-9_-]{30,100}',key):
            raise LiveError('Stored key is invalid. Request a deliberate key rotation.')
        return key
    except OSError:
        raise LiveError('Add your key locally first: run.sh key-add') from None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def request_api(endpoint,params,key):
    allowed={'channels':{'part','forHandle','id'},'playlistItems':{'part','playlistId','maxResults'}}
    if endpoint not in allowed or not set(params)<=allowed[endpoint]:
        raise LiveError('Request blocked: endpoint or parameter not permitted.')
    url='https://www.googleapis.com/youtube/v3/'+endpoint+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'X-Goog-Api-Key':key,'Accept':'application/json','User-Agent':'SignalTube/0.2'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(req,timeout=15) as response:
            body=response.read(1_048_577)
        if len(body)>1_048_576:
            raise LiveError('YouTube response exceeded the local size limit.')
        data=json.loads(body)
        if not isinstance(data,dict) or not isinstance(data.get('items'),list):
            raise LiveError('YouTube returned an unexpected response. Cached data kept.')
        return data
    except urllib.error.HTTPError as exc:
        if exc.code==429:
            retry=900
            raw=exc.headers.get('Retry-After','')
            try: retry=max(retry,int(raw))
            except ValueError:
                try: retry=max(retry,parsedate_to_datetime(raw).timestamp()-time.time())
                except (ValueError,TypeError,OverflowError): pass
            raise LiveError('YouTube rate limit: refresh paused. No automatic retry.',retry) from None
        if exc.code in (400,401,403):
            # Never echo Google's body, request URL or credentials.
            raise LiveError('YouTube rejected the request (key, API restriction or quota). Check Cloud Console. Paused until the next quota day.',reset_day=True) from None
        raise LiveError('YouTube request failed. Cached data kept; no automatic retry.') from None
    except (urllib.error.URLError,TimeoutError,OSError,ValueError):
        raise LiveError('YouTube is unavailable or returned invalid data. Cached data kept.') from None

def quota_day(now):
    return datetime.fromtimestamp(now,PACIFIC).date().isoformat()

def reset_at(now):
    day=datetime.fromtimestamp(now,PACIFIC).date()+timedelta(days=1)
    return datetime.combine(day,datetime.min.time(),PACIFIC).timestamp()

def refresh(state=STATE,transport=request_api,now=None):
    from . import images
    fixed_time = now
    now=time.time() if now is None else now
    state=Path(state); state.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(state/'refresh.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise LiveError('A refresh is already running.') from None
        channels=current_channels(state)
        if not channels: raise LiveError('Choose a channel before refreshing.')
        key=read_key(state)
        with database(state) as db:
            prune(db,now)
            db.execute('BEGIN IMMEDIATE')
            control=db.execute('SELECT * FROM control').fetchone()
            if now<control['next_at']:
                db.rollback();raise LiveError('Refresh paused. See the next refresh time on the dashboard.')
            cached={r['handle']:dict(r) for r in db.execute('SELECT * FROM sources')}
            # Reserve the entire maximum batch up front, never refund uncertain outcomes.
            budget=refresh_budget(cached,channels)
            day=quota_day(now)
            used=db.execute('SELECT used FROM quota WHERE day=?',(day,)).fetchone()
            if (used['used'] if used else 0)+budget>CAP:
                db.rollback();raise LiveError('Daily 100-unit cap reached. No request sent.')
            db.execute('INSERT INTO quota VALUES(?,?) ON CONFLICT(day) DO UPDATE SET used=used+excluded.used',(day,budget))
            db.execute("UPDATE control SET next_at=?,message='Refresh started; reserved units include interrupted requests'",(now+900,))
            db.commit()
            reserved_day=day
            remaining_budget=budget
            def fetch(endpoint, params):
                nonlocal reserved_day, remaining_budget
                call_time=time.time() if fixed_time is None else fixed_time
                call_day=quota_day(call_time)
                # A suspended process may resume on another Pacific quota day.
                # Reserve all remaining calls against that day too, never refund.
                if call_day != reserved_day:
                    db.execute('BEGIN IMMEDIATE')
                    row=db.execute('SELECT used FROM quota WHERE day=?',(call_day,)).fetchone()
                    if (row['used'] if row else 0)+remaining_budget>CAP:
                        db.rollback()
                        raise LiveError('Daily cap reached after quota-day rollover. Refresh stopped.')
                    db.execute('INSERT INTO quota VALUES(?,?) ON CONFLICT(day) DO UPDATE SET used=used+excluded.used',(call_day,remaining_budget))
                    db.commit()
                    reserved_day=call_day
                remaining_budget-=1
                return transport(endpoint,params,key)
            new_count=0
            try:
                for handle,_,_ in channels:
                    source=cached.get(handle)
                    if source is None:
                        identity={'id':handle} if ID.fullmatch(handle) else {'forHandle':'@'+handle}
                        raw=fetch('channels',{'part':'snippet,contentDetails',**identity})
                        if len(raw['items'])!=1: raise LiveError('A selected channel could not be resolved. No substitute used.')
                        item=raw['items'][0]
                        cid=item['id'];playlist=item['contentDetails']['relatedPlaylists']['uploads'];title=item['snippet']['title']
                        if ID.fullmatch(handle) and cid!=handle:raise LiveError('YouTube returned a different channel ID. No substitute used.')
                        if not ID.fullmatch(cid) or not re.fullmatch(r'[A-Za-z0-9_-]{10,100}',playlist) or not isinstance(title,str):
                            raise ValueError('Invalid channel metadata')
                        source=dict(channel_id=cid,playlist=playlist,title=title[:500],baseline=None)
                        with db: images.remember(db,'avatar',handle,item['snippet'],now)
                    raw=fetch('playlistItems',{'part':'snippet,contentDetails','playlistId':source['playlist'],'maxResults':50})
                    if len(raw['items'])>50: raise ValueError('Unbounded response')
                    rows=[]
                    for item in raw['items']:
                        vid=item['contentDetails']['videoId'];title=item['snippet']['title'];published=item['contentDetails'].get('videoPublishedAt')
                        if not VID.fullmatch(vid) or not isinstance(title,str): raise ValueError('Invalid video metadata')
                        if not published: continue # unavailable/private items have no reliable publication timestamp
                        stamp=datetime.fromisoformat(published.replace('Z','+00:00'))
                        if stamp.tzinfo is None: raise ValueError('Missing timezone')
                        rows.append((vid,title[:1000],stamp.astimezone(timezone.utc).isoformat(),item['snippet']))
                    baseline=source['baseline'] is None
                    with db:
                        for vid,title,published,snippet in rows:
                            images.remember(db,'thumbnail',vid,snippet,now)
                            old=db.execute('SELECT 1 FROM uploads WHERE id=?',(vid,)).fetchone()
                            if not old and not baseline:new_count+=1
                            db.execute('''INSERT INTO uploads VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,published=excluded.published,fetched=excluded.fetched''',
                                       (vid,handle,title,published,now,now,int(baseline)))
                        if handle not in cached:
                            db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?)',(handle,source['channel_id'],source['playlist'],source['title'],now,now,now))
                        else:
                            # A playlist refresh does not refresh channel metadata's retention clock.
                            db.execute('UPDATE sources SET success=?,baseline=coalesce(baseline,?) WHERE handle=?',(now,now,handle))
                message=f'Refresh complete. {new_count} newly discovered items after baseline. Bounded to 50 recent items per channel.'
                with db:db.execute('UPDATE control SET message=?',(message,))
                return message
            except (LiveError,KeyError,TypeError,ValueError,IndexError) as exc:
                message=str(exc) if isinstance(exc,LiveError) else 'Unexpected YouTube metadata. This channel was not updated.'
                delay=exc.retry_after if isinstance(exc,LiveError) else 900
                failed_at=time.time() if fixed_time is None else now
                next_at=reset_at(failed_at) if isinstance(exc,LiveError) and exc.reset_day else failed_at+max(900,delay)
                with db:db.execute('UPDATE control SET message=?,next_at=?',(message,next_at))
                raise LiveError(message,delay) from None

def status(state=STATE,now=None):
    now=time.time() if now is None else now
    channels=current_channels(state)
    with database(state) as db:
        prune(db,now)
        used=db.execute('SELECT used FROM quota WHERE day=?',(quota_day(now),)).fetchone()
        sources={r['handle']:dict(r) for r in db.execute('SELECT * FROM sources')}
        return dict(used=used['used'] if used else 0,cap=CAP,key_ready=key_path(state).is_file(),tracked_count=len(channels),next_budget=refresh_budget(sources,channels),normal_budget=len(channels),
                    control=dict(db.execute('SELECT * FROM control').fetchone()),now=now,
                    media={(r['kind'],r['resource']) for r in db.execute('SELECT kind,resource FROM media')},
                    channels=[dict(handle=h,name=n,category=c,url=channel_url(h),source=sources.get(h),stale=bool(sources.get(h) and now-(sources[h]['success'] or 0)>86400)) for h,n,c in channels],
                    videos=[dict(r) for r in db.execute('SELECT * FROM uploads ORDER BY published DESC,id') if r['handle'] in {h for h,_,_ in channels}],
                    reset=reset_at(now))
