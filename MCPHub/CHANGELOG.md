# Changelog

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

### Commits in this Dev build

- [`292436b`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/292436b825b1576844158f6aa50f2e1ae17da5c5) feat(mcphub): consolidated stable changelog for v2026.10.20 (#88)
