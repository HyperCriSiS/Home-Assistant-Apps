# PlexTraktSync for Home Assistant

Experimental native Home Assistant App wrapping [PlexTraktSync 0.35.21](https://github.com/Taxel/PlexTraktSync/releases/tag/0.35.21).
This is a development candidate, **not an accepted or released implementation**.

- Dark, responsive admin-only Ingress UI with a sidebar, all 29 settings,
  Plex connection test and Trakt device authorization. No native HA configuration form.
- Changes apply immediately; existing native settings migrate once and survive restarts.
- Credentials, refreshed OAuth tokens, approval and sync status persist under `/data/pts`.
- Read-only initial sync analysis and explicit approval before normal media writes.
- Single-writer periodic/manual watched-history sync; optional reverse sync and ratings.
- Read-only playback listener with targeted sync; no direct Trakt scrobbling or rewatch entries.
- Independent ratings/watchlist directions, optional liked-list playlists and Trakt-to-Plex resume progress.
- Watchlist, liked-list and progress sync default off; normal sync cannot change collection or Trakt favorites.
- Full/partial Trakt ZIP backups, schedules, tiered retention and separately approved restore; see [BACKUPS.md](BACKUPS.md).
- No host ports, host networking, Docker access or Supervisor API access.

Normal sync excludes Trakt collection/favorite writes. Explicit backup restoration
is separate and can restore the categories selected in its own preview.

See [DOCS.md](DOCS.md) for setup, safety boundaries and outstanding acceptance work.
See [OPTIONS.md](OPTIONS.md) for the complete supported sync-setting mapping,
safe defaults and the effects of explicitly enabling optional list/progress sync.
The upstream project is MIT licensed; see [LICENSE.upstream](LICENSE.upstream).
The wrapper does not update packages during startup. Upstream updates are proposed
as draft PRs after wheel checksum verification; stable releases remain manual.
