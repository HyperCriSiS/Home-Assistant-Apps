# Trakt backups and restore

The Ingress **Sicherungen** workspace provides independent archives, schedules,
retention and explicit restore. Backup settings are separate from sync options:
you can back up a category even if its synchronization is disabled. Automatic
backups are off until configured. Normal sync's collection/favorites guards are
unchanged; a separately previewed and approved restore can change selected Trakt
categories, including collection/favorites and removal of surplus history.

## Supported scope

| Category | Archive | Restore |
| --- | --- | --- |
| Watched history | Individual movie/episode plays, UTC timestamps, event IDs | Adds missing plays; mirror removes surplus events by their current IDs |
| Ratings | Movies, shows, seasons, episodes, rating timestamps | Preserve conflicts or apply backed-up ratings |
| Watchlist | Supported media, notes, order | Membership, notes, order |
| Trakt favorites | Movies/shows, notes, order | Membership, notes, order |
| Collection | Movies and individual collected episodes, dates and supported media metadata | Exact episode selection; never infer all episodes from a show ID |
| Personal lists | Names, descriptions, visibility, item order and notes | Create missing lists, merge/overwrite items, optionally delete surplus personal lists |
| Hidden media | Calendar, watched/collection progress and recommendations | Membership by section |
| Playback progress | Available positions and paused timestamps | Archive only; no equivalent direct restore endpoint |

“All” means all supported categories in this table, not a bit-for-bit account
image. Social relationships, comments, general notes, account settings,
collaboration lists and newer specialized favorite scopes are outside this format.
Trakt assigns new event/list-item IDs and insertion times on import. Original
scrobble origins cannot be recreated. History preserves the number of plays,
including plays with identical timestamps, using UTC-normalized multiset matching.
The normal sync adapter still does not create extra rewatch entries.

## Manual archives, downloads and import

1. Open **Sicherungen → Archive**, choose one or more categories, then **Jetzt sichern**.
2. A successful snapshot is written as a versioned ZIP with JSON category files
   and SHA-256 checksums. A temporary file is verified before atomic publication.
3. Download ZIP files for storage outside Home Assistant. Archive actions include
   integrity checking, pin/unpin and deletion with a typed confirmation.
4. Import accepts this App's archive format, not arbitrary Trakt web/GDPR ZIPs.
   Uploaded archives receive new local IDs and are initially pinned. Imports check
   structure, version, checksums, JSON and semantic media records without extraction.

Limits: 128 MiB compressed, 512 MiB uncompressed, known exact member names,
no duplicate ZIP entries/JSON keys, no encrypted members or arbitrary paths.
No credentials, access/refresh tokens, Plex tokens or client secrets are exported.
Archive contents include private viewing data and notes. ZIPs are not encrypted;
store downloaded copies appropriately. Files use owner-only permissions.

## Automatic operation

Up to 12 independently enabled schedules select categories, name, local wall time
and daily/weekly/monthly cadence or an interval of 1–8760 hours. Weekly schedules
select weekdays. Month days 29–31 clamp to the last day of shorter months.

The IANA timezone is explicit (initially UTC; choose e.g. Europe/Berlin).
Daily calendar jobs run once across the repeated autumn hour. A nonexistent spring
time advances through the gap. Missed jobs run once after restart, without a
backfill storm. Due times and bounded retry counters persist across restarts.
Disabling the schedule master does not disable the separate pre-sync option.
Pausing sync does not stop independently enabled backup schedules.

Optional pre-sync snapshots have a minimum interval (default 1440 minutes; 0 means every run) and a
selected scope. A required snapshot failing blocks that sync rather than silently
writing without a backup. OAuth/account credential changes force a new snapshot.

Failed scheduled backups retry up to the configured count, with increasing
configured delays. Restore never retries automatically. GETs handle pagination
and bounded rate-limit/server retries; POST/PUT/DELETE are not replayed after an
ambiguous response. The client honors Retry-After and spaces writes by at least
1.1 seconds. Account activity changing during reads causes bounded recapture;
inconsistent or incomplete snapshots are not published.

## Retention and storage

Defaults combine the newest 10 archives plus one newest representative of the
last 14 represented days, 8 weeks, 12 months and 3 years. These are unions, not
additive quotas: one file can satisfy several tiers. Each account and exact
category set is handled independently, so a partial backup cannot displace the
last complete snapshot. Calendar buckets use the configured timezone.

An optional age cap affects historical tiers, while the newest minimum and pinned
archives are preserved. Manual/import archives are also retained when “keep manual”
is enabled. Pre-restore rollback archives start pinned and can be explicitly
unpinned later. Pinning always wins over automatic retention. Corrupt archives
remain visible and are not automatically pruned.

Saving settings does not delete archives. Successful new backups apply retention;
**Jetzt bereinigen** previews the number eligible under saved rules and requires
typed confirmation. Quotas never override protections. A full quota blocks further
ordinary backups with a clear error; users can increase space or explicitly free
unneeded files. Minimum free space and job timeouts are configurable.

## Restore workflow

1. Select an archive and one or more restorable categories.
2. Choose **merge** (only fill missing data), **overwrite** (apply backed-up values,
   keep extra entries), or **mirror** (remove surplus entries in selected categories).
   Overwrite can remove/re-add list/collection entries to apply metadata; these
   removals appear in the preview. History in overwrite mode still fills missing
   plays; only mirror deletes surplus plays.
3. Start a fresh read-only preview. Review counts, affected categories, title
   samples, visibility warnings and source/target account. Cross-account restore
   needs its own opt-in. Plans expire after 15 minutes and bind archive contents,
   current remote data, account identity and current App credentials/options.
4. Type the displayed confirmation word. The job rereads remote data and refuses
   stale plans. Before its first media write, it publishes a pinned rollback archive.
   A failed rollback save blocks all restore writes.
5. Sync is paused and old sync/restore approvals are revoked. The restore records
   a bounded durable journal before each request and after each confirmed response.
6. The job rereads selected data and checks remaining differences. Only a verified
   result is reported successful. A failure/cancellation/restart can leave confirmed
   partial changes; create a fresh preview rather than replaying the old plan.

Trakt has no transaction covering all endpoints. Other apps can still change data
between API calls; pausing our sync cannot lock the entire Trakt account. Trakt may
auto-remove watchlist items when history is added; history is therefore restored
before watchlists. API limits and missing catalogue items can prevent full restore.

Archives live at `/data/pts/backups`, settings at `backup-settings.json`, job/schedule
state at `backup-state.json`. HA cold backups include these persistent files.
Keep a downloaded/off-device copy as well. After restore, review Trakt, then perform
a new sync analysis and explicit approval before resuming normal synchronization.

## Validation boundary

Tests and browser QA use disposable Trakt fixtures only. Container checks verify
archive/settings persistence and IANA data on native amd64/aarch64. Actual Trakt
acceptance, HAOS upgrade/restore and large-account behavior remain required before
stable release. No production account writes are part of implementation testing.
