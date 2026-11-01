# SignalTube

> **Next candidate: v0.6.0-beta.1 (not yet published).** First-use improvements, direct channel setup and optional images. The current published desktop release is **v0.5.0-beta.1**. Own window, tray icon, app-menu installer and built-in Google API setup guide. [Download the desktop bundle](https://github.com/shaggyrs6-netizen/signaltube/releases/tag/v0.5.0-beta.1) · [Installation and existing-library instructions](DESKTOP-PACKAGING.md).

![SignalTube — Less looking. More watching.](assets/signaltube-cover.png)

**Public beta · Linux / Omarchy · MIT licence · Bring your own Google API key**

YouTube’s notification bell tells you something arrived. It does not make it easy to catch up once you fall behind. SignalTube gives those uploads a calmer place to wait: an explainable next-watch list, a catch-up queue and a separate place for things you deliberately save.

A calmer, local-first YouTube organiser for Linux, with Omarchy theme support.

**Watch next** keeps a manually built, explainable shortlist. **Catch up** shows cached uploads you have not reviewed in SignalTube. **Saved** is your deliberate queue. Save, Watched, Dismiss and one-step Undo are local choices, not changes to your YouTube account.

No cloud AI, embedded player, analytics, automatic watch tracking or background YouTube polling. Video links open YouTube in your browser. Local artwork is the default; you can opt into channel avatars or video thumbnails under Images. Local-model integration is deferred.

## Choose your setup

| Option | Google key? | What you get |
|---|---|---|
| Try the design and fictional demo | No | Interactive `/preview` and the original synthetic import dashboard at `/` |
| Use public channel uploads | Your own key | Manual collection, Watch next, Catch up, Saved and creator organisation |
| Add your Takeout history | Optional for import; needed for live uploads | Local history counts for ranking and an imported subscription list to choose from |

See [the small-group tester guide](TESTING.md) for the short installation and feedback checklist. The desktop bundle installs an app-menu entry. The source/browser edition remains available through `run.sh`.

## Recommended: desktop installation

Follow [the desktop installation guide](DESKTOP-PACKAGING.md) for an app-menu entry, its own window and a tray icon. Start with **Try the demo**, then **Set up my channels** when ready. The source/browser route below is optional.

## Alternative: source/browser installation

Supported target: Linux (tested on Omarchy), Python 3.12 or newer. The launcher and file locks use Unix facilities; Windows is not currently supported. Omarchy is optional: another Linux desktop gets a readable fallback palette. You need `uv` installed through its official instructions at https://docs.astral.sh/uv/getting-started/installation/ or your distribution. Installing Python dependencies requires an Internet connection; using already-cached data does not.

Download the [latest public beta](https://github.com/shaggyrs6-netizen/signaltube/releases), or clone this repository:

```bash
git clone https://github.com/shaggyrs6-netizen/signaltube.git
cd signaltube
```

Then install the locked dependencies and launch:

```bash
uv sync --frozen
./run.sh
```

If the executable bit was lost during extraction, use `bash run.sh` or `chmod +x run.sh`.

The launcher starts or reuses a server on **127.0.0.1:8765**, opens a private login link in your default browser, and prints that link for use in another browser. The launch link lands on Watch next. Keep it private. The server keeps running when you close the terminal; it does not start at login.

```bash
./run.sh status
./run.sh stop
./run.sh launch --no-open  # print the private link instead of opening a browser
```

If locked, run `./run.sh` again and open its link. A normal direct URL is not an unlock link. `./run.sh serve` runs in the foreground instead (Ctrl+C stops it). For a busy port, use `./run.sh launch --port 8766` and the same port for status/stop. Never kill an unknown process to reclaim a port. Keep one production copy so the local quota ledger is not split across checkouts.

## Option A: no-key demo

```bash
./run.sh demo
./run.sh
```

Visit `/preview` for the fictional visual demo, or `/` for the imported synthetic records. Demo actions do not edit your real choices. The real `/watch` page will have no uploads until you explicitly refresh with your own key. There is no paid account requirement for the demo.

## Option B: public uploads

Follow [Google API setup and quota](API-SETUP.md). Every user supplies their own key and Google project; no shared developer key is bundled.

```bash
./run.sh key-add
```

Paste the key into the hidden local terminal prompt. Never put it in a command argument, screenshot, issue or Git commit. Then open `/watch` and explicitly choose **Refresh from YouTube**. Saving the key or starting the app does not refresh.

A fresh installation starts with three public example channels: Mentour Pilot, Learn Linux TV and Two Minute Papers. In **Manage library → Channels & quota**, paste a YouTube @handle or `/channel/UC…` URL, choose **Look up channel** (1 quota unit), confirm the returned channel and review the next-refresh estimate before applying. Lookup does not collect videos. You may remove all example channels. Takeout is optional for bulk selection. Tracking changes have a quota preview and explicit Apply; they never automatically track an entire Takeout export.

Build Watch next using **Build my five**. Its selected references survive navigation/restart. Opening it does not build a replacement list. Save options only remembers profile, category and history options without building. Dismissed/watched/untracked/expired references are omitted; use Build again to choose new ones. Order stays fixed until that action; displayed reasons reflect current preferences and cache.

Catch up means **unreviewed in SignalTube**, not necessarily unseen on YouTube. A saved video can remain unreviewed; Watched/Dismiss clears it from Catch up. Saved status is independent, so a watched saved video may stay in Saved until unsaved. Undo restores the immediately previous dashboard choice, even after restart. A newer dashboard action replaces the one-step Undo; editing the same video elsewhere invalidates it rather than overwriting a later change.

## Option C: import your history

Request a Google Takeout YouTube export with subscriptions and history in CSV/JSON. Extract only the files you choose locally. ZIP and HTML input are not accepted by this importer.

```bash
./run.sh takeout-preview --profile local \
  --subscriptions '/absolute/path/subscriptions.csv' \
  --history '/absolute/path/watch-history.json'
```

Review the counts/errors and copy the reported `preview_id`. Then rerun with the same paths and profile:

```bash
./run.sh takeout-import --profile local \
  --subscriptions '/absolute/path/subscriptions.csv' \
  --history '/absolute/path/watch-history.json' \
  --confirm 'PASTE_THE_PREVIEW_ID_HERE'
```

Imports are additive and duplicate-safe. The original files are unchanged. Preview/Import use no YouTube quota and never enable tracking automatically. A single imported profile is selected automatically for a new workspace; existing saved profile choices are retained. With multiple imports, choose the intended profile. History controls appear only when a real import exists. The importer currently recognises English `Watched` activity records; other languages/export variants need validation. Event counts are not completion or watch duration.

## Images and Saved

Under **Images**, choose local artwork only (default), channel avatars with local artwork, or avatars with video thumbnails. URLs are retained from normal API responses; displaying an image uses bandwidth but no API quota. Images load only when visible, through a restricted local endpoint, with no key, cookies or imported history sent to the image server. Google still receives your IP address and the requested image URL. A maximum of 64 images, each at most 512 KiB, is cached for up to one day and never beyond the metadata expiry. Missing/failed images fall back to local artwork. Existing cached channels without avatar URLs can be looked up manually later (1 unit); normal refreshes do not add hidden avatar requests.

Saved choices persist separately from expiring API metadata. **Unavailable saved item** entries remain visible with an option to remove the choice and Undo. They cannot show a title or playback link after expiry, and a recent-uploads refresh may not recover older items. This beta does not promise permanent video bookmarks or independently refresh saved videos; see the acceptance notes for the design boundary.

## Limits and privacy

- Hard **100-unit daily local cap**, even if Google gives the project a larger allowance. Reserve the whole batch before requests; failures retain their reservations. A 15-minute cooldown applies. No automatic retries or schedules.
- Up to 50 recent uploads per tracked creator per refresh. This is not a full notification archive. API metadata expires after 30 days and is purged when the app runs; personal choices remain, but expired details cannot be displayed until legitimately fetched again.
- Omarchy colours follow the active palette through a local stylesheet check. SignalTube never edits desktop theme files. No shell plugin is required.
- Private runtime files live under the desktop data directory (normally `~/.local/share/signaltube`) or the source edition’s `var/`, including Takeout data, API key and local session credential. Do not share that folder, launch URLs, logs or database files. Owner-only permissions are not encryption or isolation from other processes under your account.
- See the in-app `/privacy` page and [recovery guidance](RECOVERY.md).

## Development

```bash
uv sync --frozen
uv run --frozen pytest -q
```

Tests use synthetic fixtures and fake API transports, not a real Google key. No automatic live-API test runs. Contributions and bug reports are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Security issues belong in [private vulnerability reports](SECURITY.md).


## Status and limitations

This is an early beta for a small group of testers. The desktop edition includes a per-user installer, app-menu entry and tray icon; the browser edition uses `run.sh`. There is no automatic updater. Start with the demo before setting up an API key.

The synthetic suite includes actual server stop/restart checks for Save, Watched, Dismiss and Undo, plus quota, onboarding, channel lookup and optional-image checks. See [candidate acceptance](BETA-ACCEPTANCE.md) for dated results. Candidate testing does not perform live collection. This is not a Google compliance certification or a complete accessibility audit. Please report what happens on your own setup.

## Licence and credits

Released under the [MIT licence](LICENSE). SignalTube is independent and is not affiliated with or endorsed by YouTube, Google or Omarchy. YouTube playback and data access remain subject to their respective terms. The cover graphic was generated for this project; category illustrations are local SVG artwork. No external fonts or analytics are loaded. Optional YouTube images are fetched only after opting in; local artwork remains available.
