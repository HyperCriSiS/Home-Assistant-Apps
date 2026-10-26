# Changelog

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
