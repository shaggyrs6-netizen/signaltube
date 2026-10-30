# Changelog

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
