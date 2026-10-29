import argparse
import json
import os
import secrets
import sys
import getpass
from pathlib import Path
from .storage import initialise
from .importers import import_file
from .webapp import create_app, load_demo, ROOT
from .live import store_key, refresh, LiveError
from . import takeout, launcher

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='SignalTube — local library and bounded public API trial')
    parser.add_argument('--db',type=Path,default=ROOT/'var'/'signaltube.sqlite3')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('demo',help='Import the bundled synthetic fixtures (safe to repeat)')
    sub.add_parser('key-add',help='Save an API key using a hidden local terminal prompt; no network request')
    sub.add_parser('refresh',help='Manually refresh the approved channel list within the 100-unit cap')
    for command in ('takeout-preview','takeout-import'):
        real = sub.add_parser(command,help='Preview/import explicitly selected real Takeout files locally, separate from demo')
        real.add_argument('--profile',required=True,help='A stable lowercase profile label, for example lee')
        real.add_argument('--subscriptions',type=Path,help='Explicit extracted subscriptions.csv file')
        real.add_argument('--history',type=Path,help='Explicit extracted watch-history.json file')
        if command=='takeout-import':real.add_argument('--confirm',required=True,help='Exact preview_id returned by takeout-preview')
    for command in ('launch','status','stop'):
        control=sub.add_parser(command,help='On-demand local server control; never refreshes YouTube')
        control.add_argument('--port',type=int,default=8765)
        if command=='launch':control.add_argument('--no-open',action='store_true',help='Print the private launch link without opening a browser')
    serve = sub.add_parser('serve',help='Start the dashboard on loopback only')
    serve.add_argument('--port',type=int,default=8765)
    imp = sub.add_parser('import',help='Import an explicitly selected synthetic CSV or JSON file')
    imp.add_argument('kind',choices=['subscriptions','history'])
    imp.add_argument('file',type=Path)
    imp.add_argument('--profile',default='synthetic-demo')
    args = parser.parse_args()
    try:
        if args.command.startswith('takeout-'):
            plan=takeout.prepare(args.profile,args.subscriptions,args.history)
            if args.command=='takeout-preview':
                print(json.dumps({'profile':plan['profile'],'preview_id':plan['preview_id'],'report':plan['report'],'writes':'none; preview only'},indent=2))
            else:
                print(json.dumps({'profile':plan['profile'],'report':takeout.commit(plan,args.confirm),'status':'Imported locally; demo and API quota unchanged'},indent=2))
            return
        if args.db.resolve().is_relative_to(takeout.ROOT.resolve()):
            raise ValueError('The Takeout directory is reserved for real data. Do not use --db to point demo commands at it.')
        if args.command in ('launch','status','stop'):
            launcher.manage(args.command,args.db,args.port,not getattr(args,'no_open',False))
            return
        initialise(args.db)
        if args.command == 'key-add':
            if not sys.stdin.isatty():
                raise LiveError('Run key-add in an interactive terminal; piping credentials is disabled.')
            store_key(getpass.getpass('YouTube API key (input hidden): ').strip())
            print('Key saved locally with owner-only permissions. No request sent. Reload the dashboard, then choose Refresh from YouTube.')
        elif args.command == 'refresh':
            print(refresh())
        elif args.command == 'demo':
            print(json.dumps(load_demo(args.db),indent=2))
        elif args.command == 'import':
            print(json.dumps(import_file(args.file,args.db,args.kind,args.profile),indent=2))
        else:
            import uvicorn
            if not 1024 <= args.port <= 65535:
                parser.error('Use an unprivileged port from 1024 to 65535.')
            token = launcher.session_token()
            print(f'\nSignalTube — manual public API trial + separate synthetic demo\nOpen: http://127.0.0.1:{args.port}/?token={token}\nStop: Ctrl+C\n',flush=True)
            uvicorn.run(create_app(args.db,token,args.port),host='127.0.0.1',port=args.port,access_log=False)
    except (ValueError,OSError,LiveError) as exc:
        print(f'Import/start failed: {exc}',file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
