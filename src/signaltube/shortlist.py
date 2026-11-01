"""Transparent local shortlist. No model, transport, scheduler or remote enrichment."""
import json
import math
import sqlite3
import time
from datetime import datetime
from . import live, library, takeout
from .subscriptions import TEST_IDENTITIES


DEFAULT_OPTIONS=dict(profile='local',category='',use_history=True,exclude_history=True)

def options_load(state,categories,root=None):
    with library.personal(state) as db:
        row=db.execute('SELECT profile,category,use_history,exclude_history FROM shortlist_preferences WHERE id=1').fetchone()
    options=dict(row) if row else dict(DEFAULT_OPTIONS)
    if not row and root is not None:
        available=profiles(root)
        if len(available)==1:options['profile']=available[0]
    options['use_history']=bool(options['use_history'])
    options['exclude_history']=bool(options['exclude_history'])
    notice=''
    if options['category'] and options['category'] not in categories:
        notice='Your saved category is no longer available. No category boost is selected; choose another or save these options.'
        options['category']=''
    return options,notice

def options_save(state,root,profile,category,use_history,exclude_history,categories):
    takeout.profile_path(profile,root)
    if category and category not in categories:raise ValueError('Choose a category currently available in your library.')
    with library.personal(state) as db:
        db.execute('INSERT INTO shortlist_preferences VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET profile=excluded.profile,category=excluded.category,use_history=excluded.use_history,exclude_history=excluded.exclude_history',
                   (profile,category,int(use_history),int(exclude_history)))


def context(state):
    data=live.status(state)
    with library.personal(state) as db:
        creators={r['handle']:dict(r) for r in db.execute('SELECT * FROM creator_preferences')}
        videos={r['fingerprint']:dict(r) for r in db.execute('SELECT * FROM video_preferences')}
    categories=set()
    for c in data['channels']:
        p=creators.get(c['handle'],{})
        c['categories']=json.loads(p['categories']) if p else [c['category']]
        categories.update(c['categories'])
    for p in videos.values():
        if p['categories']:categories.update(json.loads(p['categories']))
    return data,creators,videos,sorted(categories)


def history(profile,root):
    path=takeout.profile_path(profile,root)
    if not path.exists():return {},set(),None
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        counts=dict(db.execute('''SELECT coalesce(e.creator_id,v.creator_id),count(*) FROM events e
            LEFT JOIN videos v ON v.id=e.video_id GROUP BY coalesce(e.creator_id,v.creator_id)'''))
        watched={r[0] for r in db.execute('SELECT DISTINCT video_id FROM events WHERE video_id IS NOT NULL')}
        last=db.execute('SELECT max(time) FROM events').fetchone()[0]
    return counts,watched,last


def candidate_data(state,root,profile=None,category='',use_history=True,exclude_history=True,now=None):
    now=time.time() if now is None else now
    if profile is None:profile=options_load(state,[],root)[0]['profile']
    takeout.profile_path(profile,root) # Always validate; never silently fall back to demo.
    data,creators,preferences,categories=context(state)
    if category and category not in categories:raise ValueError('Choose a category currently available in your library.')
    counts,watched,last=history(profile,root) if use_history or exclude_history else ({},set(),None)
    channels={c['handle']:c for c in data['channels']}
    aliases={handle:cid for cid,handle in TEST_IDENTITIES.items()}
    candidates=[];excluded=dict(local_state=0,history=0,invalid_date=0)
    for v in data['videos']:
        p=preferences.get(library.fingerprint(v['id']),{})
        if p.get('review') in ('dismissed','marked watched'):
            excluded['local_state']+=1;continue
        if exclude_history and v['id'] in watched:
            excluded['history']+=1;continue
        try:
            stamp=datetime.fromisoformat(v['published'].replace('Z','+00:00'))
            if stamp.tzinfo is None:raise ValueError('Missing timezone')
            age=(now-stamp.timestamp())/86400
            if age<0:raise ValueError('Future publication')
        except (ValueError,TypeError,OverflowError):
            excluded['invalid_date']+=1;continue
        c=channels[v['handle']];cp=creators.get(v['handle'],{})
        cats=json.loads(p['categories']) if p.get('categories') else c['categories']
        reasons=[]
        def add(label,points):
            if points:reasons.append(dict(label=label,points=points))
        add('Favourite creator',8 if cp.get('favourite') else 0)
        add('Pinned creator',4 if cp.get('pinned') else 0)
        add('Saved for later',2 if p.get('saved') else 0)
        add('Your chosen category: '+category,6 if category and category in cats else 0)
        recent=6 if age<=1 else 4 if age<=3 else 3 if age<=7 else 1 if age<=30 else 0
        add('Published within '+('24 hours' if age<=1 else '3 days' if age<=3 else '7 days' if age<=7 else '30 days'),recent)
        cid=(c.get('source') or {}).get('channel_id') or aliases.get(v['handle'],v['handle'])
        events=counts.get(cid,0) if use_history else 0
        add(f'{events} imported watch events for this creator',min(6,int(math.log2(events+1))))
        base=sum(r['points'] for r in reasons)
        candidates.append(dict(id=v['id'],title=v['title'],creator=c['name'],handle=v['handle'],categories=cats,
            published=v['published'],stamp=stamp.timestamp(),base=base,reasons=reasons,
            stale=not c.get('source') or bool(c.get('stale')),saved=bool(p.get('saved'))))
    return dict(candidates=candidates,excluded=excluded,generated=now,history_last=last,
        history_available=takeout.profile_path(profile,root).exists() if use_history or exclude_history else None,
        quota=data['used'],cap=data['cap'],categories=categories)


def build(state,root,profile=None,category='',use_history=True,exclude_history=True,now=None):
    data=candidate_data(state,root,profile,category,use_history,exclude_history,now)
    candidates=data.pop('candidates')
    # Greedy diversity adjustment, applied after each pick. Stable ties: newest, then video ID.
    selected=[];used_creators=set();used_categories={}
    while len(selected)<8:
        remaining=[c for c in candidates if c['handle'] not in used_creators]
        if not remaining:break
        def penalty(c):return 3*sum(used_categories.get(cat,0) for cat in set(c['categories']))
        best=min(remaining,key=lambda c:(-(c['base']-penalty(c)),-c['stamp'],c['id']))
        adjustment=penalty(best)
        selected.append({**best,'adjustment':adjustment,'score':best['base']-adjustment})
        used_creators.add(best['handle'])
        for cat in set(best['categories']):used_categories[cat]=used_categories.get(cat,0)+1
    return dict(**data,picks=selected[:5],alternatives=selected[5:],eligible=len(candidates),
                available_creators=len({c['handle'] for c in candidates}))


def profiles(root):
    """Only list valid local import filenames; do not create or rename personal profiles."""
    from pathlib import Path
    result=[]
    for path in sorted(Path(root).glob('*.sqlite3')):
        try: takeout.profile_path(path.stem,root)
        except ValueError: continue
        if path.is_file() and not path.is_symlink():result.append(path.stem)
    return result
