# Automated checks and acceptance boundaries

The App currently has 119 Python tests. They run automatically on relevant
pushes and pull requests in `validate-plextraktsync.yml`, followed by native
amd64/aarch64 container builds and startup/restart smoke tests.

| Area | Automated coverage | What it does not establish |
| --- | --- | --- |
| Settings and credentials | Type/range validation, all option types, persistence, stale tabs, writer locks, write-only secrets and blank replacements | Browser rendering or actual account credentials |
| Sync options | Upstream setting coverage, direction/master mapping, immutable policy and worker boundaries | Correct matching of every item in a real library |
| Events and scheduling | User/session filters, debouncing, reconnect/backoff, approval and writer exclusion | Notifications from every Plex server/client version |
| HTTP and Ingress | Real local HTTP routes, trusted source restriction, CSRF, static allowlist and error boundaries | Full Home Assistant Supervisor proxy behavior |
| Library loading | Movie/show selection, account mismatch rejected before section access, secret redaction | Availability/permissions of the user's real Plex server |
| Backups | Supported categories, checksums/import validation, storage failures, quota, retention, pins, schedules, DST and restart | Trakt service availability and all possible remote account datasets |
| Restore | Merge/overwrite/mirror, multiset history, preview expiry/account binding, rollback-before-write, ambiguous failures, cancellation and post-verification | Atomic remote changes: Trakt offers no cross-endpoint transaction |
| Packaging | Native container builds, real process startup, source restrictions, stop/restart and persistent settings/archives/timezone data | Installation/upgrades on every HAOS/Supervisor release |
| Frontend | JavaScript syntax in CI; scripted browser QA during development | A committed continuous browser E2E suite is not yet present |

Run the backend suite from the repository root with the pinned PlexTraktSync
dependency installed:

```sh
python -m unittest discover -s PlexTraktSync/tests -v
python PlexTraktSync/scripts/upstream.py check
node --check PlexTraktSync/app/ui.js
node --check PlexTraktSync/app/backups-ui.js
```

The Windows development runtime without IANA timezone data skips one DST test;
Linux CI includes timezone data and must run it. Most external Plex/Trakt behavior
uses fixtures or mocked clients. These tests never prove that real remote writes
succeeded and do not need production credentials.

Scripted browser acceptance should cover navigation, desktop/mobile layout,
drawer keyboard behavior, dependent controls, save/discard/reload, failure/retry,
backup selection and restore confirmation. A future committed browser E2E suite
can run these flows against an isolated fixture server without credentials.

Live acceptance remains separate: use disposable Plex/Trakt accounts and known
test media to verify upstream matching, OAuth, events, watchlist/playlist behavior
and each supported restore category. HAOS acceptance must also verify Ingress,
installation, upgrades and persistent storage. Never enable destructive live
restore tests against a production account as part of ordinary CI.
