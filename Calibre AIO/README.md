# Calibre AIO

Find books with **Shelfmark** and manage/read them with **Calibre-Web Automated**
in one Home Assistant App. A shared navigation bar switches between
**Bibliothek** (your library) and **Entdecken** (discovery/downloads). The compact
bar opens Bibliothek first by default; choose `start_page: shelfmark` in the
App options to start with Entdecken instead.

- Automatic Home Assistant ingress sign-in, without copying user IDs
- One configured HA login name manages both applications; other HA users have their own
  identities, reader accounts and Shelfmark requests
- Real-Debrid, AllDebrid, TorBox and other upstream download clients
- Complete downloads automatically delivered to CWA's import folder
- Separate persistent databases and separate Python environments
- Pinned upstream sources, checksums and automated update proposals

This is a new experimental app. Its private state is independent of the
previous CWA test app. Installation does not migrate or delete existing data.

## Install the development build

Add this repository to the HA App store:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#feature/calibre-aio
```

Install **Calibre AIO**, start it and open its web interface as an HA
user. Before starting, set `sso.admin_username` to your HA login name (not your
display name or user ID). Configure search sources and your download service in the
Shelfmark settings under **Entdecken**. Use **Bibliothek** for CWA settings.
The administrator assignment is managed by this option; changes to HA roles do
not automatically change it. No additional HA API permission is required.

The initial image contains Shelfmark's core download stack. Browser-challenge
sources may require a separate compatible bypass service, configured through
the optional `shelfmark.external_bypass_url` App option. An old pinned browser
is deliberately not bundled. Torrent/debrid downloads do not require it.

See [configuration](DOCS.md), [integration design](INTEGRATION.md),
[verification](TESTING.md) and [upstream maintenance](UPDATING.md).
