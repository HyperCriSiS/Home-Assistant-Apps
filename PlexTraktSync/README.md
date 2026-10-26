# PlexTraktSync for Home Assistant

Experimental native Home Assistant App wrapping [PlexTraktSync 0.35.21](https://github.com/Taxel/PlexTraktSync/releases/tag/0.35.21).
This is a development candidate, **not an accepted or released implementation**.

- Admin-only Ingress onboarding, Plex connection test and Trakt device authorization.
- Credentials, refreshed OAuth tokens, approval and sync status persist under `/data/pts`.
- Read-only initial analysis and explicit approval before any media writes.
- Single-writer periodic/manual watched-history sync; optional reverse sync and ratings.
- Read-only playback listener with targeted sync; no direct Trakt scrobbling or rewatch entries.
- Collection, watchlist, liked lists and favorites are protected by generated configuration and a request allowlist.
- No host ports, host networking, Docker access or Supervisor API access.

**Die Trakt-Sammlung wird von dieser App nicht verändert, weil sie in meinem System als Favoritenarchiv verwendet wird.**

See [DOCS.md](DOCS.md) for setup, safety boundaries and outstanding acceptance work.
The upstream project is MIT licensed; see [LICENSE.upstream](LICENSE.upstream).
The wrapper does not update packages during startup. Upstream updates are proposed
as draft PRs after wheel checksum verification; stable releases remain manual.
