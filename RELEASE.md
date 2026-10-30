# Release notes

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

Build releases only from this clean public repository. Review staged files for secrets/personal data, run tests, and keep runtime files ignored. Do not copy an entire private development folder into a release. Use synthetic examples for screenshots and issue reports. Review current YouTube policies and quota documentation before changing collection behaviour. MIT covers this project's code; upstream services and dependencies retain their own terms.
