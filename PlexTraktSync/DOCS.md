# Setup and operations

## Candidate status

Local adapter tests are available. Docker builds, Home Assistant OS installation,
actual Ingress and live Plex/Trakt acceptance must pass before release. Both
architectures have CI jobs but are not yet verified build targets.

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

1. Install the development App in HAOS after the generated store contains it.
2. Set `plex_url` to a reachable LAN URL or hostname, normally `http://SERVER:32400`.
3. Set `plex_username` to the Plex account owning the token. Start the App with
   both automatic modes disabled. Open its Ingress panel as an HA administrator.
4. Enter the Plex token in the panel and save. The connection test checks account
   identity and lists accessible libraries. A token for another account is rejected.
   Managed Plex Home profiles are not supported by this candidate; do not put
   an owner's token alongside a managed user's name.
5. Create an application at <https://developer.trakt.tv/apps/new> and enter its
   client ID. Use redirect URI `urn:ietf:wg:oauth:2.0:oob`. Client secret is optional
   for newer applications. No manually generated access token is needed.
6. Request a Trakt device code, open the returned verification URL in your browser
   and confirm the displayed code. Click authorization check after confirming.
   Polling respects Trakt's interval, slows on HTTP 429 and refuses expired codes.
7. Prepare the initial analysis. Wait until `busy` becomes false and inspect the
   counts and unmatched titles. Approval must match the current options and
   credentials. Reauthorization invalidates the previous analysis and approval.
8. Explicitly approve the first write and use manual sync. Enable `sync_enabled`
   for periodic operation after reviewing the results. HA configuration changes
   require restart and another analysis/approval.

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

The preview walks the library with upstream's reader and resolver and never calls
its synchronization method. HTTP policy additionally refuses media writes,
including Plex's GET-based scrobble/rate endpoints. OAuth refresh is permitted
because it updates credentials, not watched history. ID searches returning more
than one match fail closed. API failures invalidate the analysis run.

The report inventories selected libraries independently of upstream matching.
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
  any native option or credentials require a new approval.
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
