# Development status — 2026-10-26

This file records the current task's handoff, not a replacement repository roadmap.

## Implemented locally

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
- Docker/HAOS execution has **not** been performed. No live Plex/Trakt data was
  read or written, and no secrets were supplied to tests.

## Publication and environment status

- The GitHub MCP connection was rechecked successfully after the user's permission
  change. `dev-plextraktsync` now exists on the intended Home-Assistant-Apps repository.
- Publishing uses the connected GitHub tools. The desktop checkout's `.git` is
  read-only in this execution environment; its existing MCPHub branch is preserved.
- Docker/HAOS image execution has not been verified. No stable release or completed
  HAOS acceptance is claimed. The generated Dev-Store needs separate shared
  infrastructure review on `main`; it is never edited directly.

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
4. Validate update proposal and manual release workflows on GitHub; actionlint
   is not installed locally and no remote workflow run is available.
5. Review the development candidate and the separate shared Dev-Store infrastructure
   PR before any `main` merge. The App remains experimental until acceptance passes.
6. Run both native builds and real container checks, then disposable HAOS install,
   Ingress, restart and backup/restore acceptance. Verify architecture support.
7. With explicit user approval only, run live-account write acceptance, including
   unchanged collection/watchlist/favorites and preservation of watched timestamps.
8. Publish via the generator, attach PR to the chat and report verified URLs.
   Stable promotion is a later manual decision after all acceptance gates pass.
