"""Personal organisation, independent of the expiring YouTube cache and quota ledger."""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from .storage import CATEGORIES
from . import live

DEFAULTS={'topic':'','category':'','query':'','start':'','end':'','view':'inbox','sort':'newest','density':'comfortable','favourites':'0'}
REVIEWS=('unreviewed','reviewed','marked watched','dismissed')

@contextmanager
def personal(state):
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(state/'personal.sqlite3',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.close(fd)
    db=sqlite3.connect(state/'personal.sqlite3',timeout=5);db.row_factory=sqlite3.Row
    try:
        db.executescript('''CREATE TABLE IF NOT EXISTS creator_preferences(handle TEXT PRIMARY KEY,categories TEXT NOT NULL,favourite INTEGER NOT NULL DEFAULT 0,pinned INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS video_preferences(fingerprint TEXT PRIMARY KEY,saved INTEGER NOT NULL DEFAULT 0,review TEXT NOT NULL DEFAULT 'unreviewed',categories TEXT);
        CREATE TABLE IF NOT EXISTS library_preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shortlist_preferences(id INTEGER PRIMARY KEY CHECK(id=1),profile TEXT NOT NULL,category TEXT NOT NULL,use_history INTEGER NOT NULL,exclude_history INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS watch_plan(id INTEGER PRIMARY KEY CHECK(id=1),generated REAL NOT NULL,options TEXT NOT NULL,fingerprints TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS watch_undo(id INTEGER PRIMARY KEY CHECK(id=1),token TEXT NOT NULL,fingerprint TEXT NOT NULL,before_state TEXT NOT NULL,action TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS undo_after_insert AFTER INSERT ON video_preferences BEGIN DELETE FROM watch_undo WHERE fingerprint=NEW.fingerprint; END;
        CREATE TRIGGER IF NOT EXISTS undo_after_update AFTER UPDATE ON video_preferences BEGIN DELETE FROM watch_undo WHERE fingerprint=NEW.fingerprint; END;
        CREATE TRIGGER IF NOT EXISTS undo_after_delete AFTER DELETE ON video_preferences BEGIN DELETE FROM watch_undo WHERE fingerprint=OLD.fingerprint; END;
        PRAGMA user_version=1;''')
        with db:yield db
    finally:db.close()

def fingerprint(vid):
    return hashlib.sha256(vid.encode()).hexdigest()

def categories(raw):
    result=[]
    for item in raw.split(','):
        item=item.strip()
        if not item:continue
        if len(item)>60 or any(ord(c)<32 for c in item):raise ValueError('Use category names of at most 60 characters, separated by commas.')
        if item not in result:result.append(item)
    if len(result)>8:raise ValueError('Use up to eight categories.')
    return result

def creator_save(state,fields):
    handle=fields.get('handle','')
    if handle not in {h for h,_,_ in live.current_channels(state)}:raise ValueError('Unknown creator')
    cats=categories(fields.get('categories','')) or ['Other / uncategorised']
    with personal(state) as db:
        db.execute('INSERT INTO creator_preferences VALUES(?,?,?,?) ON CONFLICT(handle) DO UPDATE SET categories=excluded.categories,favourite=excluded.favourite,pinned=excluded.pinned',
                   (handle,json.dumps(cats),int(fields.get('favourite')=='1'),int(fields.get('pinned')=='1')))

def video_save(state,fields):
    vid=fields.get('video','')
    if not live.VID.fullmatch(vid):raise ValueError('Invalid video')
    # Only accept a current cached item; no network lookup or arbitrary bookmark fetching.
    data=live.status(state)
    if vid not in {v['id'] for v in data['videos']}:raise ValueError('This video is no longer cached. Refresh manually before editing it.')
    key=fingerprint(vid);action=fields.get('action','update')
    with personal(state) as db:
        old=db.execute('SELECT * FROM video_preferences WHERE fingerprint=?',(key,)).fetchone()
        saved=old['saved'] if old else 0
        review=old['review'] if old else 'unreviewed'
        cats=old['categories'] if old else None
        if action=='save':saved=1
        elif action=='unsave':saved=0
        elif action=='dismiss':review='dismissed'
        elif action=='restore':review='unreviewed'
        elif action=='update':
            review=fields.get('review','unreviewed')
            if review not in REVIEWS:raise ValueError('Unsupported review state')
            values=categories(fields.get('categories',''))
            cats=json.dumps(values) if values else None
        else:raise ValueError('Unsupported action')
        db.execute('INSERT INTO video_preferences VALUES(?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET saved=excluded.saved,review=excluded.review,categories=excluded.categories',(key,saved,review,cats))

def preferences_save(state,fields):
    values={k:str(fields.get(k,default)) for k,default in DEFAULTS.items()}
    if fields.get('reset')=='1':values=dict(DEFAULTS)
    if values['topic'] not in ['',*[h for h,_,_ in live.current_channels(state)]]:raise ValueError('Unknown creator')
    if values['view'] not in ('inbox','all','saved','unreviewed','reviewed','marked watched','dismissed'):raise ValueError('Unknown view')
    if values['sort'] not in ('newest','oldest','creator','favourites'):raise ValueError('Unknown sort')
    if values['density'] not in ('comfortable','compact'):raise ValueError('Unknown density')
    if values['favourites'] not in ('0','1'):raise ValueError('Unknown favourite filter')
    if len(values['query'])>120 or len(values['category'])>60:raise ValueError('Filter text is too long')
    for key in ('start','end'):
        if values[key]:values[key]=date.fromisoformat(values[key]).isoformat()
    if values['start'] and values['end'] and values['start']>values['end']:raise ValueError('Start date must be on or before end date')
    with personal(state) as db:
        db.executemany('INSERT INTO library_preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',values.items())

def library_data(state,page=1,topic_override=None):
    data=live.status(state)
    with personal(state) as db:
        prefs={**DEFAULTS,**dict(db.execute('SELECT key,value FROM library_preferences'))}
        cp={r['handle']:dict(r) for r in db.execute('SELECT * FROM creator_preferences')}
        vp={r['fingerprint']:dict(r) for r in db.execute('SELECT * FROM video_preferences')}
    if topic_override is not None:
        if topic_override not in ['',*[h for h,_,_ in live.current_channels(state)]]:raise ValueError('Unknown topic')
        prefs['topic']=topic_override
    if prefs['topic'] not in {h for h,_,_ in live.current_channels(state)}:prefs['topic']=''
    all_categories=set(CATEGORIES)
    for c in data['channels']:
        p=cp.get(c['handle'],{})
        c.update(categories=json.loads(p['categories']) if p else [c['category']],favourite=bool(p.get('favourite')),pinned=bool(p.get('pinned')))
        c['category_text']=', '.join(c['categories']);all_categories.update(c['categories'])
    creators={c['handle']:c for c in data['channels']}
    for v in data['videos']:
        p=vp.get(fingerprint(v['id']),{})
        c=creators[v['handle']]
        v.update(saved=bool(p.get('saved')),review=p.get('review','unreviewed'),creator=c['name'],favourite=c['favourite'],pinned=c['pinned'])
        v['categories']=json.loads(p['categories']) if p.get('categories') else c['categories']
        v['category_override']=', '.join(json.loads(p['categories'])) if p.get('categories') else ''
        all_categories.update(v['categories'])
    all_videos=data['videos']
    counts={'all':len(all_videos),'saved':sum(v['saved'] for v in all_videos),'unreviewed':sum(v['review']=='unreviewed' for v in all_videos),'dismissed':sum(v['review']=='dismissed' for v in all_videos)}
    # Personal choices survive cache expiry, but API metadata is never copied here.
    known={fingerprint(v['id']) for v in all_videos}
    unavailable_saved=sum(p['saved'] for key,p in vp.items() if key not in known)
    videos=[]
    for v in all_videos:
        if prefs['topic'] and v['handle']!=prefs['topic']:continue
        if prefs['category'] and prefs['category'] not in v['categories']:continue
        if prefs['query'].casefold() not in (v['title']+' '+v['creator']).casefold():continue
        if prefs['start'] and v['published'][:10]<prefs['start']:continue
        if prefs['end'] and v['published'][:10]>prefs['end']:continue
        if prefs['favourites']=='1' and not v['favourite']:continue
        view=prefs['view']
        if view=='inbox' and v['review']=='dismissed':continue
        if view=='saved' and not v['saved']:continue
        if view in REVIEWS and v['review']!=view:continue
        videos.append(v)
    videos.sort(key=lambda v:(v['published'],v['id']),reverse=prefs['sort']!='oldest')
    if prefs['sort']=='creator':videos.sort(key=lambda v:v['creator'].casefold())
    if prefs['sort']=='favourites':videos.sort(key=lambda v:(not v['pinned'],not v['favourite']))
    total=len(videos);pages=max(1,(total+11)//12);page=max(1,min(page,pages))
    data.update(videos=videos[(page-1)*12:page*12],total=total,pages=pages,page=page,filters=prefs,
                categories=sorted(all_categories),counts=counts,unavailable_saved=unavailable_saved,reviews=REVIEWS)
    return data
