"""Explicit, local-only Takeout preview/import; never reads archives or discovers files."""
import csv
import fcntl
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .importers import channel_id, utc_time
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parents[2]/'var'/'takeout'
LIMIT=256*1024*1024
RECORD_LIMIT=1024*1024
SCHEMA=[
 'CREATE TABLE IF NOT EXISTS creators(id TEXT PRIMARY KEY,name TEXT NOT NULL,subscribed INTEGER NOT NULL DEFAULT 0)',
 'CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY,title TEXT NOT NULL,creator_id TEXT)',
 'CREATE TABLE IF NOT EXISTS events(event_key TEXT PRIMARY KEY,video_id TEXT,creator_id TEXT,time TEXT NOT NULL)',
 'CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,created TEXT NOT NULL,report TEXT NOT NULL)',
 'PRAGMA user_version=1']


def profile_path(profile,root=ROOT):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,39}',profile) or profile in ('demo','synthetic-demo'):
        raise ValueError('Use a real-data profile name of 1–40 lowercase letters, digits, hyphens or underscores; not demo.')
    return Path(root)/(profile+'.sqlite3')

@contextmanager
def source(path):
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size>LIMIT:
                raise ValueError('Select a regular extracted file no larger than 256 MiB. Archives are not accepted.')
            yield stream
    except OSError:
        raise ValueError('Cannot read the selected file. Use an extracted regular file, not a symlink or archive.') from None


def digest(path):
    result=hashlib.sha256()
    total=0
    with source(path) as stream:
        for chunk in iter(lambda:stream.read(65536),b''):
            total+=len(chunk)
            if total>LIMIT:raise ValueError('Selected file exceeds 256 MiB.')
            result.update(chunk)
    return result.hexdigest()


def json_rows(path):
    """Stream a JSON array, with a bounded buffer for any individual record."""
    with source(path) as stream:
        reader=io.TextIOWrapper(stream,encoding='utf-8-sig')
        decoder=json.JSONDecoder();buf='';eof=False;total=0
        def more():
            nonlocal buf,eof,total
            chunk=reader.read(65536)
            total+=len(chunk)
            if total>LIMIT:raise ValueError('History exceeds the input size limit.')
            eof=not chunk;buf+=chunk
        def ws():
            nonlocal buf
            buf=buf.lstrip()
            while not buf and not eof:more();buf=buf.lstrip()
        ws()
        if not buf.startswith('['):raise ValueError('History must be a JSON array. Choose JSON rather than HTML in Takeout.')
        buf=buf[1:];ws()
        if buf.startswith(']'):buf=buf[1:]
        else:
            while True:
                while True:
                    try:row,end=decoder.raw_decode(buf);break
                    except json.JSONDecodeError:
                        if eof:raise ValueError('Malformed history JSON. Nothing imported.') from None
                        if len(buf)>RECORD_LIMIT:raise ValueError('A history record exceeds the 1 MiB safety limit.')
                        more()
                if end>RECORD_LIMIT:raise ValueError('A history record exceeds the 1 MiB safety limit.')
                yield row
                buf=buf[end:];ws()
                if buf.startswith(']'):buf=buf[1:];break
                if not buf.startswith(','):raise ValueError('Malformed history JSON. Nothing imported.')
                buf=buf[1:];ws()
        ws()
        if buf:raise ValueError('Unexpected data after the history array. Nothing imported.')


def subscriptions(path):
    with source(path) as stream:
        reader=csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''))
        fields=reader.fieldnames or []
        mapped=[f.strip().casefold() for f in fields]
        if len(mapped)!=len(set(mapped)) or not {'channel id','channel url','channel title'}<=set(mapped):
            raise ValueError('Subscription CSV needs Channel Id, Channel Url and Channel Title columns.')
        for row in reader:
            yield {k.strip().casefold():v for k,v in row.items() if isinstance(k,str)}


def video_id(url):
    if not isinstance(url,str):return None
    u=urlsplit(url)
    if u.scheme not in ('https','http') or u.netloc not in ('www.youtube.com','youtube.com','m.youtube.com','music.youtube.com','youtu.be'):return None
    value=''
    if u.netloc=='youtu.be':value=u.path.strip('/')
    elif u.path=='/watch':value=parse_qs(u.query).get('v',[''])[0]
    elif u.path.startswith(('/shorts/','/live/')):value=u.path.split('/')[2]
    return value if re.fullmatch(r'[A-Za-z0-9_-]{11}',value) else None


def blank_schema(db):
    for statement in SCHEMA:db.execute(statement)


def apply_files(db,files,fail_after=None):
    r={'subscription_rows':0,'creators_added':0,'creator_names_updated':0,'video_metadata_updated':0,'subscriptions_added':0,'subscription_duplicates':0,
       'history_rows':0,'events_added':0,'event_duplicates':0,'non_watch_rows_skipped':0,
       'invalid_rows':0,'issues':[],'first_event':None,'last_event':None}
    def issue(kind,n,reason):
        r['invalid_rows']+=1
        if len(r['issues'])<30:r['issues'].append({'file_type':kind,'row':n,'reason':reason})
    if files.get('subscriptions'):
        for n,row in enumerate(subscriptions(files['subscriptions']),1):
            r['subscription_rows']+=1
            cid=row.get('channel id');name=row.get('channel title')
            try:valid=isinstance(name,str) and bool(name.strip()) and channel_id(row.get('channel url',''))==cid and bool(cid)
            except (ValueError,TypeError,AttributeError):valid=False
            if not valid:issue('subscriptions',n,'Missing or invalid channel identity/title');continue
            old=db.execute('SELECT subscribed,name FROM creators WHERE id=?',(cid,)).fetchone()
            r['creators_added']+=int(old is None)
            r['creator_names_updated']+=int(bool(old and old[1]!=name.strip()[:500]))
            r['subscriptions_added' if not old or not old[0] else 'subscription_duplicates']+=1
            db.execute('INSERT INTO creators VALUES(?,?,1) ON CONFLICT(id) DO UPDATE SET name=excluded.name,subscribed=1',(cid,name.strip()[:500]))
    if files.get('history'):
        for n,row in enumerate(json_rows(files['history']),1):
            r['history_rows']+=1
            if not isinstance(row,dict) or not isinstance(row.get('title'),str):issue('history',n,'Missing activity title');continue
            if not row['title'].startswith('Watched '):
                r['non_watch_rows_skipped']+=1
                if len(r['issues'])<30:r['issues'].append({'file_type':'history','row':n,'reason':'Not an English Watched event; skipped (may be another activity or export language)'})
                continue
            try:stamp=utc_time(row['time']);vid=video_id(row.get('titleUrl'))
            except (KeyError,ValueError,TypeError,AttributeError):issue('history',n,'Missing or invalid timestamp/video URL');continue
            # Retain a timestamped unavailable-video event without inventing a video ID.
            title=row['title'][8:];cid=None;cname=None
            for sub in row.get('subtitles',[]) if isinstance(row.get('subtitles',[]),list) else []:
                if not isinstance(sub,dict):continue
                try:found=channel_id(sub.get('url',''))
                except (ValueError,TypeError,AttributeError):found=None
                if found:
                    cid=found;cname=sub.get('name');break
            if cid:
                old=db.execute('SELECT 1 FROM creators WHERE id=?',(cid,)).fetchone()
                if old is None:
                    db.execute('INSERT INTO creators VALUES(?,?,0)',(cid,cname[:500] if isinstance(cname,str) and cname else cid));r['creators_added']+=1
            if vid:
                old_video=db.execute('SELECT title,creator_id FROM videos WHERE id=?',(vid,)).fetchone()
                r['video_metadata_updated']+=int(bool(old_video and (old_video[0]!=title[:1000] or (cid is not None and old_video[1]!=cid))))
                db.execute('INSERT INTO videos VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,creator_id=coalesce(excluded.creator_id,videos.creator_id)',(vid,title[:1000],cid))
            identity=vid or 'unavailable:'+hashlib.sha256(title.encode()).hexdigest()
            key=hashlib.sha256(('watch\0'+identity+'\0'+stamp).encode()).hexdigest()
            cur=db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',(key,vid,cid,stamp))
            if not cur.rowcount and cid:db.execute('UPDATE events SET creator_id=coalesce(creator_id,?) WHERE event_key=?',(cid,key))
            r['events_added' if cur.rowcount else 'event_duplicates']+=1
            r['first_event']=min(r['first_event'],stamp) if r['first_event'] else stamp
            r['last_event']=max(r['last_event'],stamp) if r['last_event'] else stamp
            if fail_after==n:raise RuntimeError('Simulated interruption')
    summary=db.execute('SELECT count(*),sum(video_id IS NULL),sum(coalesce(creator_id,(SELECT creator_id FROM videos WHERE id=video_id)) IS NULL),min(time),max(time) FROM events').fetchone()
    r['resulting_events']=summary[0];r['events_without_video_id']=summary[1] or 0;r['unresolved_creator_events']=summary[2] or 0
    r['resulting_first_event']=summary[3];r['resulting_last_event']=summary[4]
    r['resulting_subscriptions']=db.execute('SELECT count(*) FROM creators WHERE subscribed=1').fetchone()[0]
    return r


def target_digest(path):
    if not path.exists():return 'absent'
    if path.is_symlink():raise ValueError('Refusing a symlink as a real-data database.')
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):h.update(chunk)
    return h.hexdigest()


def prepare(profile,subscriptions_file=None,history_file=None,root=ROOT):
    path=profile_path(profile,root)
    files={k:Path(v) for k,v in [('subscriptions',subscriptions_file),('history',history_file)] if v is not None}
    if not files:raise ValueError('Select --subscriptions and/or --history explicitly.')
    hashes={k:digest(p) for k,p in files.items()}
    original=target_digest(path)
    db=sqlite3.connect(':memory:')
    try:
        if path.exists():
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as old:old.backup(db)
        blank_schema(db)
        report=apply_files(db,files)
    except (UnicodeError,csv.Error):raise ValueError('Unsupported encoding or malformed CSV. Use UTF-8 Takeout files.') from None
    finally:db.close()
    if hashes!={k:digest(p) for k,p in files.items()} or original!=target_digest(path):raise ValueError('Files or destination changed during preview. Preview again.')
    token=hashlib.sha256(json.dumps({'profile':profile,'files':hashes,'destination':original},sort_keys=True).encode()).hexdigest()
    return {'profile':profile,'preview_id':token,'files':files,'hashes':hashes,'destination_hash':original,'report':report,'path':path}


def commit(plan,confirmation,fail_after=None):
    if confirmation!=plan['preview_id']:raise ValueError('Confirmation does not match the preview. Nothing imported.')
    path=plan['path'];path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.parent.chmod(0o700)
    fd=os.open(path.parent/(path.stem+'.lock'),os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if target_digest(path)!=plan['destination_hash'] or plan['hashes']!={k:digest(p) for k,p in plan['files'].items()}:
            raise ValueError('Files or destination changed since preview. Preview again; nothing imported.')
        fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.close(fd);path.chmod(0o600)
        db=sqlite3.connect(path)
        try:
            db.execute('BEGIN IMMEDIATE')
            blank_schema(db)
            report=apply_files(db,plan['files'],fail_after)
            if plan['hashes']!={k:digest(p) for k,p in plan['files'].items()}:raise ValueError('Input changed during import. Import rolled back.')
            if report!=plan['report']:raise ValueError('Preview no longer matches. Import rolled back.')
            db.execute('INSERT INTO imports(created,report) VALUES(?,?)',(datetime.now(timezone.utc).isoformat(),json.dumps(report)))
            db.commit()
            return report
        except BaseException:db.rollback();raise
        finally:db.close()


def overview(profile,root=ROOT):
    path=profile_path(profile,root)
    if not path.exists():return None
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        summary=dict(db.execute('SELECT count(*) events,count(DISTINCT video_id) videos,min(time) first,max(time) last FROM events').fetchone())
        summary['subscriptions']=db.execute('SELECT count(*) FROM creators WHERE subscribed=1').fetchone()[0]
        summary['unavailable']=db.execute('SELECT count(*) FROM events WHERE video_id IS NULL').fetchone()[0]
        creators=[dict(r) for r in db.execute('''SELECT c.*,count(e.event_key) events,max(e.time) last FROM creators c LEFT JOIN
          (SELECT events.*,coalesce(events.creator_id,videos.creator_id) resolved FROM events LEFT JOIN videos ON videos.id=events.video_id) e
          ON e.resolved=c.id GROUP BY c.id ORDER BY events DESC,c.name''')]
        summary['unresolved']=summary['events']-sum(c['events'] for c in creators)
        months=[dict(r) for r in db.execute('SELECT substr(time,1,7) month,count(*) events FROM events GROUP BY month ORDER BY month DESC')]
        latest=db.execute('SELECT created,report FROM imports ORDER BY id DESC LIMIT 1').fetchone()
        return {'summary':summary,'creators':creators,'months':months,'latest':{'created':latest['created'],'report':json.loads(latest['report'])} if latest else None}
