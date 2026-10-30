# Synchronization configuration and protected defaults

This table covers the sync, watch and list settings in the pinned PlexTraktSync
0.35.21 configuration. The dark Ingress UI exposes all 29 supported controls;
Home Assistant's native App configuration form is disabled. The analysis shows
effective sync directions and immutable protection. An analysis and
explicit approval are required again after any option changes.

## Your history-first defaults

| Upstream setting | App control / behavior | Default |
| --- | --- | --- |
| `sync.plex_to_trakt.watched_status` | `plex_to_trakt_watched` | true |
| `sync.trakt_to_plex.watched_status` | `trakt_to_plex_watched` | false |
| `sync.plex_to_trakt.ratings` | `ratings` AND `plex_to_trakt_ratings` | master false |
| `sync.trakt_to_plex.ratings` | `ratings` AND `trakt_to_plex_ratings` | master false |
| `sync.rating_priority` | `rating_priority`: none / plex / trakt | none |
| `sync.plex_to_trakt.watchlist` | `plex_to_trakt_watchlist` | false |
| `sync.trakt_to_plex.watchlist` | `trakt_to_plex_watchlist` | false |
| `sync.trakt_to_plex.watchlist_as_playlist` | `watchlist_as_playlist` (requires the preceding option) | false |
| `sync.trakt_to_plex.liked_lists` | `liked_lists` | false |
| `sync.trakt_to_plex.playback_status` | `trakt_to_plex_playback` | false |
| `liked_lists.keep_watched` | `liked_lists_keep_watched` | true |
| `liked_list.<name>.keep_watched` | `liked_list_overrides`: name + keep_watched entries | empty |
| `watch.ignore_clients` | `watch_ignore_clients`: Plex client identifiers | empty |
| `watch.username_filter` | Always enforced; other Plex users are excluded | true, locked |
| `watch.add_collection` | Permanently blocked | false, locked |
| `watch.remove_collection` | Permanently blocked | false, locked |
| `sync.plex_to_trakt.collection` | Permanently blocked | false, locked |
| `sync.plex_to_trakt.clear_collected` | Permanently blocked | false, locked |
| Trakt favorites / history deletion | No normal-sync write path; separately approved restore is independent | unchanged during sync |

The `ratings` master switch preserves compatibility with 0.1.0. When it is on,
the two independent direction switches take effect (both default to true, as in
0.1.0). `rating_priority: none` fills missing ratings while retaining existing
conflicts; plex/trakt priorities explicitly permit replacement on the other side.

## Optional watchlist/list/progress behavior

**Watchlist directions are real synchronization controls, not add-only export.**
Upstream may remove entries from the destination when only one direction is
enabled. With both enabled it combines the lists. The pinned upstream skips its
normal watchlist synchronization if the Plex watchlist is empty; this wrapper
preserves that behavior. Watchlist sync uses Plex Discover and can encounter
matching limitations. Its scope is the account watchlist, not the selected media
libraries. Keep both switches off for your original history-only plan.

`watchlist_as_playlist` takes effect only with `trakt_to_plex_watchlist`. It imports
the Trakt watchlist as a managed Plex playlist instead of editing the Plex online
watchlist (the pinned upstream imports movies only in this playlist mode).
`liked_lists` imports liked Trakt lists into managed Plex playlists;
it does not change Trakt favorites. These features can replace the contents of
Plex playlists managed by upstream. `liked_list_overrides` uses exact Trakt list
names, for example:

```yaml
liked_list_overrides:
  - name: "My Films"
    keep_watched: false
```

`trakt_to_plex_playback` overwrites Plex resume progress from Trakt. Upstream
marks an item watched when its Trakt progress is at least 99%, even when the
separate reverse watched-status switch is off. This side effect is shown in
the initial analysis warning.

The initial report includes effective switches and explicit warnings. Enabled
optional features are also passed through upstream's dry-run with HTTP writes
blocked. The report does **not** enumerate exact watchlist/playlist replacement
diffs or every resume offset; do not treat the watched-count report as a complete
preview of those optional features. Leave them off unless these effects are wanted.

Incremental playback-event jobs never synchronize global watchlists or playlists.
Those operations run only in a full/manual scheduled job. If using monitoring
without periodic full sync, global list options require manual full runs.
Upstream also disables liked-list and watchlist-playlist rebuilding during a
partial media walk: choose `sync_media: all` when using these playlist imports.

## Other supported controls

| App option | Purpose / upstream mapping | Default |
| --- | --- | --- |
| `plex_url`, `plex_username` | Server and exact token account | empty |
| `sync_enabled`, `sync_interval_minutes` | Periodic full sync, independently of monitoring | false / 60 |
| `watch_enabled` | Read-only upstream notification adapter; no direct scrobbles | false |
| `sync_media` | `all`, `movies` or `tv` library traversal | all |
| `include_libraries`, `exclude_libraries` | Per-server library selection; exclusion wins | empty |
| `ignore_ids` | Per-server `ignore_ids`: numeric Plex metadata IDs | empty |
| `plex_timeout` | Upstream `plex.timeout` and connection test, seconds | 30 |
| `request_timeout` | Trakt requests and device OAuth, seconds | 30 |
| `batch_delay` | Upstream worker batch timer, seconds; 0 disables delay | 5 |
| `movie_provider` | `xbmc-providers.movies`: imdb/tmdb for legacy XBMC IDs | imdb |
| `show_provider` | `xbmc-providers.shows`: tvdb/tmdb/imdb for legacy XBMC IDs | tvdb |
| `log_level` | Sanitized JSON operational log threshold | info |

## Deliberate boundaries

This is coverage of the App's supported **configuration**, not an unrestricted
front end for every upstream CLI command. Interactive console login, collection
clearing, arbitrary history deletion, IMDb import, self-update and raw scrobbling
are not exposed. They could bypass the App's intended data protection or versioned
update process. Rewatches do not create additional history entries in this adapter.

Terminal progress bars remain disabled in HA. Raw upstream debug logs and its
logger/file/filter knobs are intentionally not exposed because errors may contain
token-bearing URLs. Cache, config and log paths stay under `/data`; HTTP caching
is disabled to avoid stale watched-state decisions. Environment-file overrides
are disabled. Favorites, collection locks and username filtering cannot be
overridden through the settings API or an arbitrary upstream YAML block.

## Ingress navigation (0.3.0)

| Area | Controls |
| --- | --- |
| Verbindungen | Plex URL, username and write-only Plex/Trakt credentials, connection test and device OAuth |
| Synchronisierung | Timer, interval, event monitoring, watched/ratings/watchlist directions, priority, playlists, per-list exceptions and playback progress |
| Bibliotheken & Filter | Media scope, library include/exclude, ignored media IDs and clients |
| Erweitert | Plex/API timeouts, batch delay, metadata providers and log level |
| Analyse & Freigabe | Counts, chosen directions, risk notices, title lists, approval and manual sync |

The save bar applies validated settings immediately. A new analysis/approval is
required before further writes. Unsaved edits survive navigation and status
refreshes. Concurrent stale saves are rejected. Blank secret fields retain stored
values; replacing Trakt client credentials requires a new device authorization.

Upgrades retain `/data/pts/options.json` and credentials. On first start only,
legacy Supervisor options are imported if the persistent options file is absent.
Subsequent starts never overwrite Ingress settings from `/data/options.json`.

## Upgrade from 0.1.0

Missing new fields are merged with the safe defaults above. Tokens and files are
preserved, and the legacy ratings switch retains its old behavior. The expanded
configuration changes the approval fingerprint: perform another analysis and
explicitly approve before writes resume. No new optional write mode is enabled
by the migration.

## Backup settings are separate

All controls above govern normal synchronization. The **Sicherungen** workspace
has its own versioned settings, category scope, schedules and retention. A
separately previewed and explicitly approved restore can write selected Trakt
categories even if their normal sync is disabled. See [BACKUPS.md](BACKUPS.md).

## UI explanations and origin (0.4.1)

The sync directions, rating priority, watchlist-as-playlist, liked-list handling,
playback import, library filters, ignore IDs/clients, timeouts and XBMC providers
come from PlexTraktSync or its command-line/server configuration. The rating
master, Ingress UI, schedules, analysis/approval, protected HTTP policy and backup/
restore workspace are App additions. Our event trigger reuses upstream event
tracking but schedules guarded targeted sync instead of raw live scrobbling.

Watched status specifies WHAT may transfer; manual runs, intervals and events
specify WHEN. Playlist imports need a full library walk (media scope `all`);
targeted event jobs never rebuild account-wide playlists. Watchlist playlist
import handles locally available movies, while ordinary watchlists are account
level and can contain unavailable media. One-way ordinary watchlist sync mirrors
its source; two-way sync unions entries. A separate Plex-to-Trakt direction still
uses the Plex Watchlist, even when reverse import targets a playlist. Upstream
skips ordinary watchlist sync if the Plex Watchlist is empty.

Liked lists are entire Trakt lists the user liked, not individual media favorites.
Matching local media become managed Plex playlists; playlist rebuilding may
replace manual playlist edits, without modifying the Trakt source list. The
keep-watched default and per-name overrides control inclusion of seen items.

`xbmc-providers` only resolves IDs from legacy `xbmcnfo`/`xbmcnfotv` agents to
IMDb/TMDb/TheTVDB. It is not a metadata refresh or Plex agent setting; modern
Plex agent IDs normally do not use this mapping.

Library selection loads film/series section names after checking the token's
Plex account. Empty include selection means all; explicit exclusions win.
Unknown saved names remain visible after loading and can be edited offline.
Changing filters still requires a fresh analysis/approval. Secrets remain stored
server-side; empty replacement fields never clear them or reload their contents.
