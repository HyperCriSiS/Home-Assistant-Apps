<p align="center"><img src="https://raw.githubusercontent.com/HyperCriSiS/Home-Assistant-Apps/main/Calibre%20AIO/icon.png" alt="Calibre AIO icon" width="128"></p>

# Calibre AIO

**Book discovery and your Calibre library in one Home Assistant App.**

[![Validate Calibre AIO](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml)
[![CWA version](https://img.shields.io/badge/CWA-v4.0.8-B49A64)](https://github.com/crocodilestick/Calibre-Web-Automated/releases/tag/v4.0.8)
[![Shelfmark version](https://img.shields.io/badge/Shelfmark-v1.6.1-B49A64)](https://github.com/calibrain/shelfmark/releases/tag/v1.6.1)
![Architecture amd64](https://img.shields.io/badge/amd64-supported-success)
![Architecture aarch64](https://img.shields.io/badge/aarch64-supported-success)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-App-41BDF5?logo=homeassistant&logoColor=white)
![Ingress](https://img.shields.io/badge/Ingress-SSO-41BDF5)
![License](https://img.shields.io/badge/license-MIT-blue)

Find books with **Shelfmark** and manage/read them with **Calibre-Web Automated**
in one Home Assistant App. A shared navigation bar switches between
**Library** and **Discover** (downloads). The compact
bar opens Library first by default; choose `start_page: shelfmark` in the
App options to start with Discover instead.

> [!IMPORTANT]
> Home Assistant Apps require **Home Assistant OS** or a **Supervised** installation.

> [!IMPORTANT]
> You are responsible for only downloading books you are legally entitled
> to access. This App does not ship or configure any download source.

## 📦 Installation

### Stable

[![Add stable repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps)

If the button opens the App store without showing the repository dialog, add it manually:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps
```

Then search for **Calibre AIO**, install it, start it and open **Web UI**.

### Development testing

To test the current `dev-calibre` candidate before it is promoted to `main`, add the shared generated
development store:

[![Add development repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps%23dev-store)

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

The development App is shown as **Calibre AIO (Dev)** under
**HyperCriSiS Apps (Dev)**.

> [!WARNING]
> Development builds may contain incomplete or breaking changes. Use the stable repository
> for normal production use.

## 🚀 First start

Start the app and open its interface inside HA.
On an unconfigured installation your signed-in HA administrator is adopted
automatically and the app restarts. The interface reloads when both applications
are ready. Existing administrator assignments are preserved.
Alternatively, set `sso.admin_username` manually to your HA login name.

Configure search sources and your download service in the
Shelfmark settings under **Discover**. Use **Library** for CWA settings.
The administrator assignment is managed by this option; changes to HA roles do
not automatically change it. No additional HA API permission is required.

Existing settings, accounts and library data are retained on upgrades.
HA option labels and the AIO shell follow your German or English language.
CWA has its own user language; Shelfmark uses English.

## ✨ Features

- Automatic Home Assistant ingress sign-in, without copying user IDs
- One configured HA login name manages both applications; other HA users have their own
  identities, reader accounts and Shelfmark requests
- Real-Debrid, AllDebrid, TorBox and other upstream download clients
- Complete downloads automatically delivered to CWA's import folder
- Separate persistent databases and separate Python environments
- Pinned upstream sources, checksums and automated update proposals

Its private state is independent of other CWA apps. Installation does not
migrate or delete existing data.

## 🧭 Browser-challenge sources

The App includes Shelfmark's full browser stack with the same Chromium version
as the official Shelfmark image, so browser-challenge sources work without an
extra service. Shelfmark's bypass settings are configured directly in its
interface. Setting the optional `shelfmark.external_bypass_url` App option
instead uses an external service and locks those settings to that service.

## 📚 Documentation

- [Configuration](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/DOCS.md) · [Deutsche Anleitung](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/DOCS.de.md)
- [Integration design](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/INTEGRATION.md)
- [Verification](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/TESTING.md)
- [Upstream maintenance](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/UPDATING.md)
- [Third-party notices](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/NOTICE.md)

## 🩺 Troubleshooting

Library imports that fail with a read-only database, SSO sign-in issues and
backup scope are covered in [DOCS.md](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/DOCS.md#-troubleshooting). The App log
(Settings, Apps, Calibre AIO, Log) shows both applications and the ingress proxy.

## 🏷️ Versioning

The App version follows the repository's CalVer scheme `vYYYY.MM.DD`, with
`-N` for a further release on the same day. The packaged Calibre-Web Automated
and Shelfmark versions are separate: the badges above and the App description
in the store name them, and [CHANGELOG.md](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/CHANGELOG.md) lists every change.
Development builds carry a `-dev.<n>` suffix.

## 💬 Support

Open an issue in the
[repository issue tracker](https://github.com/HyperCriSiS/Home-Assistant-Apps/issues)
with the App version, the App log and the steps that led to the problem.

## 📄 License

The wrapper code in this directory is licensed under the MIT License, see
[LICENSE](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/LICENSE). Calibre-Web Automated (GPL-3.0-or-later), Shelfmark (MIT),
Calibre, kepubify and the original add-on packaging keep their own licenses;
see [NOTICE.md](https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/Calibre%20AIO/NOTICE.md) for the packaged versions and license files.
