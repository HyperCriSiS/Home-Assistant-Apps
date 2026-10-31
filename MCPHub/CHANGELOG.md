# Changelog

## v2026.10.31-1

### Added

- Optional unofficial Home Assistant MCP server (ha-mcp), started by the App and added to MCPHub as `HomeAssistant MCP (unofficial)`. Off by default. The name can be changed with `ha_mcp_server_name`.

### Changed

- Updated MCPHub from 1.1.10 to 1.1.15.
- The existing configuration section is now named Home Assistant MCP (official).
- The official server is now named `HomeAssistant MCP (official)` in MCPHub. Installations using the old default `ha-home-assistant` are renamed automatically; update MCPHub groups or clients that reference the old name. Custom names stay unchanged.
- Updated bundled OpenAI tunnel-client v0.0.18 to v0.0.19.

### Fixed

- Remove obsolete `cloudflare` and `tailscale` option groups from Supervisor storage on startup to prevent schema warnings after upgrading from the bundled remote-access implementation.
- Use a self-contained constant-time check for the Home Assistant Ingress proxy secret instead of an internal MCPHub helper that newer MCPHub releases removed (sign-in failed with HTTP 500 on MCPHub 1.1.13).

## v2026.10.24-1

### Commits in this Dev build

- [`0ed4f8a`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/0ed4f8ae89cceb994bd2c525200e42fd2af2c5c2) feat(mcphub): configurable ha-mcp name and official name migration (#131)
