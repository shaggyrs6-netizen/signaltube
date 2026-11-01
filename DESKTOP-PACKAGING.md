# Install the SignalTube desktop beta

**v0.6.0-beta.1 · Linux · Python 3.12+ · MIT**

This beta adds easier first use, direct channel setup and optional YouTube thumbnails. Existing libraries and quota ledgers must stay together when upgrading.

The desktop edition has its own window, an app-menu entry and a tray icon. Closing the window keeps it in the tray; **Quit SignalTube** stops its local server. If no tray host is available, closing quits instead. Opening a second copy restores the existing window. YouTube videos open in your normal browser.

Background operation does **not** mean automatic refreshes. Refresh and shortlist generation remain manual; the 100-unit daily application cap is unchanged.

## New installation

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) using its official instructions or your distribution. Have Python 3.12 or newer available.
2. From the [release page](https://github.com/shaggyrs6-netizen/signaltube/releases/tag/v0.6.0-beta.1), download **signaltube-desktop-0.6.0-beta.1-linux.tar.gz** and **SHA256SUMS**. The other source archives are for developers/browser-edition users.
3. Check the downloaded archive against its entry in SHA256SUMS, then extract it. In the extracted folder run:

```sh
python3 install.py signaltube-0.6.0b1-py3-none-any.whl
```

4. Open **SignalTube** from your app menu. No API key is required to open the empty library. Use **Google API setup and costs** in the tray, or the guide link in the app, when ready for public YouTube uploads.

No sudo is needed. Installation downloads Python dependencies, including approximately 250 MB of Qt wheels, with more space required once unpacked. This is an online per-user installer, not an offline executable, AppImage, Flatpak or Arch/AUR package. Tested on Omarchy; other Linux desktops are not yet verified. Qt needs a supported Linux graphics stack and system libraries. Do not disable its browser sandbox to work around installation errors.

Optional login startup is an explicit installation choice:

```sh
python3 install.py signaltube-0.6.0b1-py3-none-any.whl --autostart
```

Choose one install command. Login startup opens in the tray when a tray host exists; otherwise it shows the window. Login startup is off by default and has not yet been tested across a real login.

## Already using the 0.4 source/browser beta?

Keep your old source folder. Do not copy just the API key into a fresh library: the quota history and personal choices belong together.

1. Stop the old source server with `bash run.sh stop` from its folder. Quit any desktop test copy from the tray.
2. Make a private backup of your personal/import databases and tracking configuration. See [recovery](RECOVERY.md); never restore an older quota ledger to gain allowance.
3. Find the existing `var` directory. The desktop app requires it to be owner-only. Review the exact path before changing permissions:

```sh
chmod 700 /absolute/path/to/your/signaltube/var
```

4. Install with that existing folder:

```sh
python3 install.py signaltube-0.6.0b1-py3-none-any.whl --data-dir /absolute/path/to/your/signaltube/var
```

This points the menu entry at the same data; it does not move or copy it. Keep the original directory in place. Do not refresh two independent copies using the same Google project. Installed CLI commands need the same `SIGNALTUBE_DATA_DIR` environment variable when using a custom folder.

## Updating an earlier desktop candidate

Quit SignalTube first. The installer intentionally refuses to overwrite existing desktop files. From the earlier installer bundle, run `python3 install.py --uninstall`, then install this release. Personal data is retained. If you used a custom folder, supply the same `--data-dir` when reinstalling. Reapply `--autostart` only if wanted. If removal reports an edited or unrecognised file, stop and inspect it; do not blindly delete it.

There is no automatic updater. You choose when to install a later release.

## Data and removal

Default personal data: `$XDG_DATA_HOME/signaltube`, normally `~/.local/share/signaltube`. `--data-dir` changes the menu entry's location. Your key, quota ledger, library and choices remain local. API metadata still expires after 30 days. The embedded browser uses an in-memory profile; SignalTube's actual library persists in its databases.

Quit from the tray, then run this from the installer folder:

```sh
python3 install.py --uninstall
```

This removes the uv tool, owned menu/icon entries and optional login entry. It checks its receipt and refuses to remove edited/unrecognised files. It retains personal data and API credentials. Stop the app first: uninstall does not terminate it. Google account/project changes are never part of uninstall.

## Troubleshooting

- **Dependency download failed:** retry when the connection is stable. No YouTube request is made by the installer. A failed attempt may leave a uv environment; inspect `uv tool list` before retrying.
- **No tray:** closing quits instead of leaving an inaccessible hidden app. Relaunch from the app menu.
- **Data-folder permission error:** confirm it is your intended directory and owned by you, then make only that directory mode 700.
- **New install looks empty:** this is expected until you add a key and refresh, or explicitly reuse an existing data folder.
- **Key already exists:** replacement is deliberately refused. Follow API-SETUP.md for revocation/rotation; do not delete the quota ledger.

## Development and validation

From the source checkout: `uv sync --extra desktop`, `uv run pytest -q`, then `uv build`. The wheel includes templates, static assets, demo fixtures and the icon. For a temporary empty test use `SIGNALTUBE_DATA_DIR="$(mktemp -d)" uv run signaltube-desktop`.

On the developer's Omarchy PC: window load, tray registration, close-to-tray, second-launch restore, Quit and live-library refresh were exercised. This is limited host evidence, not certification across Linux distributions. See TESTING.md for the remaining acceptance checks.
