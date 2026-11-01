"""Real local queues. Explicit build and reversible choices; never refreshes YouTube."""
import json
import math
import secrets
from datetime import datetime,timezone
from urllib.parse import urlencode
from . import library,shortlist,live,images


def build_plan(state,root,options):
    result=shortlist.build(state,root,**options)
    refs=[library.fingerprint(v['id']) for v in result['picks']+result['alternatives']]
    with library.personal(state) as db:
        db.execute('INSERT INTO watch_plan VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET generated=excluded.generated,options=excluded.options,fingerprints=excluded.fingerprints',
                   (result['generated'],json.dumps(options),json.dumps(refs)))
    shortlist.options_save(state,root,**options,categories=result['categories'])


def video_action(state,vid,action):
    if action not in ('save','unsave','watched','dismiss'):raise ValueError('Unsupported video action.')
    if vid not in {v['id'] for v in live.status(state)['videos']}:raise ValueError('This video is no longer available in the cache. No choice changed.')
    fp=library.fingerprint(vid)
    with library.personal(state) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT saved,review,categories FROM video_preferences WHERE fingerprint=?',(fp,)).fetchone()
        before=dict(old) if old else None
        values=dict(before) if before else dict(saved=0,review='unreviewed',categories=None)
        if action=='save':values['saved']=1
        elif action=='unsave':values['saved']=0
        elif action=='watched':values['review']='marked watched'
        else:values['review']='dismissed'
        db.execute('INSERT INTO video_preferences VALUES(?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET saved=excluded.saved,review=excluded.review,categories=excluded.categories',
                   (fp,values['saved'],values['review'],values['categories']))
        db.execute('INSERT INTO watch_undo VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token,fingerprint=excluded.fingerprint,before_state=excluded.before_state,action=excluded.action',
                   (secrets.token_urlsafe(24),fp,json.dumps(before),action))


def undo(state,token):
    with library.personal(state) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM watch_undo WHERE id=1').fetchone()
        if not row or not secrets.compare_digest(row['token'],token):raise ValueError('This Undo is no longer current. No newer choice was overwritten.')
        before=json.loads(row['before_state'])
        if before is None:db.execute('DELETE FROM video_preferences WHERE fingerprint=?',(row['fingerprint'],))
        else:
            db.execute('INSERT INTO video_preferences VALUES(?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET saved=excluded.saved,review=excluded.review,categories=excluded.categories',
                       (row['fingerprint'],before['saved'],before['review'],before['categories']))
        db.execute('DELETE FROM watch_undo WHERE id=1')


def art_kind(categories):
    text=' '.join(categories).lower()
    return 'flight' if 'aviation' in text else 'terminal' if 'linux' in text or 'comput' in text else 'nodes' if 'machine' in text or ' ai ' in ' '+text+' ' else 'coast' if 'boat' in text or 'weather' in text else 'grid'


def page(state,root,view='watch',category='',query='',page=1):
    if view not in ('watch','catchup','saved'):raise ValueError('Unknown view.')
    if len(query)>120 or len(category)>60:raise ValueError('Filter is too long.')
    data,cp,vp,categories=shortlist.context(state)
    options,option_notice=shortlist.options_load(state,categories,root)
    with library.personal(state) as db:
        plan=db.execute('SELECT * FROM watch_plan WHERE id=1').fetchone()
        last=db.execute('SELECT token,action FROM watch_undo WHERE id=1').fetchone()
    channels={c['handle']:c for c in data['channels']}
    available={}
    for v in data['videos']:
        pref=vp.get(library.fingerprint(v['id']),{});c=channels[v['handle']]
        cats=json.loads(pref['categories']) if pref.get('categories') else c['categories']
        v.update(creator=c['name'],categories=cats,category=' · '.join(cats),kind=art_kind(cats),
                 thumbnail=('thumbnail',v['id']) in data['media'],avatar=('avatar',v['handle']) in data['media'],
                 saved=bool(pref.get('saved')),review=pref.get('review','unreviewed'),stale=c['stale'] or not c['source'])
        available[library.fingerprint(v['id'])]=v
    pending=[v for v in available.values() if v['review']=='unreviewed']
    saved=[v for v in available.values() if v['saved']]
    unavailable_entries=[dict(fingerprint=fp,review=p['review']) for fp,p in vp.items() if p['saved'] and fp not in available]
    unavailable_saved=len(unavailable_entries)
    picks=[];alternatives=[];unavailable_plan=0;plan_notice='';generated=None
    if plan:
        generated=plan['generated'];built_options=json.loads(plan['options'])
        if built_options['category'] not in categories:built_options['category']=''
        # Explain only the retained references. This never selects or replaces a pick.
        signals=shortlist.candidate_data(state,root,**built_options)
        current={library.fingerprint(v['id']):v for v in signals['candidates']}
        seen_categories={}
        for index,fp in enumerate(json.loads(plan['fingerprints'])):
            if fp not in current or fp not in available:
                unavailable_plan+=1;continue
            v={**available[fp],**current[fp]};v['rank']=index+1
            v['adjustment']=3*sum(seen_categories.get(c,0) for c in set(v['categories']))
            v['score']=v['base']-v['adjustment']
            for c in set(v['categories']):seen_categories[c]=seen_categories.get(c,0)+1
            (picks if index<5 else alternatives).append(v)
        plan_notice='Order is kept from your last manual build. Reasons use current local choices and cache; rebuild to update the ranking.'
        if signals['history_available'] is False:plan_notice+=' No imported history is available for this profile; history exclusions cannot be applied.'
        elif signals['history_last']:plan_notice+=' History coverage ends '+signals['history_last'][:10]+' (UTC).'
        if built_options!=options:plan_notice+=' Your saved build options have changed since this list was built.'
    rows=pending if view=='catchup' else saved if view=='saved' else []
    rows=[v for v in rows if (not category or category in v['categories']) and query.casefold() in (v['title']+' '+v['creator']).casefold()]
    total=len(rows);pages=max(1,(total+11)//12);page=max(1,min(page,pages))
    rows=rows[(page-1)*12:page*12]
    groups={}
    for v in rows:groups.setdefault(v['published'][:10],[]).append(v)
    successes=[c['source']['success'] for c in data['channels'] if c['source'] and c['source']['success']]
    return dict(view=view,category=category,query=query,page=page,pages=pages,total=total,groups=groups,
        picks=picks,alternatives=alternatives,generated=generated,unavailable_plan=unavailable_plan,
        profiles=shortlist.profiles(root),image_mode=images.mode(state),unavailable_entries=unavailable_entries,
        cooldown_minutes=max(0,math.ceil((data['control']['next_at']-data['now'])/60)),
        fresh_channels=sum(bool(c['source'] and c['source']['success'] and data['now']-c['source']['success']<=86400) for c in data['channels']),
        options=options,option_notice=option_notice,plan_notice=plan_notice,categories=categories,
        pending=len(pending),saved_count=len(saved),unavailable_saved=unavailable_saved,
        handled=len(available)-len(pending),cached_count=len(available),quota=data['used'],cap=data['cap'],
        next_budget=data['next_budget'],key_ready=data['key_ready'],next_at=data['control']['next_at'],
        refresh_message=data['control']['message'],last_refresh=max(successes) if successes else None,
        stale_channels=sum(c['stale'] or not c['source'] for c in data['channels']),tracked_count=data['tracked_count'],
        undo=dict(last) if last else None,
        base='/watch?'+urlencode(dict(view=view,category=category,query=query)))


def remove_unavailable(state,root,fp):
    if fp not in {v['fingerprint'] for v in page(state,root,'saved')['unavailable_entries']}:
        raise ValueError('This saved entry is no longer unavailable. Reload Saved.')
    with library.personal(state) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT saved,review,categories FROM video_preferences WHERE fingerprint=?',(fp,)).fetchone()
        if not row or not row['saved']:raise ValueError('Saved entry already changed.')
        db.execute('UPDATE video_preferences SET saved=0 WHERE fingerprint=?',(fp,))
        db.execute('INSERT INTO watch_undo VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token,fingerprint=excluded.fingerprint,before_state=excluded.before_state,action=excluded.action',
                   (secrets.token_urlsafe(24),fp,json.dumps(dict(row)),'unsave'))
