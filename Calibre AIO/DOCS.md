# Calibre AIO configuration

## Getting started

Open Calibre AIO from Home Assistant. **Entdecken** contains Shelfmark search,
requests, downloads and source/client settings. **Bibliothek** contains CWA's
library, reading and management features. The navigation stays visible while
using either application. Both native interfaces remain intact.

An HA administrator receives administrator access to both. Normal HA users
get a separate CWA reader/download account and a Shelfmark user/request
account; Shelfmark's source request policies determine what they can request
or download. A shared Calibre library is visible according to CWA's content
restrictions; this is not a private library per user. CWA administrators share
the selected CWA admin account. Shelfmark keeps separate HA identities.

## App options

```yaml
library_dir: calibre-aio/library
ingest_dir: calibre-aio/ingest
network_share_mode: false
shelfmark:
  external_bypass_url: ""
sso:
  enabled: true
  admin_users: []
  admin_account: admin
  auto_create_users: true
```

- `library_dir`: library path relative to `/share`.
- `ingest_dir`: completed-book handoff path relative to `/share`. Do not use
  the same path for the library or another app's active download directory.
- `network_share_mode`: polling instead of filesystem notifications for SMB/NFS.
- `shelfmark.external_bypass_url`: optional HTTP(S) endpoint of a compatible
  external browser-challenge service. Empty disables browser challenge handling.
  This is not required for debrid torrent clients. This app does not contain
  an embedded Chromium/Tor/VPN stack. Configure outbound routing separately.
- `sso.enabled`: must remain `true` in this initial AIO version. Both applications
  are ingress-only; native standalone login/device clients are not exposed.
- `sso.admin_users`: leave `[]` for automatic HA administrator roles. A nonempty
  optional list selects specific HA user IDs instead, matching the original
  CWA adapter. It applies consistently to Shelfmark and CWA.
- `sso.admin_account`: name of the existing CWA administrator (default `admin`).
  The initial CWA database creates this account. A missing or non-admin target
  prevents CWA from starting. This does not select Shelfmark accounts.
- `sso.auto_create_users`: create CWA reader accounts for normal HA users.
  When false, CWA permits only existing bound readers and selected admins.
  Shelfmark's proxy user provisioning remains controlled by HA identity;
  this option does not disable its request accounts.

Automatic roles require a Supervisor that supplies `X-Remote-User-Groups`.
Missing or malformed groups never grant admin rights. Use the optional explicit
selection if your Supervisor lacks groups. A CWA cookie, Shelfmark cookie or
API key cannot replace the current HA identity. Roles apply as soon as
Supervisor forwards updated groups; open a fresh HA session when testing role
revocation to avoid Supervisor session caching.

## Downloads and library handoff

Configure sources and Real-Debrid/other clients in Shelfmark's settings, not in
the HA YAML. Credentials remain in Shelfmark's private persistent settings.
Real-Debrid handles torrent/magnet downloads; search sources are still needed.
External torrent/Usenet clients need paths visible to this container. Only
`/share` is mounted from the host; use shared `/share` paths and Shelfmark's
remote path mappings if such a client reports different paths.

Shelfmark stages downloads under `/data/shelfmark-staging` and publishes
completed ebooks to `/cwa-book-ingest`, backed by `/share/<ingest_dir>`.
Hardlink delivery is disabled because CWA consumes the ingest files. Shelfmark
reads Calibre's `metadata.db` to mark already-owned books; it does not write
the library database directly. CWA owns the actual import/conversion process.
Audiobooks go to separate `/data/shelfmark-audiobooks` storage; CWA is not an
audiobook library server. No Audiobookshelf integration is bundled.

## Persistence and backups

| Data | Container path |
| --- | --- |
| CWA state and account bindings | `/data/config` (via `/config`) |
| Shelfmark settings, accounts and secrets | `/data/shelfmark` |
| Shelfmark staging | `/data/shelfmark-staging` |
| Ebook library | `/share/<library_dir>` |
| Completed-book handoff | `/share/<ingest_dir>` |

HA backs up the private App data. Back up the library under `/share` separately
or include the share folder in your HA backup. This app has a distinct slug
and does not adopt the private databases of the previous CWA test installation.
Test with the default separate folders before copying existing library data.

No backend ports are published. CWA binds `127.0.0.1:8083`, Shelfmark
`127.0.0.1:8085`; nginx ingress on 8084 accepts only Supervisor `172.30.32.2`.
CWA OAuth, Magic Links, Kobo and KOReader auth endpoints remain blocked under
SSO. Standalone external reader sync is outside the initial AIO scope.

## Troubleshooting

Check App logs after a restart. The CWA launcher identifies whether automatic
HA roles or an explicit selection is active. Shelfmark startup is separate;
one backend can be unavailable while the other is restarting. A 403 means the
request lacks a trusted HA identity/permission; a 502 normally means that the
target backend has not started yet. Send only relevant log excerpts; avoid
including API tokens or ingress URLs containing session identifiers.

Upstream versions are listed in `upstream.json`. All upgrades should use the
manifest/update workflow described in [UPDATING.md](UPDATING.md), with a backup
before a real installation is upgraded.
