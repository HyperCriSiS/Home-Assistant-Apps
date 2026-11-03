# Changelog

## v2026.11.02

### Changed

- Install and update MCPHub using prebuilt `amd64` and `aarch64` images from GitHub Container Registry instead of building the App on the Home Assistant device. Bundled packages are installed and both container architectures are tested in CI before publication.
- Publish and verify development-store images before making their version available in the store. Additional dynamically installed MCP servers still use the persistent local package caches.

## v2026.10.31-1

### Commits in this Dev build

- [`80690ca`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/80690ca6edf22b5715ec8385ea01c5cf65cbd51e) chore: use the shared tested Calibre image gate for store updates (#152)
