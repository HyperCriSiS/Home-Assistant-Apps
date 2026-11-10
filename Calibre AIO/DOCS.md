# Calibre AIO documentation

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

All options with their defaults:

```yaml
library_theme: modern
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

### `library_theme`

`modern` (default) applies the App's own dark theme with gold accents to CWA; `upstream` keeps CWA's
original look. Restart the App after changing it. The theme changes appearance only, not library
data, sorting logic or permissions. Shelfmark keeps its native interface; the shared navigation
uses matching colors.

### `start_page`

Initial view, `library` (Library, default) or `shelfmark`
(Discover). The compact navigation always lists Library first. Restart
the app after changing this option, then reopen its web interface.

### `library_dir`

Library path relative to `/share`. The value must be a
relative path without `.` or `..` segments; an empty or absolute value stops
the app from starting.

### `ingest_dir`

Completed-book handoff path relative to `/share`, with the
same rules. It must not be the library folder, lie inside it or contain it,
and should not be another app's active download directory.

### `network_share_mode`

Polling instead of filesystem notifications for SMB/NFS.

### `shelfmark.external_bypass_url`

Optional HTTP(S) endpoint of a compatible
external browser-challenge service. Leave empty to use the included Chromium
and configure the bypass in Shelfmark's settings. A value locks those settings
to the external service. This app has no embedded Tor/VPN stack; configure
outbound routing separately.

### `sso.enabled`

Must remain `true` in this initial AIO version. Both applications
are ingress-only; native standalone login/device clients are not exposed.

### `sso.admin_username`

HA login name, matched exactly (case-sensitive).
Enter the name used to sign in to HA, not the display name or an ID. Empty
configuration opens setup; nobody receives administrator access until configured. This option selects the
administrator in both applications; other HA users get normal accounts.

### `sso.admin_account`

Name of the existing CWA administrator (default `admin`).
The initial CWA database creates this account. A missing or non-admin target
prevents CWA from starting. This does not select Shelfmark accounts.

### `sso.auto_create_users`

Create CWA reader accounts for normal HA users.
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

Use the **+** menu in the library to upload files or choose **Add folder …**.
Folder selection includes supported ebook files in subfolders; unrelated file
types are skipped. The books use the normal upload/import flow. Calibre organizes
the resulting library; the source directory hierarchy is not preserved as shelves.

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
Calibre Web's admin **Downloads** page instead groups recorded downloads by
user. It fills when users download library books through Calibre Web or send
them to an e-reader; Shelfmark imports do not populate this overview.
Audiobooks go to separate `/data/shelfmark-audiobooks` storage; CWA is not an
audiobook library server. No Audiobookshelf integration is bundled.

## Persistence and backups

| Data | Container path |
| --- | --- |
| CWA state and account bindings | `/data/config` (via `/config`) |
| CWA safety copies of processed books | `/data/config/processed_books` |
| CWA cover thumbnails (not backed up) | `/data/config/thumbnails` |
| Shelfmark settings, accounts and secrets | `/data/shelfmark` |
| Shelfmark cover cache of search results (not backed up) | `/data/shelfmark/covers` |
| Shelfmark staging and logs (not backed up) | `/data/shelfmark-staging`, `/data/shelfmark-logs` |
| Shelfmark audiobooks | `/data/shelfmark-audiobooks` |
| Ebook library | `/share/<library_dir>` |
| Completed-book handoff | `/share/<ingest_dir>` |

> [!WARNING]
> An HA backup of this App contains only the private `/data` folder: CWA state,
> Shelfmark settings and audiobooks. The ebook library and the ingest folder
> live under `/share` and are **never part of the App backup**. They are covered
> by the **Share** folder of an HA backup: tick **Share** to include the
> library, untick it when you back up the library by other means.

The App backup skips everything that is rebuilt or not needed after a
restore: CWA's cover thumbnails (regenerated from the library covers on first
view and by the nightly thumbnail task), Shelfmark's cover cache of search
results (up to 500 MB by default, downloaded again on the next search), caches,
logs, temporary conversion files, runtime markers, Shelfmark's download
staging and CWA's `processed_books/imported` copies, which duplicate files in
the library.

The rest of `processed_books` stays in the backup because it exists nowhere
else: originals before an automatic conversion (`converted`) or EPUB fix
(`fixed_originals`), failed imports (`failed`) and books removed while
resolving duplicates (`duplicate_resolutions`). Disable CWA's automatic import
and conversion backups in CWA Settings if you do not want these copies. This app has a distinct slug
and does not adopt the private databases of the previous CWA test installation.
Test with the default separate folders before copying existing library data.

No backend ports are published. CWA binds `127.0.0.1:8083`, Shelfmark
`127.0.0.1:8085`; nginx ingress on 8084 accepts only Supervisor `172.30.32.2`.
CWA OAuth, Magic Links, Kobo and KOReader auth endpoints remain blocked under
SSO. Standalone external reader sync is outside the initial AIO scope.

## Troubleshooting

If Shelfmark reports a completed download but the book is missing from the
library, check the subsequent CWA ingest log. `apsw.ReadOnlyError: attempt to
write a readonly database` means that CWA cannot write the library database;
the earlier Shelfmark completion only confirms delivery to the ingest folder.
The App repairs local library ownership after library initialization,
including existing installations, and checks write access as UID/GID 911
before starting CWA. Update and restart the app, then retry the import of the
affected file. For `network_share_mode: true`, ownership is kept unchanged;
the share must grant UID/GID 911 write access to both `metadata.db` and the
library directory so SQLite can create its journal files. Do not delete or
recreate `metadata.db` to resolve a permissions error.

Check App logs after a restart. The CWA launcher confirms the configured
HA login-name policy. An empty `sso.admin_username` opens automatic setup inside
HA for an HA administrator. Existing assignments are never overwritten by setup.
If setup fails, the message identifies the failed step; retry or configure the
login manually and restart. Shelfmark startup is separate;
one backend can be unavailable while the other is restarting. A 403 means the
request lacks a trusted HA identity/permission; a 502 normally means that the
target backend has not started yet. Send only relevant log excerpts; avoid
including API tokens or ingress URLs containing session identifiers.

At every start CWA's own init script asks `api.github.com` for the newest CWA
release to show its update notice. The request has a short timeout and the
start continues without internet access; a related warning in the log is
harmless. This App updates CWA only through its own releases.

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

## Installation images

Home Assistant pulls the versioned GHCR image for its architecture. GitHub Actions
builds and tests both images before a Dev update is advertised. Initial downloads
can still be large; later updates reuse unchanged image layers. No registry login
is needed. The supported development repository is `#dev-store`; `dev-calibre`
is an integration branch, not an installation channel.
