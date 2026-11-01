# Calibre AIO configuration

[Deutsch](DOCS.de.md) | English

## Getting started

Open Calibre AIO inside Home Assistant. On first use with no configured app
administrator, your signed-in HA administrator is adopted automatically and
the app restarts. The interface reloads automatically once both applications
are ready. HA verifies your
administrator permission before saving your login name. Alternatively, enter
it manually in the app configuration. No additional app HA API access is needed.
**Discover** contains Shelfmark search,
requests, downloads and source/client settings. **Library** contains CWA's
library, reading and management features. The navigation stays visible while
using either application. Both native interfaces remain intact.

Shelfmark's Go To Library link opens CWA inside this shared interface on a
normal click, preserving the navigation bar.

The HA login configured in `sso.admin_username` receives administrator access
to both applications. Other HA users
get a separate CWA reader/download account and a Shelfmark user/request
account; Shelfmark's source request policies determine what they can request
or download. A shared Calibre library is visible according to CWA's content
restrictions; this is not a private library per user. CWA administrators share
the selected CWA admin account. Shelfmark keeps separate HA identities.

## App options

```yaml
start_page: library
library_dir: calibre-aio/library
ingest_dir: calibre-aio/ingest
network_share_mode: false
shelfmark:
  external_bypass_url: ""
sso:
  enabled: true
  admin_username: your_ha_login_name
  admin_account: admin
  auto_create_users: true
```

- `start_page`: initial view, `library` (Library, default) or `shelfmark`
  (Discover). The compact navigation always lists Library first. Restart
  the app after changing this option, then reopen its web interface.
- `library_dir`: library path relative to `/share`.
- `ingest_dir`: completed-book handoff path relative to `/share`. Do not use
  the same path for the library or another app's active download directory.
- `network_share_mode`: polling instead of filesystem notifications for SMB/NFS.
- `shelfmark.external_bypass_url`: optional HTTP(S) endpoint of a compatible
  external browser-challenge service. Leave empty to use the included Chromium
  and configure the bypass in Shelfmark's settings. A value locks those settings
  to the external service. This app has no embedded Tor/VPN stack; configure
  outbound routing separately.
- `sso.enabled`: must remain `true` in this initial AIO version. Both applications
  are ingress-only; native standalone login/device clients are not exposed.
- `sso.admin_username`: HA login name, matched exactly (case-sensitive).
  Enter the name used to sign in to HA, not the display name or an ID. Empty
  configuration opens setup; nobody receives administrator access until configured. This option selects the
  administrator in both applications; other HA users get normal accounts.
- `sso.admin_account`: name of the existing CWA administrator (default `admin`).
  The initial CWA database creates this account. A missing or non-admin target
  prevents CWA from starting. This does not select Shelfmark accounts.
- `sso.auto_create_users`: create CWA reader accounts for normal HA users.
  When false, CWA permits only existing bound readers and selected admins.
  Shelfmark's proxy user provisioning remains controlled by HA identity;
  this option does not disable its request accounts.

The app relies on Supervisor's authenticated user ID and login-name headers,
available in Supervisor 2026.10. It does not trust group headers or need HA API
access. The selected login is automatically bound to its HA ID in the private
`/data/config/ha_admin_bindings.db`; a replacement account with the same name
does not automatically inherit that binding. Both applications use this same
binding. Include it in app backups.

This assignment is independent of HA's administrator role. If you revoke
someone's HA admin role, also change `sso.admin_username` and restart this app
if their Calibre AIO administrator access should end. Disabling an HA account
still prevents new authenticated ingress sessions. A CWA/Shelfmark cookie,
API key, display name or supplied group header cannot replace the HA identity.
Readers do not see the administrator-only Shelfmark setup wizard.

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

Check App logs after a restart. The CWA launcher confirms the configured
HA login-name policy. An empty `sso.admin_username` opens automatic setup inside
HA for an HA administrator. Existing assignments are never overwritten by setup.
If setup fails, the message identifies the failed step; retry or configure the
login manually and restart. Shelfmark startup is separate;
one backend can be unavailable while the other is restarting. A 403 means the
request lacks a trusted HA identity/permission; a 502 normally means that the
target backend has not started yet. Send only relevant log excerpts; avoid
including API tokens or ingress URLs containing session identifiers.

Upstream versions are listed in `upstream.json`. All upgrades should use the
manifest/update workflow described in [UPDATING.md](UPDATING.md), with a backup
before a real installation is upgraded.

## Languages and development builds

HA displays option labels in your profile language (German or English). AIO
navigation and setup use HA's language, with the browser language as fallback.
CWA has its own per-user language setting. The Shelfmark interface
is English; book-language filters do not translate it. Static documentation
uses separate language files.

Use the existing `#dev-store` repository and install **Calibre AIO (Dev)**.
It is generated from `dev-calibre`; promotion to `main` is a separate release
step after testing. Its default library and import folders are separate from
the stable app. Do not point simultaneously running installations at the same
library or import folder.
