# Release notes

## v0.6.0-beta.1 — 1 November 2026

### Thumbnails and easier setup

- Optional real YouTube video thumbnails and channel avatars, with local artwork as the default and fallback.
- Demo-first onboarding; direct channel URL/@handle lookup with identity confirmation and quota preview.
- Clear unavailable Saved entries, removable with Undo; no promise of permanent titles or playback links after metadata expiry.
- Persistent Manage library navigation, larger labels, optional scoring details and clearer refresh coverage/cooldown.
- A separate manual Build my five action after refresh; no automatic collection or shortlist generation.
- Corrected desktop/browser setup directions and a short explanation of optional-image privacy.

### Install or upgrade

Download **signaltube-desktop-0.6.0-beta.1-linux.tar.gz** and **SHA256SUMS**. Verify the archive, extract it, then follow [desktop installation](DESKTOP-PACKAGING.md). The wheel and source archive are also supplied. Each user provides their own Google API key.

Existing users: quit SignalTube before upgrading, preserve the same data directory and quota ledger, and follow the documented upgrade procedure. Do not create a fresh ledger to gain allowance. There is no automatic updater.

### Validation

105 synthetic tests passed locally and from a clean package, including real synthetic process restarts. The beta was installed with an existing library and its pre-existing database tables, credentials, tracking and quota history were verified unchanged.

One explicitly authorised live refresh covered 13 channels, found 93 new records, left 854 distinct cached videos and no duplicates, and consumed exactly 13 units. All 93 newly found records had publication times after their channel's initial baseline. Five real thumbnails loaded successfully; image loading left quota unchanged. These are local-ledger observations, not a new Google Console audit.

### Known limits

Channel-avatar rendering passed synthetic tests but still awaits live verification. Existing channel caches may lack avatar URLs until a later explicit lookup. Optional images contact Google image servers and use bandwidth, though not Data API quota. Local artwork remains available. Metadata expires after 30 days; a recent-upload refresh may not recover old Saved entries. Wider Linux installation, native zoom and accessibility testing remain feedback areas.

Manual refreshes, the hard **100-unit daily application cap**, Omarchy themes and local personal data remain unchanged. No model, background polling, automatic saved-item refresh or duration filter.

See [acceptance evidence](BETA-ACCEPTANCE.md) and [tester checklist](TESTING.md). This is a prerelease for testing, not a stable release or compatibility/compliance certification.

## v0.5.0-beta.1 — 30 October 2026

Desktop beta: own window, tray, app-menu installer, optional login startup and built-in Google API setup/costs guide. Download `signaltube-desktop-0.5.0-beta.1-linux.tar.gz` and read [desktop installation](DESKTOP-PACKAGING.md), [changelog](CHANGELOG.md) and [tester checklist](TESTING.md). Existing users should reuse their data folder; no automatic migration or updater is included. This is a prerelease for feedback, not a universal Linux compatibility claim.

## v0.4.0-beta.1 — 29 October 2026

First public test release under MIT.

- Local Watch next, Catch up and Saved views, following Omarchy colours.
- Explainable manual shortlist with retained references, profile/category/history options and no automatic rebuild.
- Save, Watched, Dismiss and one-step Undo, including state restoration across actual server restarts.
- Explicit subscription tracking with a quota-cost preview.
- Your own restricted Google API key, manual collection, persistent 100-unit daily cap and cooldown.
- Optional local Takeout CSV/JSON preview/confirm import, separate from the synthetic demo.
- No-key visual preview and synthetic fixtures.
- 72 tests passing in the validated Linux environment.

### Before testing

Read README.md and TESTING.md. This is a terminal-launched local browser app: **no app-menu icon, desktop installer, login autostart or automatic updater**. Each tester supplies their own Google project/key and optional data. Nothing from the original developer's private runtime is included.

### Known limits

Up to 50 recent uploads per tracked creator per refresh, with 30-day API metadata retention. No remote thumbnails, automatic watch detection, cloud/local model, scheduled refresh or full notification archive. Genuine new-upload observation after a baseline remains a field check; simulated detection and successful live refresh/deduplication checks are separate evidence. The existing Starlette/httpx deprecation warning is non-failing.

### Maintainers

Build releases only from this clean public repository. Review staged files for secrets/personal data, run tests, and keep runtime files ignored. Do not copy an entire private development folder into a release. Use synthetic examples for screenshots and issue reports unless the owner explicitly approves a specific app screenshot for publication; review that capture for private data first. Review current YouTube policies and quota documentation before changing collection behaviour. MIT covers this project's code; upstream services and dependencies retain their own terms.
