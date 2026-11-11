# Changelog

## v2026.11.11

### Changed

- Updated Inbox Zero from a08ec63 to 4d08657 (v2.30.0).

## v2026.11.09

### Added

- First release. Packages the [Inbox Zero fork](https://github.com/HyperCriSiS/inbox-zero) with IMAP/SMTP and CalDAV support at commit `a08ec63`, based on upstream v2.30.0.
- PostgreSQL 16, Redis, the Redis HTTP adapter and the scheduler for polling, digests and cleanup run inside the App.
- Secrets are generated on the first start and kept in the App data.
