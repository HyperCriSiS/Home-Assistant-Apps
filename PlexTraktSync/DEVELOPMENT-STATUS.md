# Development status — 2026-10-26

This file records the current task's handoff, not a replacement repository roadmap.

## Published development candidate

- Dedicated local `dev-plextraktsync` baseline and feature branch.
- Experimental App metadata, version-pinned upstream installation, unprivileged runtime.
- Ingress panel, account-token connection test, Trakt device OAuth with persistent
  pytrakt-compatible credentials, interval/expiry/rate-limit handling.
- Read-only library analysis, report-bound approval and invalidation on changes.
- Periodic/manual scheduling, one writer, bounded jobs, pause, persistent status.
- Read-only upstream playback listener, session/user binding, coalesced targeted
  jobs, reconnect backoff and shared single-writer execution.
- Independent library inventory including unresolved/skipped episodes and
  show-level rating conflicts; structured sanitized logs with persistent errors.
- Wheel checksum verification and stable update draft PRs; manual draft release
  integration in the existing promotion workflow.
- Immutable collection/watchlist/list policy, HTTP write guard, preview Plex GET
  mutation guard, account-identity validation, ambiguous ID-match rejection.
- Proposed shared generator/base-sync changes; independent four-App revision test.
- Proposed amd64/aarch64 build and real container stop/restart CI workflow.
- Setup, attribution and operational limitations documented.

## Validation evidence

- 45 App unit, HTTP, OAuth refresh, notification and pinned-upstream contract tests
  pass locally on Python 3.14.
- Existing repository automation suite: 56 tests pass, including the extended
  generated Dev-Store test.
- Changed YAML files pass yamllint 1.37.1; Git whitespace checks pass.
- GitHub validation passed on source commit `ea882d7745ffd476a0b75e5cb4ff7aaf06761792`:
  native amd64/aarch64 builds and real container startup, source restriction,
  clean stop and persistent restart checks. Evidence:
  https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/40348133083
- GitHub YAML/Actions lint and repository automation tests passed for that commit.
- Real HAOS/Supervisor acceptance is still pending. No production Plex/Trakt data
  was read or written; tests use fixture credentials only.

## Publication and environment status

- The GitHub MCP connection was rechecked successfully after the user's permission
  change. `dev-plextraktsync` now exists on the intended Home-Assistant-Apps repository.
- Publishing uses the connected GitHub tools. The desktop checkout's `.git` is
  read-only in this execution environment; its existing MCPHub branch is preserved.
- Development review: https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/112
- Separate Dev-Store infrastructure: https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/113
- Native container checks passed. No stable release or completed HAOS acceptance
  is claimed. The generated Dev-Store needs PR #113 reviewed and merged on `main`;
  it is never edited directly.

## Required remaining work

1. Perform end-to-end playback acceptance against disposable Plex/Trakt fixtures:
   reconnects, real sessions permission responses, overlapping manual/periodic
   triggers and library changes. Current monitoring intentionally synchronizes
   missing watched state; it does not expose direct scrobbling or add history
   entries for each rewatch. This limitation is documented in the UI and DOCS.
2. Validate large-library traversal completeness, partial API failure boundaries
   and mutable-library snapshots against an actual server.
3. Verify state/backup migration and actual Supervisor Ingress on HAOS. HTTP,
   CSRF, token-refresh, device-denial and fail-closed version fixtures pass locally.
4. Exercise the scheduled upstream update and manual promotion workflows.
   GitHub validation and actionlint passed; actual update PR creation remains
   a separate runtime acceptance check.
5. Review the development candidate and the separate shared Dev-Store infrastructure
   PR before any `main` merge. The App remains experimental until acceptance passes.
6. Native builds and container restart checks passed on amd64/aarch64. Next run
   disposable HAOS install, Ingress, restart and backup/restore acceptance.
7. With explicit user approval only, run live-account write acceptance, including
   unchanged collection/watchlist/favorites and preservation of watched timestamps.
8. Publish via the generator, attach PR to the chat and report verified URLs.
   Stable promotion is a later manual decision after all acceptance gates pass.

## App 0.2.0 configuration expansion

- Native configuration now exposes all supported upstream sync flags except the
  permanently locked collection flags. Watch settings map ignored clients while
  username filtering stays mandatory and terminal progress bars remain disabled.
- Optional watchlist directions, Plex playlist imports, list overrides and reverse
  playback progress default off. Independent rating directions retain the legacy
  master switch. Scope, ignored IDs, timeouts, batch delay and XBMC providers are
  configurable. Every option has English/German labels and descriptions.
- HTTP policy allows only explicitly enabled directions, keeps collection/favorites
  blocked, and disables global list writes in playback-event jobs. Preview also
  blocks Plex GET progress writes. Additional write effects are disclosed in OPTIONS.md.
- Missing fields migrate to safe defaults without deleting tokens; old approval
  fingerprints become invalid. 58 App/security/migration tests pass locally. YAML and upstream-pin checks pass. Native CI for this
  revision must be checked separately from the earlier 0.1.0 evidence above.
