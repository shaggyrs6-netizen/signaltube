"""Imported event counts, not watch time or algorithmic YouTube scores."""
import json
from .storage import connect

def snapshot(path, category='', start='', end='', state='', page=1):
    conditions, params = [], []
    if start:
        conditions.append('e.time >= ?'); params.append(start + 'T00:00:00')
    if end:
        conditions.append('e.time < ?'); params.append(end + 'T23:59:59.999999Z')
    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    with connect(path) as db:
        counts = dict(db.execute('SELECT key,value FROM preferences'))
        summary = dict(db.execute('SELECT count(*) events,count(DISTINCT video_id) videos,min(time) first,max(time) last FROM events').fetchone())
        summary['channels'] = db.execute('SELECT count(*) FROM channels WHERE tracked=1').fetchone()[0]
        summary['unresolved'] = db.execute('SELECT count(*) FROM events e JOIN videos v ON v.id=e.video_id LEFT JOIN channels c ON c.id=v.channel_id WHERE c.id IS NULL').fetchone()[0]
        channels = [dict(r) for r in db.execute(f'''SELECT c.*,coalesce(s.events,0) events,s.last FROM channels c LEFT JOIN
          (SELECT v.channel_id,count(*) events,max(e.time) last FROM events e JOIN videos v ON v.id=e.video_id {where} GROUP BY v.channel_id) s
          ON s.channel_id=c.id WHERE c.tracked=1 ORDER BY events DESC,c.name''', params)]
        if category:
            channels = [c for c in channels if c['category'] == category]
        video_conditions, video_params = list(conditions), list(params)
        if category:
            video_conditions.append("coalesce(c.category,'Other / uncategorised')=?"); video_params.append(category)
        if state:
            video_conditions.append("coalesce(a.state,'unreviewed')=?"); video_params.append(state)
        vwhere = 'WHERE ' + ' AND '.join(video_conditions) if video_conditions else ''
        videos = [dict(r) for r in db.execute(f'''SELECT v.*,coalesce(c.name,'Unresolved creator') creator,
          coalesce(c.category,'Other / uncategorised') category,coalesce(a.state,'unreviewed') state,
          max(e.time) last,count(*) events FROM videos v JOIN events e ON e.video_id=v.id
          LEFT JOIN channels c ON c.id=v.channel_id LEFT JOIN annotations a ON a.video_id=v.id
          {vwhere} GROUP BY v.id ORDER BY last DESC,v.id''', video_params)]
        total = len(videos)
        page = max(1, min(page, max(1, (total+11)//12)))
        recent = [dict(r) for r in db.execute('SELECT * FROM imports ORDER BY id DESC LIMIT 4')]
        for r in recent:
            r['report'] = json.loads(r['report'])
        return dict(summary=summary,channels=channels,videos=videos[(page-1)*12:page*12],total=total,
                    page=page,pages=max(1,(total+11)//12),imports=recent,preferences=counts)
