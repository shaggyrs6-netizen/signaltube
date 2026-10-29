# Small-group tester guide

This candidate is a local browser application for Linux/Omarchy, not an installed desktop package. It does **not** currently add an app-menu entry, desktop shortcut, login startup or automatic updater. You launch it with `./run.sh` from its folder; it opens your default browser. A menu entry could be added in a later packaging step.

## Install once

1. Extract the supplied source ZIP into a permanent folder that belongs to you. Do not copy another person's `var/` folder or credentials.
2. Have Python 3.12+ and `uv` available. Follow the linked official `uv` instructions in README if needed.
3. Open a terminal in the extracted `signaltube` folder and run:

```bash
uv sync --frozen
bash run.sh
```

`bash run.sh` works even if ZIP extraction did not preserve executable permissions. For the shorter `./run.sh` commands in the other guides, first run `chmod +x run.sh` if needed. Dependency installation needs Internet; no YouTube request occurs simply by installing or launching.

For later launches, run `bash run.sh` from the same folder. Stop with `bash run.sh stop`. The browser opens Watch next through a private local login link. If locked, launch again; do not share that link. The server keeps running when the terminal closes but does not start automatically after reboot.

## Start without a Google key

Visit `/preview` for the fictional design demo. Try switching views, topic/search filters, sample Save/Watched/Dismiss and Undo. Refreshing this preview resets its tab-only demo choices. This is different from the persistent real queue at `/watch`.

For the original synthetic import demo, run `bash run.sh demo` and visit `/`. Do not mistake demo behaviour for a live YouTube refresh.

## Optional real-data test

Follow API-SETUP.md to create **your own** restricted key and a dedicated Google project. Use `bash run.sh key-add`; never send the key to the developer. A fresh install tracks only the three public example channels. Explicitly refresh once, inspect the preview/ledger and then build Watch next. Keep the 100-unit local cap; there is no automatic refresh.

For history/subscriptions use your own extracted Takeout CSV/JSON and the preview/confirm commands in README. Choose the matching profile in the UI. Importing does not automatically track all subscriptions. Do not send the export or databases back with feedback.

## What to try in the connected app

- Save a cached video. It should appear in Saved without clearing Catch up.
- Mark it Watched. It should disappear from Watch next/Catch up but remain Saved.
- Undo the Watched action. The previous state should return, including Saved.
- Dismiss another item, stop the app, relaunch and use Undo. No automatic rebuild or refresh should happen.
- Build a shortlist, navigate away and restart. It should retain its references and build time. Expired/handled items may be absent; no replacements are generated until you choose Build.
- Check category/search filters, long titles, keyboard navigation and readability with your own Omarchy theme. Opening YouTube does not automatically mark a video watched.

## Useful feedback

Record the source ZIP filename, Omarchy version, browser, theme, steps, expected result and actual result. A redacted screenshot can help. Mention whether the shortlist feels useful, repetitive or hard to act on. Do not include API keys, login links, console project identifiers, raw logs, Takeout exports, databases or private viewing details.

Known limits: 50 recent uploads per tracked creator per refresh; 30-day API metadata retention; Catch up means unreviewed in SignalTube, not a complete YouTube notification history. No thumbnails/video-duration fetch, automatic watch detection, model, cloud service or background polling. Genuine new-upload detection remains an outstanding live observation; synthetic detection is tested.

This is a test candidate. This beta is published under MIT. Report ordinary bugs through the repository Issues tab; follow SECURITY.md for sensitive reports.
