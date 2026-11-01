# Changelog

## 0.6.0-beta.1 — local candidate, 1 November 2026

- Demo-first onboarding with accurate setup steps and neutral profile defaults; existing preferences retained.
- Direct channel URL/@handle lookup, identity confirmation and quota preview, using the shared 100-unit ledger. No automatic tracking or refresh.
- Persistent Manage library navigation, larger labels and responsive layouts; scoring details are optional.
- Explicit unavailable Saved entries with remove/Undo, without retaining expired API titles or links.
- At-a-glance recent channel coverage, disabled cooldown refresh and submission progress.
- Optional channel avatars/video thumbnails through a bounded local image cache; local artwork remains the default and fallback.
- Corrected desktop/browser installation guidance and privacy explanation.

No model, background collection, duration filter or automatic saved-video refresh. Not published or installed over an existing user copy.


## 0.5.0-beta.1 — 30 October 2026

### Added

- Linux desktop window powered by Qt, with a tray icon and app-menu installer.
- Close-to-tray, Open, running status and Quit controls; second launch restores the existing window. Without a tray host, closing quits.
- Optional explicit startup at login; disabled by default.
- Built-in Google API setup and costs guide, first-use link and tray shortcut.
- Masked API-key entry through the tray; saving never calls YouTube or silently replaces an existing key.
- Installable Python wheel with bundled web resources and demo fixtures.
- Per-user install/removal, retained personal data and explicit existing-data-folder selection.

### Fixed

- Embedded-browser validation of profile names containing hyphens.
- Web-page/profile destruction order during desktop shutdown.
- Installer selecting an unsupported Python version.
- Data paths for installed packages and desktop/source privacy documentation.

### Unchanged

Manual refreshes and shortlist generation, local-only personal data, persistent 100-unit daily application cap, explicit choices, 30-day API metadata retention and external YouTube playback. No automatic updater, AI service or background polling.

### Validation and limits

Automated tests and local Omarchy window/tray checks; owner also tested with an existing live library. Cross-distribution installation and real login startup remain beta feedback areas. This release is not a native Arch package, Flatpak or AppImage. See TESTING.md and DESKTOP-PACKAGING.md.

## 0.4.0-beta.1 — 29 October 2026

First public browser-edition beta: local Watch next, Catch up and Saved; explainable shortlists; persistent review choices and Undo; explicit channel tracking; own Google key and quota guard; optional Takeout import; synthetic demo; MIT licence. See RELEASE.md for the original release notes.
