# Changelog

## 0.3.1

- Remove the prominent personal favorite-archive messaging from the overview and
  sidebar. Describe excluded Trakt changes in a collapsed synchronization detail;
  SeriesGuide favorites are unrelated. Synchronization policy is unchanged.

## 0.3.0

- Move all 29 settings into a dark Ingress interface with desktop sidebar and
  mobile menu: overview, connections, synchronization, libraries/filters,
  advanced options and analysis/approval. Replace raw JSON with status cards,
  readable reports, switches, selectors and a per-list exception editor.
- Apply settings without restarting, retain unsaved edits while polling,
  validate on the server, reject stale saves from other sessions and refuse
  configuration changes during active jobs. Secrets remain write-only.
- Preserve existing options and tokens; import Supervisor options only once.
  Disable the native HA settings form. Changes revoke previous analysis/approval.
- Add settings API, security and persistence regression tests, strict static
  asset routing/CSP and container restart coverage for Ingress-saved settings.

## 0.2.0

- Expose independent rating directions, optional watchlist directions and playlist
  import, liked-list keep-watched overrides and Trakt-to-Plex playback progress.
- Add movie/TV scope, ignored Plex IDs and clients, connection/request timeouts,
  batch delay and legacy XBMC provider selection.
- Preserve permanent collection/favorites protection and username filtering.
  Optional writes require the selected direction and renewed analysis/approval;
  event-driven jobs cannot replace global lists or playlists.
- Add safe migration of missing fields, option documentation, native translations,
  upstream option-coverage and directional write-policy tests.

## 0.1.0

- Initial source candidate: protected configuration, Ingress device onboarding,
  read-only analysis and explicit first-write approval, single-writer scheduling.
- Mock and pinned-upstream contract tests; proposed native container CI checks.
- Read-only playback event adapter with upstream session validation, targeted
  single-writer jobs, reconnect backoff and protected Trakt write endpoints.
- Independent library inventory and show-rating conflict analysis; skipped
  upstream traversal items are reported explicitly.
- Wheel checksum verification, draft upstream update proposals and manual
  release integration; structured sanitized logs and Ingress/OAuth tests.
- Docker/HAOS acceptance and publication remain outstanding. Playback monitoring
  fills missing watched state and does not record every rewatch. This is not a stable release.
