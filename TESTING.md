# SignalTube desktop beta — tester guide

Test plan for **v0.6.0-beta.1**, currently an unpublished local candidate. The desktop edition includes its own window, tray and installer. The original browser edition remains available.

## Get started

Follow [desktop installation](DESKTOP-PACKAGING.md). Download the named desktop bundle from Releases, extract it and run the installer. Dependencies require internet; starting the app makes no YouTube API request. Existing 0.4 testers should use the guide's **existing data folder** instructions to preserve their library and quota history.

Open SignalTube from the app menu. For live uploads, use **Google API setup and costs** in the tray or sidebar. Create your own key; never send it to us. A fresh install starts with three public example channels. Click Refresh only when ready, then Build my five.

## First-use and reliability checks

- Start with no key or uploads. Try the fictional demo; return to Watch next and follow setup → channels → refresh → build. History controls should stay hidden until an import exists.
- Paste a channel @handle/URL in Channels & quota. Lookup must be explicit and cost one unit, with a confirmation page before tracking. Cancel must leave tracking unchanged. Invalid/video links must be rejected before an API call.
- A manual refresh must show progress, then updated-channel coverage and cooldown. Rebuilding is a separate manual action.
- At a narrow window and 200% browser zoom, use the keyboard to open Manage library and reach channels, setup, categories and the full library.
- Switch between local artwork, avatars and thumbnails. Local artwork must make no image request. Images missing offline should leave artwork visible. The choice must survive reopening; image downloads must not consume API quota.
- Use synthetic expired metadata to check unavailable Saved entries remain visible. Remove one, then Undo. Do not age or delete your real library to test this.

## Short test checklist

- App-menu launch opens one window and registers a tray icon.
- Close the window, then reopen it through the tray. Launching from the menu again should restore it, not create another copy.
- Open the Google setup guide. Its Google links should open in your normal browser.
- Save a video and check Saved. Mark it Watched: it should leave Catch up but remain Saved. Undo should restore the previous state.
- Build my five, quit through the tray, then reopen. Choices and shortlist references should remain. No automatic refresh or replacement shortlist should run.
- Open a video: YouTube should open in your browser. Opening it does not automatically mark it watched.
- Check long titles, keyboard navigation, small windows and light/dark Omarchy themes.
- If you explicitly enabled login startup, test after signing out and back in. It should start in the tray when available, with no YouTube refresh.
- Quit before uninstalling. Removal should preserve your data, and reinstalling with the same data folder should find it again.

## No-key testing

You can inspect the empty library and built-in guide without a key. The source/browser edition also provides the fictional `/preview` and synthetic demo described in README.md. Do not confuse synthetic interactions with live quota or data.

## Feedback

Use the repository's Issues tab. Include version **0.6.0-beta.1**, Linux/Omarchy version, desktop/bar, install method, steps, expected result and actual result. Mention whether this is a new library or an existing 0.4 library. Redact screenshots. Do not share keys, private launch URLs, databases, Takeout files, raw logs or viewing history. See SECURITY.md for sensitive reports.

## Known limits

This beta is tested on one Omarchy workstation, not every Linux distribution. Real login-startup, clean-machine installation and external-browser handoff need wider tester coverage. Qt may print graphics-fallback or desktop-portal warnings; record the visible symptom rather than assuming every warning is a crash. Installation requires internet and a substantial Qt download. No automatic updater or native OS package is included.

Collection remains bounded to 50 recent uploads per tracked creator per refresh, with 30-day metadata retention. Catch up means unreviewed in SignalTube, not necessarily unwatched on YouTube. Remote avatars and thumbnails are opt-in; local artwork is the default. No automatic watch detection, models or background polling. The 100-unit app cap is independent of Google's default allowance. Other software using the same Google project is outside SignalTube's ledger.
