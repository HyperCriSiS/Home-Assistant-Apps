# Development status — 2026-10-26

This is the current task handoff, not a replacement repository roadmap.

## App 0.4.1: configuration clarity and compact layout

- Removed redundant connection/slogan text; stored credentials are explicitly
  described as server-side values with empty replacement fields.
- Compact top bar/content without changing sidebar spacing. Wide layouts use
  two columns for connections, sync and advanced groups.
- Ratings directions and conflict priority disable/dim under the master switch;
  their values persist through save/reload and can be reactivated.
- Authenticated Plex connection checks return film/series library names for
  include/exclude checkboxes. Offline manual filters and absent saved names
  remain supported; account verification precedes section access.
- Added concrete explanations for event triggers, watchlist vs playlist, liked
  lists, immutable normal-sync rules, separate restore and legacy XBMC providers.
- Local verification: 119 tests, one Windows-only timezone-data skip; JavaScript,
  YAML and upstream pin validation pass. Fixture browser checks cover dependency
  toggling, save/reload, library loading/filter persistence and mobile overflow.
- Actual Plex/Trakt and HAOS acceptance is still pending.

## App 0.4.0: backup and restore workspace

- Implemented full/partial versioned ZIP archives for eight supported categories;
  seven categories can be restored. Playback positions are archive-only.
- Archive download/import, checksum verification, pins, filtering, explicit deletion,
  corrupt-archive visibility and independent backup configuration in dark Ingress.
- Up to 12 daily/weekly/monthly/interval schedules with IANA timezone handling,
  persisted due times, missed-run catch-up and bounded retries. Optional required
  pre-sync snapshots with a configurable minimum interval (including every run).
- Latest/daily/weekly/monthly/yearly retention, age caps, manual protection,
  storage/free-space limits and explicit cleanup preview/confirmation.
- Merge/overwrite/mirror restore with expiring account/data-bound plans, samples,
  typed approval, mandatory pinned rollback before writes, a bounded journal,
  post-verification and no automatic replay of ambiguous writes.
- Normal sync guards remain unchanged. Restore is separately approved and leaves
  sync paused pending a fresh read-only analysis and explicit sync approval.
- Local suite: 117 tests run; one DST test is skipped on the Windows runtime
  lacking IANA files. Linux CI requires that test and native containers verify
  Europe/Berlin data and archive/settings persistence. JavaScript/YAML/pin checks pass.
- Browser fixtures verified settings save/reload, complete backup, seven-category
  restore with rollback/post-verification, desktop and 390px mobile layouts, and
  no browser console errors. No real Plex/Trakt account data was read or written.
- See BACKUPS.md for exact scope and limitations. Archives are not encrypted and
  imports accept this App's format, not Trakt web/GDPR exports. Original internal
  IDs, insertion times and scrobble sources are not reproduced. Social/comment/
  general-note/account-settings and collaboration-list backup are outside scope.
- Actual Trakt/HAOS acceptance remains pending. The latest branch CI and PR #112
  record native build results; this is not a stable release or live deployment.

## Earlier 0.3.0 baseline

### Configuration in dark Ingress

- All 29 supported options moved into Ingress; the native HA configuration form
  is hidden. Desktop sidebar and mobile drawer provide overview, connections,
  synchronization, libraries/filters, advanced options and analysis/approval.
- Charcoal surfaces, amber accents, muted rose/teal connection states, readable
  analysis cards and title lists replace the former pale page and raw JSON.
- Settings apply immediately. Status polling preserves unsaved form edits;
  server validation, stale-tab rejection and the writer lock protect saves.
- Existing settings and credentials persist. Legacy Supervisor options are
  imported only if `/data/pts/options.json` is absent, never on subsequent starts.
- Secret values are write-only; blank fields retain credentials. Replacing Trakt
  client credentials requires renewed authorization. Settings changes revoke
  analysis/approval and stop the listener before persistence, including failures.
- Static assets use an explicit allowlist, same-origin CSP, no-store and nosniff.
  Ingress-source enforcement and per-process CSRF checks remain enabled.
- Collection, Trakt favorites, foreign-user filtering, watched-history policy,
  single-writer scheduling and the pinned upstream version remain protected.
- No production Plex/Trakt data was accessed and no HA installation was changed.

## Verified locally

- 69 App tests pass on Python 3.14: policy, upstream contracts, workers, event
  monitoring, OAuth, real HTTP/CSRF routes, all option types, validation without
  side effects, stale/busy saves, secret redaction, restart and disk-failure cases.
- JavaScript syntax, YAML formatting and upstream pin checks pass.
- Browser QA against an isolated local preview: all 29 settings present,
  navigation, save/reload, rating switch, per-list override, invalid URL feedback,
  and responsive desktop/mobile layouts. No horizontal overflow at 390px and
  1280px viewport sizes. Preview uses temporary files and no scheduler/accounts.
- Container smoke checks now verify that Ingress-saved settings and credentials
  survive restart without being replaced by Supervisor's older option values.
  The latest GitHub run is the authority for native amd64/aarch64 results.

## Development publication

- App branch: `dev-plextraktsync`.
- App review: https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/112
- Native checks: https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-plextraktsync.yml
- Previous 0.2.0 candidate passed native amd64/aarch64 build/start/stop/restart:
  https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/40361937573
- Separate shared Dev-Store infrastructure review:
  https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/113
- The generated Dev-Store is never edited directly. Its generator changes need
  separate review before they become active from `main`. No stable release is claimed.
- Publication uses the connected GitHub tools; unrelated local MCPHub work is preserved.

## Remaining acceptance

1. Actual HAOS install, Supervisor Ingress, upgrade, restart and backup/restore.
2. Disposable Plex/Trakt fixtures for real sessions, reconnects, overlapping
   triggers, large-library matching and partial API failures.
3. Verify optional watchlist/playlist/progress behavior against disposable data;
   exact replacement diffs are not exposed by upstream preview.
4. Exercise scheduled upstream update proposals and manual promotion workflows.
5. Review App and Dev-Store infrastructure PRs before any stable promotion.
6. Only with explicit approval, perform live-account write acceptance.

Monitoring synchronizes missing watched state, without direct scrobbling or an
additional history entry for every rewatch. This remains an experimental candidate.
