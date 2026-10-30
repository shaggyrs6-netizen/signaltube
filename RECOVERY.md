# Local data and recovery

For the desktop edition, Quit from the tray before backup or removal. Follow [desktop installation/removal](DESKTOP-PACKAGING.md). The stores below are relative to its data folder (`~/.local/share/signaltube` by default, or the explicitly chosen folder). In the source/browser edition they are under `var/`.

The following `run.sh` commands apply to the source/browser edition, from its extracted/cloned folder.

- `./run.sh` starts/reuses the loopback server and opens a private unlock link. Re-run it if the page is locked. `./run.sh launch --no-open` prints the link for a different browser.
- `./run.sh status` checks the matching server; `./run.sh stop` stops it. Closing a browser does not stop collection because there is no automatic collection in the first place. The on-demand server remains available until stopped or the computer shuts down.
- Check `var/server.log` locally for startup errors. Logs can include the private launch URL; do not upload them unredacted. Foreground `./run.sh serve` stops with Ctrl+C.
- Never bind to a public interface or expose the local server through a tunnel. It is a single-user desktop app, not a hosted service.

## Your stores

| Path | Contents |
|---|---|
| `var/signaltube.sqlite3` | Fictional demo import |
| `var/live.sqlite3` | Expiring API metadata, persistent quota ledger and cooldown |
| `var/personal.sqlite3` | Review/saved/category choices, shortlist options, selected fingerprints and one-step Undo |
| `var/takeout/<profile>.sqlite3` | Private user-selected history/subscriptions |
| `var/tracked-channels.json` | Explicit tracking allowlist, if configured |
| `var/secrets/youtube.key` | Your private Google API key |
| `var/session.token` | Private local dashboard login credential |

Stop the app before making a deliberate private backup of personal/import stores and tracking configuration. Do not upload the runtime directory or treat a backup as a reset mechanism. Do not retain expired API metadata through old cache backups. Never restore an old live ledger to gain quota. Personal/import databases and old copies may contain private viewing data; encrypted storage/backups are your responsibility.

Removing a creator from tracking hides its cached videos but retains local choices. Expired cache details disappear while saved fingerprints remain. Undo restores the previous local choice; it never restores expired API metadata or changes your YouTube account. A later action on that video invalidates stale Undo.

For the source/browser edition only: to uninstall, stop the app, decide which personal files to retain privately, then remove the chosen project folder yourself. That source/browser path does not install desktop configuration. The desktop installer has a separate receipt-based uninstall command. Removing local files does not change your Google project, key or actual YouTube account.
