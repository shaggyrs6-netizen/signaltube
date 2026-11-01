# 0.6.0-beta.1 candidate acceptance — 1 November 2026

Status: local, unpublished candidate on `codex/first-use-beta`. The installed desktop app and private working library were not upgraded or refreshed. No real Google API key, Takeout data, or user cache was used for this work.

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
- Wheel and source archives built with `uv build --offline --out-dir dist/0.6.0-beta.1`. Clean extraction and fresh offline environment: **105 passed**, same non-failing warning. Archive inventories excluded runtime folders, databases, key files and logs. The candidate desktop bundle and SHA256SUMS are in that directory; reproduce with `python scripts/package_release.py --dist-dir dist/0.6.0-beta.1`. No publication, installer replacement, live refresh or model activation is part of this candidate.

## Saved-item refresh investigation

The official `videos.list` endpoint supports retrieving a known video's current metadata at a cost of one unit per request: https://developers.google.com/youtube/data/reference/rest/v3/videos/list . The current personal database deliberately stores matching fingerprints rather than recoverable API video IDs. Once metadata expires, the app cannot turn those fingerprints back into an ID. This beta therefore provides honest unavailable states, not a hidden lookup or retention bypass. A later explicit bookmark/refresh design needs a clear source/retention model and its own budget preview before implementation. Metadata retention remains governed by https://developers.google.com/youtube/terms/developer-policies . This is an implementation boundary, not a compliance certification.

## Remaining release checks

- Review the candidate with Lee before any public push/release or replacement of his installed copy.
- Optional real API/avatar/CDN validation requires a separately authorised manual operation; synthetic success is not a live pass.
- Wider clean-machine Linux installation, native browser/desktop zoom and external tester accessibility feedback remain outstanding.
- Models, duration filters, automatic collection, automatic shortlist regeneration and automatic saved-item refresh stay deferred.
