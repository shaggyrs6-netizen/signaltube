import json
import os
import hmac
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlencode
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .storage import initialise, connect, CATEGORIES
from .importers import import_file
from .ranking import snapshot
from . import live, theme, library, history, takeout, subscriptions, shortlist, prototype, dashboard

ROOT = Path(__file__).resolve().parents[2]
STATES = ['unreviewed', 'reviewed', 'saved', 'dismissed', 'marked watched']

def load_demo(path):
    reports = []
    for kind, filename in [('subscriptions','subscriptions.csv'),('history','watch-history.json')]:
        reports.append(import_file(Path(__file__).parent/'demo'/filename, path, kind))
    return reports

def create_app(db_path=None, token=None, port=8765, live_state=None, theme_path=None, takeout_root=None):
    db_path = Path(db_path or live.STATE/'signaltube.sqlite3')
    takeout_root=Path(takeout_root) if takeout_root is not None else takeout.ROOT
    if db_path.resolve().is_relative_to(takeout_root.resolve()):
        raise ValueError('Real Takeout databases cannot be used as the synthetic demo database.')
    initialise(db_path)
    live_state = live.STATE if live_state is None else Path(live_state)
    theme_path = theme.PALETTE if theme_path is None else Path(theme_path)
    live.status(live_state) # Retention cleanup before any UI is served; no network.
    token = token or secrets.token_urlsafe(32)
    origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token, app.state.db_path = token, db_path
    templates = Jinja2Templates(directory=str(Path(__file__).parent/'web'/'templates'))
    templates.env.filters['utc'] = lambda stamp: datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    templates.env.filters['localtime'] = lambda stamp: datetime.fromtimestamp(stamp,ZoneInfo('America/Chicago')).strftime('%d %b, %I:%M %p %Z')

    @app.middleware('http')
    async def guard(request, call_next):
        if request.headers.get('host') not in hosts:
            return PlainTextResponse('Unrecognised local host.', status_code=400)
        if request.method not in ('GET','HEAD','POST'):
            return PlainTextResponse('Method not allowed.',status_code=405)
        if request.method == 'GET' and request.url.path == '/' and secrets.compare_digest(request.query_params.get('token',''),token):
            response = RedirectResponse('/watch', status_code=303)
            response.set_cookie('signaltube_session', token, httponly=True, samesite='strict')
        elif not secrets.compare_digest(request.cookies.get('signaltube_session',''),token):
            response = HTMLResponse('<h1>SignalTube is local and locked</h1><p>Run <code>./run.sh</code> in the SignalTube folder. It starts the app if needed and opens a fresh unlock link. No YouTube refresh is made.</p>', status_code=401)
        elif request.method == 'POST' and request.headers.get('origin') not in origins:
            response = PlainTextResponse('Request origin rejected.',status_code=403)
        else:
            response = await call_next(request)
        response.headers.update({'Cache-Control':'no-store', 'Referrer-Policy':'same-origin',
            'X-Content-Type-Options':'nosniff', 'X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; connect-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"})
        return response

    async def form(request):
        if request.headers.get('content-type','').split(';')[0] != 'application/x-www-form-urlencoded':
            raise ValueError('Unsupported form type')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 8192:
                raise ValueError('Form too large')
        values = {k:v[-1] for k,v in parse_qs(data.decode(),keep_blank_values=True).items()}
        if not secrets.compare_digest(values.pop('csrf',''),token):
            raise ValueError('Invalid form token. Reload the dashboard.')
        return values

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return PlainTextResponse(str(exc),status_code=400)

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request, page: int=1):
        with connect(db_path) as db:
            filters = dict(db.execute('SELECT key,value FROM preferences'))
        data = snapshot(db_path, **{k:filters.get(k,'') for k in ('category','start','end','state')},page=page)
        return templates.TemplateResponse(request=request,name='index.html',context={**data,'csrf':token,'categories':CATEGORIES,'states':STATES,'filters':filters})

    @app.get('/local-status')
    def local_status():
        return {'app':'signaltube','pid':os.getpid()}

    @app.get('/theme.css')
    def theme_css():
        return Response(theme.css(theme_path),media_type='text/css')

    def live_page(request, page=1, topic=None, message='', notice=''):
        data=library.library_data(live_state,page,topic)
        return templates.TemplateResponse(request=request,name='library.html',context={**data,'csrf':token,'message':message,'notice':notice})

    @app.get('/live',response_class=HTMLResponse)
    def live_index(request: Request,page:int=1,topic:str|None=None,notice:str=''):
        notices={'saved':'Local choice saved. No API request sent.','filters':'Filters applied.','reset':'Filters reset.'}
        return live_page(request,page,topic,notice=notices.get(notice,''))

    @app.post('/live/filters')
    async def library_filters(request: Request):
        fields=await form(request)
        library.preferences_save(live_state,fields)
        return RedirectResponse('/live?notice=filters',status_code=303)

    @app.post('/live/view')
    async def library_view(request: Request):
        fields=await form(request)
        data=library.library_data(live_state)
        library.preferences_save(live_state,{**data['filters'],'view':fields.get('view','inbox')})
        return RedirectResponse('/live',status_code=303)

    @app.post('/live/video')
    async def library_video(request: Request):
        fields=await form(request)
        page=max(1,min(10000,int(fields.get('page','1'))))
        library.video_save(live_state,fields)
        return RedirectResponse(f'/live?page={page}&notice=saved',status_code=303)

    @app.get('/creators',response_class=HTMLResponse)
    def creators(request: Request,notice:str=''):
        data=library.library_data(live_state)
        return templates.TemplateResponse(request=request,name='creators.html',context={**data,'csrf':token,'notice':'Creator choices saved locally.' if notice=='saved' else ''})

    @app.post('/creators/save')
    async def creator_save(request: Request):
        library.creator_save(live_state,await form(request))
        return RedirectResponse('/creators?notice=saved',status_code=303)

    @app.post('/live/refresh',response_class=HTMLResponse)
    async def live_refresh(request: Request):
        await form(request)
        try:
            await run_in_threadpool(live.refresh,live_state)
        except live.LiveError as exc:
            return live_page(request,message=str(exc))
        return RedirectResponse('/live',status_code=303)

    @app.get('/setup',response_class=HTMLResponse)
    def setup(request: Request):
        return templates.TemplateResponse(request=request,name='setup.html',context={})

    @app.get('/privacy',response_class=HTMLResponse)
    def privacy(request: Request):
        return templates.TemplateResponse(request=request,name='privacy.html',context={})

    @app.get('/history',response_class=HTMLResponse)
    def history_page(request: Request):
        return templates.TemplateResponse(request=request,name='history.html',context=history.report(db_path))

    @app.get('/takeout',response_class=HTMLResponse)
    def real_history(request: Request,profile:str='lee',page:int=1):
        data=takeout.overview(profile,takeout_root)
        page=max(1,page)
        total=len(data['creators']) if data else 0
        pages=max(1,(total+49)//50);page=min(page,pages)
        if data:data['creators']=data['creators'][(page-1)*50:page*50]
        return templates.TemplateResponse(request=request,name='takeout.html',context={'data':data,'profile':profile,'page':page,'pages':pages,'total':total})

    @app.get('/watch',response_class=HTMLResponse)
    def watch(request: Request,view:str='watch',category:str='',query:str='',page:int=1,notice:str=''):
        data=dashboard.page(live_state,takeout_root,view,category,query,page)
        notices={'choice':'Choice saved locally. No YouTube request.','undo':'Previous choice restored.',
                 'built':'Shortlist built from your local cache. No YouTube refresh.',
                 'options':'Options saved. Your shortlist order is unchanged.',
                 'refresh':'Manual refresh finished. Build again when you want a new shortlist.'}
        return templates.TemplateResponse(request=request,name='dashboard.html',context={**data,'csrf':token,'notice':notices.get(notice,'')})

    def watch_return(f,notice):
        view=f.get('view','watch')
        if view not in ('watch','catchup','saved'):raise ValueError('Unknown view.')
        return '/watch?'+urlencode(dict(view=view,category=f.get('filter_category','')[:60],query=f.get('query','')[:120],page=max(1,min(10000,int(f.get('page','1')))),notice=notice))

    @app.post('/watch/build')
    async def watch_build(request: Request):
        f=await form(request)
        options=dict(profile=f.get('profile','lee'),category=f.get('category',''),use_history=f.get('use_history')=='1',exclude_history=f.get('exclude_history')=='1')
        await run_in_threadpool(dashboard.build_plan,live_state,takeout_root,options)
        return RedirectResponse('/watch?notice=built',status_code=303)

    @app.post('/watch/options')
    async def watch_options(request: Request):
        f=await form(request);_,_,_,cats=shortlist.context(live_state)
        shortlist.options_save(live_state,takeout_root,f.get('profile','lee'),f.get('category',''),f.get('use_history')=='1',f.get('exclude_history')=='1',cats)
        return RedirectResponse('/watch?notice=options',status_code=303)

    @app.post('/watch/action')
    async def watch_action(request: Request):
        f=await form(request);target=watch_return(f,'choice')
        dashboard.video_action(live_state,f.get('video',''),f.get('action',''))
        return RedirectResponse(target,status_code=303)

    @app.post('/watch/undo')
    async def watch_undo(request: Request):
        f=await form(request);target=watch_return(f,'undo')
        dashboard.undo(live_state,f.get('undo_token',''))
        return RedirectResponse(target,status_code=303)

    @app.post('/watch/refresh')
    async def watch_refresh(request: Request):
        f=await form(request)
        try:await run_in_threadpool(live.refresh,live_state)
        except live.LiveError as exc:
            data=dashboard.page(live_state,takeout_root)
            return templates.TemplateResponse(request=request,name='dashboard.html',context={**data,'csrf':token,'notice':str(exc)})
        return RedirectResponse('/watch?notice=refresh',status_code=303)

    @app.get('/preview',response_class=HTMLResponse)
    def design_preview(request: Request):
        return templates.TemplateResponse(request=request,name='prototype.html',context={
            'videos':prototype.VIDEOS,'categories':list(dict.fromkeys(v['category'] for v in prototype.VIDEOS))})

    @app.get('/shortlist',response_class=HTMLResponse)
    def shortlist_page(request: Request,saved:bool=False):
        _,_,_,categories=shortlist.context(live_state)
        options,notice=shortlist.options_load(live_state,categories)
        if saved:notice='Options saved locally. Nothing generated or refreshed. '+notice
        return templates.TemplateResponse(request=request,name='shortlist.html',context=dict(
            csrf=token,categories=categories,result=None,notice=notice,**options))

    @app.post('/shortlist/options')
    async def shortlist_options(request: Request):
        f=await form(request)
        _,_,_,categories=shortlist.context(live_state)
        shortlist.options_save(live_state,takeout_root,f.get('profile','lee'),f.get('category',''),
                               f.get('use_history')=='1',f.get('exclude_history')=='1',categories)
        return RedirectResponse('/shortlist?saved=true',status_code=303)

    @app.post('/shortlist/build',response_class=HTMLResponse)
    async def shortlist_build(request: Request):
        f=await form(request)
        profile=f.get('profile','lee');category=f.get('category','')
        use_history=f.get('use_history')=='1';exclude_history=f.get('exclude_history')=='1'
        result=await run_in_threadpool(shortlist.build,live_state,takeout_root,profile,category,use_history,exclude_history)
        shortlist.options_save(live_state,takeout_root,profile,category,use_history,exclude_history,result['categories'])
        return templates.TemplateResponse(request=request,name='shortlist.html',context=dict(
            csrf=token,notice='Options remembered for next time.',categories=result['categories'],result=result,profile=profile,category=category,
            use_history=use_history,exclude_history=exclude_history))

    @app.get('/subscriptions',response_class=HTMLResponse)
    def subscription_manager(request: Request,profile:str='lee',query:str='',show:str='all',page:int=1,notice:str=''):
        if show not in ('all','tracked','untracked') or len(query)>120:raise ValueError('Invalid filter.')
        rows,status=subscriptions.catalogue(live_state,profile,takeout_root)
        rows=[r for r in rows if query.casefold() in r['name'].casefold() and (show=='all' or r['tracked']==(show=='tracked'))]
        total=len(rows);pages=max(1,(total+24)//25);page=max(1,min(page,pages))
        base='/subscriptions?'+urlencode(dict(profile=profile,query=query,show=show))
        return templates.TemplateResponse(request=request,name='subscriptions.html',context=dict(
            rows=rows[(page-1)*25:page*25],status=status,profile=profile,query=query,show=show,page=page,pages=pages,total=total,base=base,
            csrf=token,plan=None,notice='Tracking saved locally. Refresh manually when ready.' if notice=='saved' else ''))

    @app.post('/subscriptions/preview',response_class=HTMLResponse)
    async def subscription_preview(request: Request):
        f=await form(request)
        plan=subscriptions.preview(live_state,f.get('profile',''),takeout_root,f.get('key',''),f.get('action',''))
        signature=hmac.new(token.encode(),plan['revision'].encode(),'sha256').hexdigest()
        return templates.TemplateResponse(request=request,name='subscriptions.html',context=dict(plan=plan,signature=signature,csrf=token,profile=plan['profile']))

    @app.post('/subscriptions/apply')
    async def subscription_apply(request: Request):
        f=await form(request)
        expected=hmac.new(token.encode(),f.get('revision','').encode(),'sha256').hexdigest()
        if not secrets.compare_digest(expected,f.get('signature','')):raise ValueError('Preview this change before applying it.')
        await run_in_threadpool(subscriptions.apply,live_state,f.get('profile',''),takeout_root,f.get('key',''),f.get('action',''),f.get('revision',''))
        return RedirectResponse('/subscriptions?'+urlencode(dict(profile=f['profile'],notice='saved')),status_code=303)

    @app.post('/demo')
    async def demo(request: Request):
        await form(request)
        load_demo(db_path)
        return RedirectResponse('/',status_code=303)

    @app.post('/filters')
    async def filters(request: Request):
        fields = await form(request)
        values = {k:fields.get(k,'') for k in ('category','start','end','state')}
        if fields.get('reset'):
            values = dict.fromkeys(values,'')
        for key in ('start','end'):
            if values[key]:
                values[key] = date.fromisoformat(values[key]).isoformat()
        if values['start'] and values['end'] and values['start'] > values['end']:
            raise ValueError('The start date must be before the end date.')
        if values['category'] not in ['',*CATEGORIES] or values['state'] not in ['',*STATES]:
            raise ValueError('Unsupported filter')
        with connect(db_path) as db:
            db.executemany('INSERT INTO preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',values.items())
        return RedirectResponse('/',status_code=303)

    @app.post('/annotation')
    async def annotation(request: Request):
        values = await form(request)
        if values.get('state') not in STATES:
            raise ValueError('Unsupported review state')
        with connect(db_path) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=?',(values.get('video'),)).fetchone():
                raise ValueError('Unknown video')
            db.execute('INSERT INTO annotations VALUES(?,?) ON CONFLICT(video_id) DO UPDATE SET state=excluded.state',(values['video'],values['state']))
        return RedirectResponse('/',status_code=303)

    @app.post('/category')
    async def category(request: Request):
        values = await form(request)
        if values.get('category') not in CATEGORIES:
            raise ValueError('Unsupported category')
        with connect(db_path) as db:
            db.execute('UPDATE channels SET category=? WHERE id=?',(values['category'],values.get('channel')))
        return RedirectResponse('/',status_code=303)

    app.mount('/static',StaticFiles(directory=Path(__file__).parent/'web'/'static'),name='static')
    return app
