# 0.6.0-beta.1 acceptance — 1 November 2026

The original candidate was built and tested using synthetic data only. Subsequent installation and explicitly authorised live testing on 1 November are recorded below. Source and release assets remain separate from the owner’s private runtime.

## Delivered

- Demo-first entry with an explicit route back to the real library. Empty states follow key → channels → manual refresh → manual build. No irrelevant history controls before import.
- Neutral `local` defaults; existing saved profile names/options retained. One imported profile is selected for a new workspace; multiple or missing selections expose a picker.
- Add a channel by supported URL/@handle. One explicit lookup reserves one unit in the existing ledger under the existing cross-process refresh lock. The returned identity, external channel link and next-refresh budget are confirmed before tracking. Cancel has no tracking effect. Failed/interrupted requests retain reservations. No automatic pagination, search or video collection. All example channels may be removed.
- Three primary views with a persistent Manage library menu; management pages share the navigation. Larger labels and visible keyboard focus; score arithmetic is under an optional disclosure.
- Saved entries whose metadata has expired remain explicitly visible, with removal and persistent one-step Undo. No expired title, link or image is retained as a personal preference.
- Visible updated-channel coverage over the last 24 hours, remaining cooldown and disabled refresh control. Explicit submissions show progress. Building remains a separate action and uses no API quota.
- Local artwork by default. Optional avatars or avatars plus video thumbnails. Allowlisted API-provided HTTPS image URLs only; no arbitrary proxy, redirects, cookies, key or history sent to image servers. The desktop's local-only browser guard and CSP remain unchanged. Lazy images use a local route and a maximum 64-entry / 32 MiB payload cache; each image is at most 512 KiB, expires within one day and never outlives its source metadata. Unsupported/missing images fall back to artwork.
- Consistent desktop/browser installation directions, optional image privacy explanation, and tester checklist.

## Verification

- `uv run --offline --frozen pytest -q`: **105 passed**, one existing non-failing Starlette/httpx deprecation warning. Includes existing six real synthetic process restarts, persisted Save/Watched/Dismiss/Undo and unchanged shortlist references; new tests cover onboarding, channel validation/confirmation, shared lock/cap/failure reservation, resolved-channel initial baseline, image opt-in/cache/expiry/size/type/host restrictions, partial freshness and unavailable Saved Undo.
- Isolated loopback walkthrough on port 18766, entirely synthetic API and image transports: empty entry → channel lookup (ledger 1) → confirm tracking (still 1) → explicit refresh (2) → manual build (still 2) → optional thumbnail/avatar display (still 2). Both image elements loaded through local URLs; no external image server was contacted.
- Keyboard Enter opened Manage library; Tab reached Channels & quota. At approximately 320 CSS pixels, all management links remained available and the page did not overflow horizontally. A separate 200% CSS content-zoom check preserved access. This is not a claim of native browser-menu zoom or a full accessibility audit; those remain tester checks.
- Existing Omarchy palette was used in the walkthrough; palette safety/light-dark tests remain part of the passing suite. No desktop theme setting was changed.
- Wheel and source archives built with `uv build --offline --out-dir dist/0.6.0-beta.1`. Clean extraction and fresh offline environment: **105 passed**, same non-failing warning. Archive inventories excluded runtime folders, databases, key files and logs. The candidate desktop bundle and SHA256SUMS are in that directory; reproduce with `python scripts/package_release.py --dist-dir dist/0.6.0-beta.1`. That candidate check did not install, publish, refresh or activate a model; subsequent owner-authorised installation and live checks are recorded below.

## Saved-item refresh investigation

The official `videos.list` endpoint supports retrieving a known video's current metadata at a cost of one unit per request: https://developers.google.com/youtube/data/reference/rest/v3/videos/list . The current personal database deliberately stores matching fingerprints rather than recoverable API video IDs. Once metadata expires, the app cannot turn those fingerprints back into an ID. This beta therefore provides honest unavailable states, not a hidden lookup or retention bypass. A later explicit bookmark/refresh design needs a clear source/retention model and its own budget preview before implementation. Metadata retention remains governed by https://developers.google.com/youtube/terms/developer-policies . This is an implementation boundary, not a compliance certification.

## Installed and live-tested — 1 November 2026

- Installed package 0.6.0b1 using the existing private data directory. Logical hashes of every pre-existing database table matched across the upgrade; quota history, tracking configuration, credentials and menu settings were unchanged. Dependency compatibility and authenticated local screens passed.
- Exactly one authorised refresh: all 13 channels succeeded, cache 761 → 854 unique videos, 93 newly discovered records, zero duplicates. A subsequent read-only comparison confirmed all 93 publication timestamps were later than their channel's initial baseline, demonstrating live post-baseline upload detection. Local Pacific-day usage 0 → 13/100, matching the reservation; 87 remained at that checkpoint. These are local-ledger figures, not a fresh Google Console audit.
- 650 thumbnail URLs were supplied by that refresh. Five real JPEG thumbnails loaded and decoded successfully at 320×180 (roughly 11–16 KB each); a repeated image load also passed. Quota remained 13/100. The owner confirmed the displayed result.
- Existing cached channel metadata had no avatar URLs. No extra lookup was made. Avatar rendering passed synthetic checks; live avatar verification remains pending.
- Owner-approved desktop screenshot is included at `assets/signaltube-thumbnails.png`; only the app window was captured. It includes public video titles/images and displayed queue counts, not credentials or imported history records.

## Remaining checks

- Channel avatars need a separately authorised live channel lookup; no automatic metadata backfill.
- Wider clean-machine Linux installation, native browser/desktop zoom and external tester accessibility feedback remain outstanding.
- Models, duration filters, automatic collection, automatic shortlist regeneration and automatic saved-item refresh stay deferred.
