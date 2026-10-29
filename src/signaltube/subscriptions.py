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
    rows={}
    for c in data['creators'] if data else []:
        if not c['subscribed']:continue
        key=identities.get(c['id'],c['id'])
        rows[key]=dict(key=key,name=c['name'],events=c['events'],last=c['last'],tracked=key in tracked,imported=True)
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
    if not 1<=len(proposed)<=50:raise ValueError('Keep between 1 and 50 tracked channels, within the 100-unit cold-start budget.')
    with live.database(state) as db:
        cached={r['handle'] for r in db.execute('SELECT * FROM sources')}
    budget=live.refresh_budget(cached,proposed)
    plan=dict(profile=profile,key=key,action=action,name=row['name'],channels=proposed,before=channels,
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
