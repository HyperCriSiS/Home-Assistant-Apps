# Calibre AIO

**Book discovery and your Calibre library in one Home Assistant App.**

[![Validate Calibre AIO](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml)
![Architecture amd64](https://img.shields.io/badge/amd64-supported-success)
![Architecture aarch64](https://img.shields.io/badge/aarch64-supported-success)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-App-41BDF5?logo=homeassistant&logoColor=white)
![Ingress](https://img.shields.io/badge/Ingress-SSO-41BDF5)

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

## Installation

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

## First start

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

## Features

- Automatic Home Assistant ingress sign-in, without copying user IDs
- One configured HA login name manages both applications; other HA users have their own
  identities, reader accounts and Shelfmark requests
- Real-Debrid, AllDebrid, TorBox and other upstream download clients
- Complete downloads automatically delivered to CWA's import folder
- Separate persistent databases and separate Python environments
- Pinned upstream sources, checksums and automated update proposals

Its private state is independent of other CWA apps. Installation does not
migrate or delete existing data.

## Browser-challenge sources

The initial image contains Shelfmark's core download stack. Browser-challenge
sources may require a separate compatible bypass service, configured through
the optional `shelfmark.external_bypass_url` App option. An old pinned browser
is deliberately not bundled. Torrent/debrid downloads do not require it.

## Documentation

- [Configuration](DOCS.md) · [Deutsche Anleitung](DOCS.de.md)
- [Integration design](INTEGRATION.md)
- [Verification](TESTING.md)
- [Upstream maintenance](UPDATING.md)
- [Third-party notices](NOTICE.md)
