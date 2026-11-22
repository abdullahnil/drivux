<p align="center">
  <img src="docs/logo.png" width="128" alt="G-Drivux logo">
</p>

<h1 align="center">G-Drivux</h1>

<p align="center">
  A simple Google Drive client for Linux. It mounts Drive as a disk and keeps your folders in two-way sync.<br>
  Built with GTK 4 and libadwaita, powered by <a href="https://rclone.org">rclone</a>.
</p>

<p align="center">
  <b>English</b> · <a href="README.tr.md">Türkçe</a>
</p>

---

## What it does

G-Drivux does two things, and you can use either one or both:

1. **Mounts Google Drive as a disk.** Your whole Drive shows up in the Files sidebar as "Google Drive". Files are downloaded when you open them, so they don't fill up your disk.
2. **Syncs folders in both directions.** The folders you choose stay on your computer and open without an internet connection. Changes on either side are copied to the other side.

## Features

- **Setup wizard.** On first launch a wizard walks you through every step:
  - installs rclone
  - connects your Google account, optionally with your own client ID
  - asks where to mount the disk and how big the cache can get
  - lets you pick the folders to sync
- **Installs rclone for you.** If rclone is missing or too old, the wizard downloads the latest release from the official site. It checks the file against rclone's SHA256 checksums and installs it for your user only, so it needs no root access.
- **Google Docs support.** Docs, Sheets and Slides show up on the disk as small shortcut files. Double-click one and it opens in Google's own editor in your browser.
- **Status at a glance.** One window shows the overall status, your Drive storage usage, the synced folders and when each was last synced.
- **Automatic sync.** A change in a synced folder is uploaded within about 15 seconds. G-Drivux also syncs on a regular schedule, every 5 minutes by default.
- **Error notifications.** When something goes wrong you get a desktop notification. The details are in the log viewer.
- **Protection against mass deletion.** If a single sync would delete more than 50 files, it stops and waits for your confirmation.
- **No data loss on conflicts.** If the same file changes on both sides, the newer version wins and the other one is kept as a numbered copy.
- **Starts with your session.** The disk and the sync both start when you log in.

## Installation

### From a package (recommended)

Download the package for your distribution from the [Releases](https://github.com/abdullahnil/gdrivux/releases) page:

```bash
# Fedora / RHEL / openSUSE
sudo dnf install ./gdrivux-1.2.0-1.noarch.rpm

# Ubuntu 24.04+ / Debian 13+ / Linux Mint 22+
sudo apt install ./gdrivux_1.2.0_all.deb
```

Then open **G-Drivux** from your app menu and the setup wizard starts.

### From source

```bash
git clone https://github.com/abdullahnil/gdrivux.git
cd gdrivux
./kur.sh
```

`kur.sh` does three things:

- installs the required system packages with your package manager (dnf, apt, pacman or zypper)
- installs G-Drivux for your user only, under `~/.local`
- opens the setup wizard

To update, run `git pull` and then `./kur.sh` again. Your settings are kept.

### Requirements

- GTK 4 and **libadwaita 1.5 or newer**. Fedora 40+, Ubuntu 24.04+ and Debian 13+ all qualify.
- FUSE 3, for the disk feature
- A systemd user session

## Usage

Open **G-Drivux** from your app menu.

From a terminal:

```bash
gdrivux            # open the app
gdrivux esitle     # sync now
gdrivux durum      # print sync status as JSON
```

> The app's interface is currently in Turkish. An English translation is planned.

## How it works

| Component | Role |
|---|---|
| `gdrivux-disk.service` | Mounts Drive at `~/Google Drive` with `rclone mount`, using the full VFS cache. |
| `gdrivux.service` | A Python service that syncs folders with `rclone bisync`. It watches the folders for changes and runs the schedule. |
| `gdrivux` | The GTK 4 / libadwaita app and setup wizard. It talks to the service through the settings and status files and Unix signals. |

| What | Where |
|---|---|
| Settings | `~/.config/gdrivux/ayar.json` |
| Status | `~/.local/state/gdrivux/durum.json` |
| rclone (if G-Drivux installed it) | `~/.local/share/gdrivux/bin/rclone` |
| Logs | `journalctl --user -u gdrivux -u gdrivux-disk` |

### Building packages

```bash
./paketleme/paketle.sh   # writes the .rpm and .deb to dist/
```

This needs `rpmbuild` and `dpkg-deb`. On Fedora, install them with `sudo dnf install rpm-build dpkg`.

## Good to know

- **Sync is a mirror, not a backup.** If you delete or damage a file, that change goes to Drive as well. Files deleted from Drive stay in Drive's trash for 30 days.
- **Google Docs files only appear on the disk.** They are not part of folder sync, because they are documents on Google's servers, not real files.
- **Use your own client ID.** The Google client ID that rclone shares with all its users is being retired. To avoid losing access, turn on "Kendi Google client ID'ni kullan" (Use your own Google client ID) in the wizard and enter your own ID. The [rclone guide](https://rclone.org/drive/#making-your-own-client-id) explains how to create one.
- **Upgrading from "Drive Bağlantı" (1.1 and older).** G-Drivux used to be called Drive Bağlantı. Your settings, sync state and downloaded rclone move to the new names automatically the first time you run G-Drivux, and the old services are turned off.

## Uninstalling

```bash
./kaldir.sh                  # if you installed from source
sudo dnf remove gdrivux      # Fedora
sudo apt remove gdrivux      # Ubuntu / Debian
```

None of these touch your files on the computer or on Drive.

## License

[MIT](LICENSE). G-Drivux is not affiliated with or endorsed by Google. Google Drive is a trademark of Google LLC.
