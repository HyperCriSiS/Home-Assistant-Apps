# Changelog

## v2026.11.09

### Changed

- Updated Trilium from v0.106.1 to v0.107.0. Text notes can now compose blocks from other notes, tables support merged cells and sorting, the shared pages and the mobile layout were redesigned, and AI tool calls ask for permission before reading or changing notes. See the [upstream release notes](https://github.com/TriliumNext/Trilium/releases/tag/v0.107.0).
- The sync protocol moves from 39 to 41. Desktop and mobile clients that sync with this App must be updated to v0.107.0 as well, otherwise sync stops until they match.
- The database version moves from 240 to 242. Trilium migrates the database on the first start after the update and writes `backup/backup-before-migration.db` into the App data first. An earlier Trilium version cannot open the migrated database, so a rollback means restoring the Home Assistant backup taken before the update.

### Breaking

- The old layout was removed upstream.
- Multi-level `#sorted` values need a `#` prefix on each name, for example `#sorted="#priority desc, #dueDate"`.
- ETAPI login requires a TOTP code when TOTP is enabled, and adding a new sync device requires TOTP if one is set.

### Fixed

- Upstream fixes include lost note modifications during sync, failing searches in protected notes on synced instances, and OIDC login behind some reverse proxies.

## v2026.11.08

Trilium itself stays at v0.106.1.

### Changed

- The App now installs a prebuilt image from `ghcr.io/hypercrisis/{arch}-trilium` instead of building it on the Home Assistant host. Updates and restores are faster, and existing installations switch on the next update.
- Home Assistant backups of the App are significantly smaller. The Supervisor no longer stores the container image (about 170 MB compressed) inside every backup; only the Trilium data is included. The automatic backup taken right before updating to this version still contains the old locally built image once.

## v2026.11.05

Trilium itself stays at v0.106.1.

### Changed

- The host port `8080` is no longer published by default on new installations. Direct access bypasses Home Assistant authentication, and the setup wizard is open until the first login. Existing installations keep their network settings; the port can still be enabled in the App's network configuration.

### Fixed

- The `timezone` and `log_retention_days` options never took effect: Home Assistant passes `environment` values to the container literally, so Trilium received the placeholder text and fell back to its 90 day default, while the Supervisor always sets `TZ` to the Home Assistant system timezone. Both options are now deprecated and no longer shown as active settings; existing values are ignored.

## v2026.10.24

### Changed

- Updated Trilium from v0.106.0 to v0.106.1.

## v2026.10.18

Trilium itself stays at v0.106.0. This release improves backup reliability, configuration and documentation.

### Fixed

- Home Assistant backups now capture a consistent Trilium database. The App uses cold backups, so Home Assistant stops Trilium while the backup is created and starts it again automatically afterwards. Previously a backup taken while Trilium was writing could contain an incomplete SQLite database.

### Added

- English and German names and descriptions for all configuration options and for port `8080` in the Home Assistant interface.
- Status, Trilium version, architecture and license badges in the README.

### Changed

- The App's website link in Home Assistant now opens the Trilium Notes App page instead of the repository root.
- The README now uses the term "App" consistently and explains how to disable the optional direct port `8080`.

### Maintenance

- Automated Trilium updates now also update the README version badge and never leave partially updated files behind.
- CI runs only for Trilium-related changes, validates backups, translations and the version badge, and installs test dependencies from a lockfile.

## v2026.10.11

### Changed

- Updated Trilium from v0.105.0 to v0.106.0.

## v2026.09.21

### Fixed

- Fixed Home Assistant Ingress requests triggering `ERR_ERL_UNEXPECTED_X_FORWARDED_FOR`.
- Restricted trusted reverse-proxy handling to the Home Assistant Ingress proxy at `172.30.32.2`.

### Security

- Removed permissive reverse-proxy trust so forwarded client addresses cannot be accepted from arbitrary sources.

## v2026.09.07

### Changed

- Updated Trilium to v0.105.0.
- Trilium's ARM64 image now uses Debian 13 and requires a host with sufficiently recent `libseccomp` support.

## v2026.07.26

### Added

- Added a Home Assistant TCP watchdog for automatic service supervision.

### Changed

- Updated Trilium to v0.104.1.
- Switched to Trilium's upstream startup command and health check.
- Updated the Trilium environment configuration for host, port, trusted reverse proxy, and log retention.
- Deprecated the non-functional `log_level` and `https_only` options while retaining compatibility with existing installations.

## v2026.07.07

### Changed

- Updated Trilium to v0.103.0.

## v2025.11.30

### Changed

- Updated Trilium to v0.99.5.
- Renamed the Home Assistant App to Trilium Notes.

### Fixed

- Fixed the Trilium startup parameters.

## v2025.09.22

### Fixed

- Fixed Trilium startup and health-check handling.

## v2025.09.17

### Changed

- Updated Trilium to v0.98.1.

## v2025.03.13

### Added

- Added timezone and log-level configuration options.

### Changed

- Updated the Trilium Notes branding and logo.

### Fixed

- Fixed inconsistent Trilium naming across the Home Assistant App files.

## v2025.03.12

### Added

- Initial Home Assistant App release.
