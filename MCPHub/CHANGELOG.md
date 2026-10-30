# Changelog

## v2026.10.31

### Added

- Optional unofficial Home Assistant MCP server (ha-mcp), started by the App and
  added to MCPHub as `ha-home-assistant-unofficial`. Off by default.

### Changed

- The existing configuration section is now named Home Assistant MCP (official).

## v2026.10.29-1

### Changed

- Updated MCPHub from 1.1.10 to 1.1.13.

## v2026.10.29

### Fixed

- Remove obsolete `cloudflare` and `tailscale` option groups from Supervisor storage on startup to prevent schema warnings after upgrading from the bundled remote-access implementation.
- Use a self-contained constant-time check for the Home Assistant Ingress proxy secret instead of an internal MCPHub helper that newer MCPHub releases removed (sign-in failed with HTTP 500 on MCPHub 1.1.13).

## v2026.10.24-1

### Changed

- Replaced the store wordmark with a transparent MCPHub symbol and enlarged the symbol by 30% in the store icon and app-page logo.
- Removed the experimental designation; MCPHub is now listed as stable. Development-store builds remain experimental.
- Updated bundled OpenAI tunnel-client v0.0.16 to v0.0.17.
- Updated MCPHub from 1.1.7 to 1.1.8.
- Updated MCPHub from 1.1.8 to 1.1.9.
- Updated MCPHub from 1.1.9 to 1.1.10.
- Updated bundled OpenAI tunnel-client v0.0.17 to v0.0.18.

## v2026.10.20-1

### Changed

- Updated MCPHub from 1.1.6 to 1.1.7.

## v2026.10.20

All changes since the previous stable release v2026.10.07-4.

### Breaking changes

- The bundled Cloudflare tunnel is removed. Cloudflare and Tailscale now run in their own Home Assistant Apps ([Cloudflared](https://my.home-assistant.io/redirect/supervisor_addon/?addon=396f0234_cloudflared&repository_url=https%3A%2F%2Fgithub.com%2Fhomeassistant-apps%2Frepository), [Tailscale](https://my.home-assistant.io/redirect/supervisor_addon/?addon=a0d7b954_tailscale&repository_url=https%3A%2F%2Fgithub.com%2Fhassio-addons%2Frepository)) and forward to MCPHub's MCP gateway on port `3001`. The options `cloudflare_tunnel_enabled`, `cloudflare_tunnel_token`, `cloudflare_mcp_path` and `cloudflare_access_token` are ignored, and the old Cloudflare credentials are deleted on start. Remote clients use a normal MCPHub bearer key. See **Remote access** in the documentation.
- App settings are grouped into sections (OpenAI, Remote access, Home Assistant MCP, GitHub CLI, Logging). Existing values are still read and saved credentials are kept, but Home Assistant may show the new fields empty. Check the settings after updating.

### Added

- **Remote access page:** a new **Remote access** button in MCPHub's top bar (Home Assistant Ingress only) opens a page to start, stop and reload the OpenAI Secure Tunnel without restarting MCPHub, with status, plain-language diagnostics and redacted live logs. It also shows the state of the Cloudflared and Tailscale Apps, links to install or open them, provides ready-to-copy setup text and checks your external address end to end.
- **MCP gateway on port 3001:** LAN clients and the Cloudflared and Tailscale Apps reach MCPHub's `/mcp` endpoints with an MCPHub bearer key. The web interface, login and management API are never reachable through it. Leave the host port blank to disable it.
- **Base URL for MCP clients** (`external_url`): MCPHub uses this address for **Copy client config**, so copied configurations work from outside Home Assistant.
- **Home Assistant MCP:** optional bridge that adds Home Assistant's MCP Server to MCPHub, with Supervisor-token or dedicated-user authentication, a configurable server name, and support for LAN IPs, IPv6, custom ports, HTTPS and private CA files.
- The OpenAI Secure Tunnel is supervised with liveness and readiness checks, automatic restarts with backoff, and remembers **Start**/**Stop** across App restarts. The App option remains the permission gate.
- Home Assistant watchdog for MCPHub's health endpoint.

### Changed

- Updated MCPHub from 1.1.1 to 1.1.6 and the OpenAI tunnel client from v0.0.15 to v0.0.16.
- The App description shows the bundled MCPHub version.
- Shorter configuration texts in English and German, with direct links to the OpenAI API key and Tunnels pages.
- Hot backups: MCPHub keeps running during backups, and re-downloadable package caches are skipped.
- OpenAI tunnel output is also written, redacted, to the Home Assistant App log.

### Fixed

- Invalid or failing OpenAI tunnel settings, including an invalid Tunnel ID, no longer stop MCPHub or Home Assistant Ingress.
- An existing GitHub CLI token is kept when its option is empty or the integration is disabled.

### Security

- Home Assistant MCP connections verify HTTPS certificates and hostnames; plain HTTP on the LAN still works.
- The Home Assistant MCP bridge listens on loopback only and never exposes the Home Assistant token in MCPHub.
- Tunnel controls are available only through Home Assistant Ingress, and their status never contains credentials.
- MCP gateways forward only normalized request paths and reject unsafe dot-segment routes.

### Upgrade notes

- If you used the bundled Cloudflare tunnel: install the Cloudflared App, point the hostname to `http://<Home Assistant IP>:3001`, set **Base URL for MCP clients**, and give your clients an MCPHub bearer key. The **Remote access** page shows the exact entry to copy.
- After updating, open **Settings → Apps → MCPHub → Configuration** once and check the OpenAI, Home Assistant MCP and GitHub sections.

## v2026.10.07-4

### Changed

- Updated MCPHub from 1.1.0 to 1.1.1.
- Moved the OpenAI Tunnel log-level option to the end of the Home Assistant App configuration.

### Fixed

- Fixed Home Assistant Ingress SSO falling back to MCPHub's local login when optional Supervisor user-name headers are unavailable.

## v2026.10.07-3

### Fixed

- Fixed Home Assistant Ingress-created MCP servers being stored with a synthetic Home Assistant username instead of the MCPHub `admin` owner.
- Existing affected servers can be repaired by saving them again through Home Assistant Ingress.

## v2026.10.07-2

### Fixed

- Fixed `ha-github-cli` startup failures caused by an incompatible MCP Python SDK version.
- Pinned the compatible MCP Python SDK runtime to 1.30.0.

### Changed

- Bundled `gh-cli-mcp-server` and its compatible MCP Python SDK in the App image instead of resolving them when the server starts.

## v2026.10.07-1

### Fixed

- Fixed `ha-github-cli` failing to start because the GitHub CLI runtime bootstrap used invalid release-asset checksums.

### Changed

- Bundled GitHub CLI 2.101.0 in the App image instead of downloading it at runtime.

## v2026.10.07

### Added

- Added an optional managed GitHub CLI MCP server named `ha-github-cli`.
- Added GitHub token handling through `/data/secrets/github_token` instead of storing the token in MCPHub settings.

### Changed

- Disabling the GitHub CLI MCP option removes only the App-managed `ha-github-cli` server and leaves user-managed GitHub servers untouched.

## v2026.10.05

### Added

- Added Home Assistant Ingress single sign-on.
- Added optional Cloudflare Tunnel support with a dedicated MCP route and remote-client access key.

### Changed

- Switched MCPHub App releases to CalVer using `vYYYY.MM.DD`, with same-day releases using numeric suffixes.
- Kept MCPHub dashboard and API authentication enabled while mapping authenticated Home Assistant users through Ingress.
- Scoped internal OpenAI and Cloudflare access keys to the configured MCP route where possible.

### Security

- Home Assistant identity headers are accepted only together with the private per-installation Ingress proxy secret.
- Cloudflare removes Home Assistant identity headers and exposes only the configured MCP route.
- Cloudflare connector tokens are passed through a protected token file instead of the process command line.

## v0.2.0

### Added

- Added MCPHub 1.1.0 as the central MCP gateway and control plane.
- Added Home Assistant Ingress support.
- Added optional OpenAI Secure MCP Tunnel support.
- Added persistent MCPHub configuration and package caches.
- Added English and German Home Assistant option translations.

### Changed

- Moved MCPHub into the shared HyperCriSiS Home Assistant Apps repository.
- Simplified the visible App name to MCPHub and the technical slug to `mcphub`.
- Switched to building the Home Assistant App directly from this repository.

### Security

- MCPHub runs without the Docker socket, privileged mode, host networking, Supervisor API access, or Home Assistant API access.
- MCP transport bearer authentication remains enabled when dashboard authentication is delegated to Home Assistant Ingress.
