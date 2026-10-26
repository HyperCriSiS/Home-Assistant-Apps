# Setup and operations

## Configuration coverage (App 0.3.0)

See [OPTIONS.md](OPTIONS.md) for every supported sync/watch setting, all 29 option names, defaults and permanently locked settings.
All configuration lives in the dark Ingress UI, with a desktop sidebar and mobile
menu. The native HA configuration form is disabled. No restart is needed after saving.
Watchlists, liked-list playlists and playback progress are now optional controls;
all default off. Collection changes, Trakt favorites, direct scrobbles and importing
other Plex users remain prohibited. The ratings master switch is retained, with
independent per-direction controls. Upgrading from 0.1.0 preserves credentials and
safe defaults but requires a fresh analysis/approval.

## Candidate status

The previous 0.2.0 candidate passed native amd64/aarch64 builds, startup,
source restrictions, clean stop and persistent restart checks.
[0.2.0 CI evidence](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/40361937573).
The 0.3.0 Ingress implementation passes 69 local tests and desktop/mobile browser QA.
Use the [current validation workflow](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-plextraktsync.yml)
for the latest native build results.
Real Home Assistant OS installation, actual Ingress and live Plex/Trakt acceptance
must still pass before stable release.

`watch_enabled` enables a read-only notification adapter using upstream's
WebSocket listener and username/session validator. The upstream listener does not
require Plex Pass according to its documentation. Real Plex compatibility and
reconnection still require acceptance testing. This candidate does not yet satisfy
the full project acceptance criteria.

## Development installation

The intended repository is:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

It will contain **PlexTraktSync (Dev)** only after the development branch and
shared generator changes have been published. Until then this is a source-only
candidate. Do not claim store availability from these instructions.

1. Install and start the development App in HAOS after the generated store contains it.
2. Open **Web UI / Ingress** as a Home Assistant administrator. Under
   **Verbindungen**, enter the Plex server URL (normally `http://SERVER:32400`),
   exact Plex username and its Plex token. Save, then test the connection.
   The test rejects tokens belonging to another account and lists libraries.
   Managed Plex Home profiles are not supported by this candidate.
3. Create a Trakt API application at <https://trakt.tv/oauth/applications> using
   redirect URI `urn:ietf:wg:oauth:2.0:oob`. Enter its client ID and, when needed,
   client secret in **Verbindungen**, then save. Existing values remain stored
   when secret fields are left blank; they are never sent back to the browser.
4. Click **Mit Trakt verbinden**, open Trakt's activation page and confirm the
   displayed code. The App polls automatically; manual checks are also available.
   Polling respects Trakt's interval, slows on HTTP 429 and refuses expired codes.
5. Choose directions and scheduling under **Synchronisierung**, media selection
   under **Bibliotheken & Filter**, and timeouts/providers under **Erweitert**.
   Automatic modes and optional list/progress writes are off by default.
6. Save changes. They apply immediately, stop the playback listener and revoke
   previous analysis/approval. Invalid inputs and stale saves from other browser
   sessions are rejected. A running job must finish before settings can change.
7. Open **Analyse & Freigabe** and analyze. Wait for completion, inspect counts,
   enabled directions, warnings and title lists, then explicitly approve.
8. Use manual sync and review results. Timer/listener operation requires the same
   approval. Enabling a mode is a configuration change, so analyze and approve
   again after saving it. Pause/resume does not change the configuration.

### Upgrade from native HA configuration

The existing `/data/pts/options.json`, credentials and OAuth tokens are retained.
Only when the persistent options file does not yet exist does startup import
legacy `/data/options.json`. Ingress becomes the configuration source afterward;
restarts never copy Supervisor options over it. Additive missing settings receive
safe defaults. No optional write mode is activated by migration. Replacing Trakt
client credentials removes the old OAuth authorization and requires reconnection.
HA metadata uses `options: {}` and `schema: false` to hide the native form while
accepting legacy Supervisor option data; server-side validation remains enforced.

## Directions and settings

Plex-to-Trakt watched status defaults on. Trakt-to-Plex defaults off. The app adds
missing watched state rather than mirroring removals. Already watched titles are
skipped by upstream; Trakt-to-Plex cannot reconstruct identical playback history
or every original watch timestamp. This wrapper refuses upstream attempts to
clear Plex watched state in response to a Trakt show reset; that run reports a
policy failure rather than marking episodes unwatched.

Ratings default off. With `rating_priority: none`, existing conflicting ratings
are preserved and missing ratings may be filled. `plex` or `trakt` explicitly
allows overwriting ratings on the other side. Show ratings are handled by the
upstream sync plugin; the initial report includes movie, episode and show conflicts.

`include_libraries` restricts the libraries to use; an empty list means all
accessible libraries except `exclude_libraries`. Exclusion wins. Sync interval is
15–1440 minutes, default 60, measured after completion. Failed runs retry at the
next interval. There is a six-hour job timeout and no overlapping writer.

`log_level` controls structured JSON job logs (`info`, `warning`, `error`). Detailed
upstream logging is suppressed to prevent secrets in request URLs reaching logs.
Errors are shown by class in Ingress and persist across App restarts.

### Playback monitoring and duplicate avoidance

The notification process performs no Trakt writes. It uses upstream's
`WatchStateUpdater.can_scrobble` only to validate session ownership, binds the
accepted session to its media ID, and coalesces progress events. It schedules a
targeted sync after 30 seconds to allow Plex to persist watched status. During
long playback a title is rechecked at most once per minute; a stop event also
requests a check. Library selection and exclusion apply to the targeted worker.

Full, targeted and manual jobs use the same lock. Every worker loads fresh watched
state and upstream skips items already watched on Trakt. Direct Trakt scrobble
endpoints are deliberately blocked, so two independent writer implementations
cannot race. This mode synchronizes missing watched state; it does **not** add
another history entry for every rewatch or show live "watching now" scrobbles.
This is a documented limitation compared with upstream's raw `watch` command.

The upstream WebSocket listener reconnects after 15 seconds; if the process exits,
the controller waits 60 seconds before restarting it. Failed targeted jobs wait
five minutes before retrying. Event queues are bounded to 1,000 titles and are
not persisted. A restart, dropped event or playback missed while disconnected is
covered by the periodic full sync when that mode is enabled. Keep it enabled as
a backstop. Monitoring requires `plex_to_trakt_watched: true` and the same initial
analysis and approval as full sync. Both automation switches are independent.

## Initial analysis and privacy

The preview walks the library with upstream's reader and resolver; optional
features additionally use upstream synchronization in dry-run mode. HTTP policy additionally refuses media writes,
including Plex's GET-based scrobble/rate endpoints. OAuth refresh is permitted
because it updates credentials, not watched history. ID searches returning more
than one match fail closed. API failures invalidate the analysis run.

The report inventories selected libraries independently of upstream matching.
Enabled optional features additionally execute upstream's dry-run behind the HTTP
write guard. The report warns about watchlist removals, managed Plex playlist
replacement and playback progress overwrites; it does not enumerate their exact
replacement diffs. See OPTIONS.md before enabling them.
It includes watched movie/episode counts, matched items already watched or missing
on Trakt, movie/episode/show rating conflicts, and unresolved titles. Items skipped
by upstream traversal (for example, an episode whose parent show disappeared)
appear in `not_traversed` and in the unresolved list. This is a point-in-time
analysis, not a transactional snapshot of both services. Completeness against
real multi-library data still requires acceptance testing.

All credentials live under `/data/pts` with owner-only file permissions. The
worker regenerates protected `config.yml` and `servers.yml` on every execution;
manual edits are overwritten. `.pytrakt.json` uses upstream pytrakt's format and
refresh logic. Credentials are never returned by the status endpoint. Backups
contain secrets: protect backup access. A cold backup includes the persistent
configuration and tokens. An unsupported state version fails closed.

The panel accepts connections only from the Supervisor Ingress proxy
`172.30.32.2` and requires a per-process CSRF token on mutations. No host port is
published. Real Supervisor/Ingress access still needs verification.

## Troubleshooting

- Connection/authentication errors: check server address, network, token account,
  and Trakt authorization. Reauthorize invalid or revoked OAuth credentials.
- No automatic sync: check `sync_enabled`, pause state and current approval.
- Approval unavailable: run a new analysis and wait for it to finish. Changes to
  any saved option or credentials require a new approval.
- Job failure: no success timestamp is recorded and the scheduler waits until
  the next interval. An ambiguous network failure after a server accepted a write
  cannot provide an exactly-once guarantee; inspect history before retrying.
- Watch not running: verify approval, pause state, watched direction and Plex
  sessions access. The account must be verifiable; other users are rejected.

## Updates and release

The build pins PlexTraktSync 0.35.21, verifies its wheel SHA-256 and uses its exact
dependency requirements. `upstream.json` owns the version and checksum; verify
generated Dockerfile and HA build arguments with `scripts/upstream.py check`.
The HA base tags follow existing repository conventions and are not digest-pinned.
No startup downloads or self-update command is exposed. New upstream versions
must be proposed and tested on `dev-plextraktsync`, never automatically released
to `main`. The weekly updater verifies the upstream tag and wheel content before
opening a draft PR against `dev-plextraktsync`, following the existing Calibre
workflow. Major upgrades and pre-1.0 minor upgrades are left for manual maintenance.
Update proposals do not merge automatically. The existing manual `promote.yml`
flow offers a PlexTraktSync draft release PR only after exact-commit validation.

Use the existing generated Dev-Store and manual release process. Shared workflow
changes must be reviewed separately before they are active from `main`; this must
not publish the unfinished App on stable. Run validation on the exact development
commit, then HAOS install, ingress, OAuth, restart and carefully approved account
tests. Only after all acceptance gaps are closed may a human approve stable release.
