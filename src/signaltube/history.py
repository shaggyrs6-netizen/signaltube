"""Analytics of explicitly imported events only; never derived from upload counts."""
from .storage import connect
from .ranking import snapshot

def report(path):
    data=snapshot(path)
    with connect(path) as db:
        data['months']=[dict(r) for r in db.execute('SELECT substr(time,1,7) month,count(*) events FROM events GROUP BY month ORDER BY month DESC')]
        data['category_counts']=[dict(r) for r in db.execute("SELECT coalesce(c.category,'Unresolved creator') category,count(*) events FROM events e JOIN videos v ON v.id=e.video_id LEFT JOIN channels c ON c.id=v.channel_id GROUP BY category ORDER BY events DESC,category")]
        data['recent_creators']=sorted([c for c in data['channels'] if c['last']],key=lambda c:c['last'],reverse=True)
    data['no_records']=[c for c in data['channels'] if not c['events']]
    return data
