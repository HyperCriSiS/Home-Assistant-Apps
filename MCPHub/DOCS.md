# MCPHub documentation

## About

This add-on runs MCPHub as a central control plane for MCP servers inside Home Assistant.

MCPHub can discover, configure, start, stop, group, monitor, and route multiple MCP
servers while exposing them through stable MCP endpoints.

A managed Home Assistant MCP bridge is also available. It can connect MCPHub
back to Home Assistant's own MCP Server without storing the Home Assistant
credential in MCPHub.

MCP clients reach MCPHub in these ways:

- **LAN:** the MCP-only gateway on port 3001, with an MCPHub bearer key
- **OpenAI Secure MCP Tunnel** for ChatGPT and supported OpenAI clients, built in
- **Cloudflare or Tailscale** for Claude, Cursor, VS Code, and other remote MCP
  clients, through the separate Cloudflared or Tailscale App, which forward to
  the same MCP-only gateway

All remote access is optional; the methods can be combined.

## Installation

Add this repository to the Home Assistant App store:

`https://github.com/HyperCriSiS/Home-Assistant-Apps`

Install **MCPHub** and start it with the default configuration first. Remote access is
disabled by default so the dashboard can be verified independently.

## First start

1. Start **MCPHub**.
2. Open **Web UI** from the Home Assistant App page.
3. Use MCPHub's **Market**, **Registry**, or **Add Server** flow to configure MCP servers.
4. Create focused groups for the tools each external client actually needs.
5. Verify that the selected servers connect successfully.
6. Enable remote access only after MCPHub is working locally.

No additional MCPHub dashboard login is required. Home Assistant Ingress authenticates
the Home Assistant user. Supervisor-provided `X-Remote-User-Id`,
`X-Remote-User-Name`, and `X-Remote-User-Display-Name` headers are then mapped
into MCPHub's request user context.

The App accepts those identity headers only when the trusted local Ingress adapter also
supplies a private per-installation proxy secret. Remote tunnel traffic cannot set or
reuse this trust marker.

The Home Assistant panel is configured with `panel_admin: true`. Because only
Home Assistant administrators are intended to enter this Ingress panel, trusted Ingress
identities are mapped to MCPHub administrators. The CI metadata checks enforce that
`panel_admin` remains enabled while this mapping is in use.

## Limit which tools a client receives

MCPHub groups are the preferred way to avoid exposing every MCP server and tool to every
client.

Examples:

- `/mcp/development`
- `/mcp/home`
- `/mcp/web`

A client connected to a group endpoint only discovers tools from servers in that group.

Both OpenAI and Cloudflare have their own route option, so they can expose different
groups at the same time.

Smart Routing is also supported by MCPHub through `/mcp/$smart`, but it requires
additional PostgreSQL/pgvector and embedding-service setup. This Home Assistant wrapper
does not automatically enable that extra infrastructure.

## Home Assistant MCP Server

The wrapper registers its managed MCPHub server under
`home_assistant_mcp_server_name` (default: `ha-home-assistant`). When enabled,
MCPHub connects to a loopback-only Nginx
bridge on `127.0.0.1:8097`; that bridge forwards Streamable HTTP requests to
Home Assistant and injects the selected Home Assistant credential.

The Home Assistant **MCP Server** integration must already be configured. The
wrapper intentionally does not create Home Assistant users, authentication
entries, or config entries through undocumented internal APIs.

### Authentication mode: `restricted_user` (default)

Use this mode when MCP requests should run as a dedicated Home Assistant user.

1. Create a dedicated **non-admin** Home Assistant user.
2. Sign in as that user in a separate/private browser session.
3. Open that user's profile and create a Long-Lived Access Token.
4. Enable `home_assistant_mcp_enabled`.
5. Set `home_assistant_mcp_auth_mode` to `restricted_user`.
6. Paste the token into `home_assistant_mcp_user_token`.
7. Keep `home_assistant_mcp_url` at its default unless the internal Home
   Assistant HTTP endpoint differs.

The default URL is:

```text
http://homeassistant:8123/api/mcp
```

The direct URL is not tied to any particular LAN subnet. Any Home Assistant MCP
endpoint reachable from the App network can be used, including addresses in
`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, IPv6, or a resolvable
local DNS hostname. Non-default ports and HTTPS are supported. For HTTPS
hostnames the proxy enables SNI and **verifies the certificate and hostname**.
Ordinary LAN HTTP works without a certificate and is unchanged. For an HTTPS
endpoint with a private CA, place a PEM CA file in Home Assistant's SSL share,
for example `/ssl/home-assistant-ca.pem`, and set `home_assistant_mcp_ca_file`
to that path. The SSL share is mounted read-only. Untrusted or hostname-mismatched
HTTPS certificates are rejected without an insecure fallback. A malformed CA
file disables only the managed Home Assistant MCP bridge, not MCPHub or Ingress.

Prefer a normal LAN IP or DNS name that resolves from containers. An mDNS-only
`*.local` hostname is not guaranteed to resolve in every Home Assistant App
network.

Home Assistant's built-in Assist MCP API can be used by non-admin users.
Other MCP APIs may require an administrator token depending on the API exposed
by the Home Assistant MCP Server integration.

### Authentication mode: `supervisor`

This mode requires no manually created user token. The wrapper forwards to:

```text
http://supervisor/core/api/mcp
```

and injects the `SUPERVISOR_TOKEN` supplied by Home Assistant.

> [!IMPORTANT]
> The `homeassistant_api: true` permission required for Supervisor mode is an
> App-manifest capability and cannot be toggled dynamically from App options.
> Therefore `restricted_user` controls the credential used by the managed MCP
> bridge but does not revoke the container's static Home Assistant API
> capability. True container-level least privilege would require a separate
> MCPHub App variant without that permission.

### Managed-server behavior

- The default MCPHub server name is `ha-home-assistant`; configure a distinct name
  with `home_assistant_mcp_server_name` using 1-64 letters, digits, dots,
  underscores, or hyphens, beginning with a letter or digit.
- Renaming or disabling removes the previous managed entry, including entries
  created by older versions of the App. Existing MCPHub groups or routes
  referencing the old name must be updated manually after a rename.
- Name conflicts with existing user-created servers are rejected rather than
  overwriting those servers.
- The Home Assistant token is injected by the local proxy and is not written to
  `mcp_settings.json`.
- The local bridge listens only on `127.0.0.1:8097`.

## OpenAI Secure MCP Tunnel

### `tunnel_enabled`

Default: `false`

Enables the OpenAI Secure MCP Tunnel.

### `openai_runtime_api_key`

OpenAI Runtime API Key used by the Secure MCP Tunnel client. Create it in
[OpenAI Runtime API keys](https://platform.openai.com/settings/organization/api-keys) with **Restricted** access and
**Tunnels: Read + Use**. Do not use an Admin API key for the tunnel daemon.

### `tunnel_id`

The OpenAI Secure MCP Tunnel ID. Find it in
[OpenAI Tunnel settings](https://platform.openai.com/settings/organization/tunnels). It starts with `tunnel_`
(for example `tunnel_0123456789abcdef0123456789abcdef`).
It is separate from the Runtime API Key. **Do not use the API key Tracking ID.**

### `tunnel_mcp_path`

Default: `/mcp`

Selects the MCPHub route exposed to OpenAI.

Examples:

- `/mcp`
- `/mcp/development`
- `/mcp/$smart`
- `/mcp/$smart/development`

### `tunnel_log_level`

Default: `info`

Allowed values are `debug`, `info`, and `warn`.

Raw HTTP logging remains disabled so Authorization headers are not intentionally written
to the App log.

### Live tunnel controls and automatic recovery

The OpenAI tunnel is supervised by a tunnel controller that runs separately
from MCPHub. Open MCPHub from the Home Assistant sidebar and
select **Tunnels** in its top bar. The tunnel dashboard provides **Start**,
**Stop**, and **Reload** without restarting MCPHub itself. Access is restricted
to the Home Assistant Ingress adapter.

- The App option `tunnel_enabled` is the permission gate: a disabled tunnel never starts, and **Start** reports an error.
- On first start the tunnel runs automatically if its option is enabled.
- **Start** and **Stop** are remembered across App restarts and updates
  (stored as `0600` files in `/data/secrets`). After **Stop**, the tunnel stays
  stopped until you press **Start** again, even if the option remains enabled.
- **Reload** rereads the current App options, including the Runtime API Key,
  without exposing the credentials to the page.
- Redacted output of `tunnel-client` appears in the Home Assistant App log
  (prefixed `[openai-tunnel]`) and under **Show logs** on the dashboard.
- The manager checks `/healthz` and `/readyz` every five seconds. A running
  but temporarily unready client is allowed to recover on its own. If its
  process exits, its liveness fails for one minute, or its readiness stays
  unavailable for ten minutes, it retries after exponential backoff (maximum
  five minutes). An invalid/missing credential suspends retries until an
  operator corrects the configuration and presses **Reload**.
- Tunnel failure or restart does not stop MCPHub's Ingress dashboard or local
  MCP servers. OpenAI connection availability is distinct from MCPHub health.
- Changes to the MCP path may require an App restart to regenerate MCPHub's
  own bearer-key scope; live reload only changes the tunnel client itself.

The tunnel controller binds `127.0.0.1:8093`. The OpenAI client's native health
listener is `127.0.0.1:8080`. Neither address is exposed through the Home
Assistant host or the MCP gateway. The control page and JSON API
contain no API keys, Tunnel IDs, or user tokens.

## Remote access through the Cloudflared and Tailscale Apps

> **Breaking change in v2026.10.19:** MCPHub no longer bundles `cloudflared` or
> its own Tailscale gateway. The options `cloudflare_tunnel_enabled`,
> `cloudflare_tunnel_token`, `cloudflare_mcp_path`, `tailscale_funnel_enabled`,
> `tailscale_mcp_path` and `tailscale_funnel_url`, host port `3002`, and the
> generated Cloudflare and Tailscale client keys are removed. Remote clients
> now use a normal MCPHub bearer key.

Cloudflare and Tailscale run in their own Home Assistant Apps, which already
manage connectors, updates and logs. They forward to MCPHub's MCP-only gateway
on port `3001` (see [LAN access](LAN_ACCESS.md)). The gateway accepts only
`/mcp` routes, MCPHub checks the bearer key, and the web interface, login and
management API are never reachable through it.

- [Cloudflared App](https://my.home-assistant.io/redirect/supervisor_addon/?addon=396f0234_cloudflared&repository_url=https%3A%2F%2Fgithub.com%2Fhomeassistant-apps%2Frepository)
- [Tailscale App](https://my.home-assistant.io/redirect/supervisor_addon/?addon=a0d7b954_tailscale&repository_url=https%3A%2F%2Fgithub.com%2Fhassio-addons%2Frepository)

### `external_url`

Optional. The address your MCP clients use, without a path, for example
`https://mcp.example.com` or `http://192.168.1.10:3001`.

- MCPHub uses it as its base URL, so **Copy client config** on a server or group
  card produces configurations that work from outside Home Assistant. While the
  option is set it overrides the base URL in MCPHub's own settings; when you
  clear it, a base URL set manually in MCPHub is kept.
- The tunnel dashboard's **Check external address** sends one request to
  `<external_url>/mcp` without credentials and without following redirects.
  Only a `401` that carries the gateway's `X-MCPHub-Gateway` marker counts as
  reachable, which proves the full path through Cloudflare or Funnel.

### Cloudflare

With the Cloudflared App's **local tunnel** (it manages `external_hostname`),
add MCPHub under `additional_hosts` in that App's configuration:

```yaml
additional_hosts:
  - hostname: mcp.example.com
    service: http://<Home Assistant IP>:3001
```

With a **remote-managed tunnel** (`tunnel_token`), `additional_hosts` is
ignored; create the same public hostname and service in the Cloudflare
dashboard instead. The tunnel dashboard shows this entry with your Home
Assistant address and the published host port filled in.

Then set `external_url` to `https://mcp.example.com`, create a bearer key in
MCPHub under **Keys**, and use **Copy client config** in MCPHub.

### Tailscale

Devices in your tailnet reach MCPHub directly at
`http://<Home Assistant Tailscale name>:3001/mcp`. Tailscale encrypts this
traffic, so the plain `http://` address is fine inside the tailnet.

For public access through **Funnel**, the Tailscale App's own options only share
Home Assistant itself. Configure Funnel for MCPHub once with the Tailscale CLI
inside the Tailscale App container, for example from the Advanced SSH & Web
Terminal App with protection mode disabled:

```bash
docker exec addon_a0d7b954_tailscale /opt/tailscale funnel --bg --https=8443 http://127.0.0.1:3001
docker exec addon_a0d7b954_tailscale /opt/tailscale funnel status
```

- `--bg` stores the setting in Tailscale's state, so it survives restarts and
  updates of the Tailscale App. This is not an officially supported option of
  that App; check `funnel status` after major Tailscale App updates.
- Port `8443` avoids a conflict when `share_homeassistant` already uses `443`.
- Funnel must be allowed for the node in your tailnet policy.
- Set `external_url` to `https://<node>.<tailnet>.ts.net:8443`.

### Tunnel dashboard

Open MCPHub from the Home Assistant sidebar and select **Tunnels** in its top bar.
The dashboard is a separate page served only through authenticated Home Assistant
Ingress; **Open MCPHub** returns to the MCPHub interface. It has two cards:

- **OpenAI Secure Tunnel** with status, **Start**, **Stop**, **Reload**,
  diagnostics and logs.
- **Remote access** with the external address and its check, the published MCP
  gateway address, and the state and version of the Cloudflared and Tailscale
  Apps with links to open or install them. It reads App state through
  read-only Supervisor info calls and never starts, stops or reconfigures the
  other Apps.

The App adds only this one link to MCPHub's top bar. The link is rendered solely
inside a Home Assistant Ingress session; the MCP gateway never serves the
MCPHub interface. Home Assistant's App configuration page cannot show buttons or
session-specific Ingress links, so its sections point to the **Tunnels** button.

## Dashboard and local proxy architecture

MCPHub is patched to bind to `127.0.0.1:3000` inside the App container.

Nginx provides these adapters:

- `8099` — Home Assistant Ingress, reachable only from the Supervisor Ingress gateway
- `3001` — MCP-only gateway for LAN clients and the Cloudflared and Tailscale
  Apps: only `/mcp` routes with an MCPHub bearer key, no web interface or
  management API
- `127.0.0.1:8097` — optional bridge to Home Assistant's own MCP Server

MCPHub dashboard authentication is not globally disabled. Instead, authenticated Home
Assistant Ingress requests carry the Home Assistant user identity plus a private
per-installation trust marker generated by the App.

The MCP gateway explicitly removes all Home Assistant identity and trust headers
before proxying to MCPHub. A remote client or misconfigured tunnel can therefore
never impersonate a Home Assistant user or reach the MCPHub dashboard or API.

## Authentication model

Home Assistant dashboard access and remote MCP transport use separate authentication
paths:

- Home Assistant Ingress uses the authenticated Home Assistant user identity plus a
  private local proxy trust secret.
- OpenAI Secure MCP Tunnel uses its own internal MCPHub bearer key, automatically
  scoped to the configured MCP route whenever possible.
- LAN, Cloudflare and Tailscale clients use MCPHub bearer keys you create under
  **Keys**; MCPHub can limit each key to specific servers or groups.

Home Assistant Ingress does not reuse any of these credentials. When upgrading from
an older version, the App removes the system keys of the former built-in Cloudflare
and Tailscale origins so they no longer grant access.

## Persistence

MCPHub configuration is stored below:

`/data/mcphub/`

Generated runtime secrets are stored below:

`/data/secrets/`

Package caches are persisted for dynamically launched MCP servers:

- npm / npx: `/data/cache/npm`
- uv / uvx: `/data/cache/uv`

## Adding MCP servers

The standard MCPHub image includes Node.js, Python, npm/pnpm, uv/uvx, Git, and build
tools. Many stdio MCP servers can therefore be installed and launched directly by MCPHub.

Remote SSE and Streamable HTTP MCP servers can be configured by URL. OpenAPI endpoints
can also be wrapped by MCPHub where appropriate.

### GitHub MCP

GitHub is intentionally not hard-coded into this Home Assistant App.

Search MCPHub's Market or Registry for the GitHub MCP implementation you want to use,
review its current upstream authentication instructions, and configure the required
credential in MCPHub.

## Optional GitHub CLI MCP

The App can manage an additional universal GitHub CLI MCP server without requiring a
custom Docker image. It is disabled by default.

### `github_cli_mcp_enabled`

Default: `false`

When enabled, the App registers the managed `ha-github-cli` stdio server in MCPHub.
The App image already bundles GitHub CLI (`gh` version `2.101.0`) for `amd64` and
`aarch64`. The release archive is downloaded and SHA-256 verified during the
Docker image build, not when the MCP server starts.

The `gh-cli-mcp-server==0.3.0` package and its pinned `mcp==1.30.0` Python SDK
are also installed at image-build time in `/opt/gh-cli-mcp/`. The helper launches
the preinstalled MCP server directly, without `uvx` resolution or runtime
package downloads.

Only the GitHub CLI configuration is persisted in `/data/tools/github-cli/config/`.
The `gh` binary and MCP server environment are part of the App image and are
updated with the image, rather than stored in `/data`.

### `github_token`

Optional GitHub Personal Access Token used as `GH_TOKEN` by GitHub CLI. Authenticated
access is required for private repositories and write operations. The App writes this
value to `/data/secrets/github_token` with mode `0600`; it is not copied into
`mcp_settings.json`.

If the integration is enabled without a token, the server still starts, but GitHub CLI
is limited to operations that work without authentication.

Disabling the option removes only the App-managed `ha-github-cli` entry. GitHub MCP
servers created manually under other names are not modified.

## Docker-based MCP servers

This App intentionally does not expose the Home Assistant Docker socket and does not run
in privileged mode.

MCP servers that strictly require launching their own Docker containers are therefore
not supported through host Docker access in this version.

## Backups

The App uses Home Assistant hot backups, so MCPHub and its tunnels keep running while
a backup is created. The persistent `/data` directory contains the MCPHub configuration
and generated secrets required to restore the instance. Re-downloadable npm and uv
package caches below `/data/cache` are excluded from backups.

Treat backups as sensitive because they may contain MCP server credentials and tunnel
configuration.

## Troubleshooting

### MCPHub exits during startup

Check the App log for the first MCPHub error. Configuration parsing and upstream package
failures normally appear before the wrapper reports that MCPHub exited.

### The Web UI does not open

Check that MCPHub reached the ready state and that Nginx started afterward.

The MCPHub interface is available only through Home Assistant; use **Open Web UI** or
the sidebar entry. Port 3001 is an MCP-only gateway and returns 404 for the interface.

### A remote client cannot connect

Open the tunnel dashboard and select **Check external address**:

- **Reaches MCPHub:** the path works; check the client's bearer key and URL path.
- **Not reachable:** check the Cloudflared or Tailscale App and its log, and that
  host port `3001` is published under **MCPHub → Network**.
- **Answers, but not MCPHub:** the hostname forwards somewhere else, for example
  to Home Assistant on port `8123` instead of `3001`.
- **Redirected:** often a Cloudflare Access login or an `http://` to `https://`
  redirect; use the final `https://` address as `external_url`.

### The remote client receives 401

Create or copy a valid key in MCPHub under **Keys** and send it as
`Authorization: Bearer <key>`. Keys limited to certain servers or groups only work
for those routes.

### The remote client receives 404

The MCP gateway serves only `/mcp`, `/mcp/<group-or-server>` and
`/mcp/$smart[/<group>]`. Every other path, including the MCPHub interface,
returns 404.

### A server fails to start

Open the server entry in MCPHub and inspect its logs.

For stdio servers, verify the package name, executable, environment variables, and
network access.

### The OpenAI tunnel does not start

Verify that:

- `tunnel_enabled` is enabled
- the OpenAI Runtime API Key is present
- the Tunnel ID is correct
- the selected `tunnel_mcp_path` exists
- MCPHub itself is healthy

## Development changelog and stable promotion

The development store builds MCPHub from `dev-mcphub` and assigns an
independently increasing `-dev.N` version. Its generated changelog starts with
the exact `-dev.N` version and lists all relevant commits and changed files
since the current Stable release on `main`. Every Dev revision has its own
entry, stored in `.dev-store-mcphub-changes.json` and retained on future builds.
The first entry establishes a tracking baseline; earlier changes still appear
in the full Stable comparison. The curated source `MCPHub/CHANGELOG.md` is
preserved beneath these entries. MCPHub-specific CI and automation changes
also create MCPHub Dev revisions, but Trilium-only changes do not.

When merging user-visible App changes into `dev-mcphub`, update the current
changelog entry with the actual new features, fixes, security changes, and any
migration caveats. The upstream-update script records the upstream image bump;
it cannot describe unrelated App wrapper changes made between upstream releases.

Before promoting MCPHub to `main`, the Stable candidate must include the full
Git history and all changed files since the current `main` release, in addition
to its human-written feature and fix notes. Generate the audit section with:

```sh
python3 .github/scripts/generate-mcphub-changelog.py stable
```

The `Validate MCPHub` workflow rejects promotion PRs into `main` when the
complete section is missing or outdated. The updated promotion workflow uses
a separate `release/mcphub-candidate` branch with full notes, preparing a PR
**for manual merge only**. It never merges or releases automatically.
GitHub executes `workflow_run` workflows from the default branch; therefore
this improved promotion workflow starts operating after it first reaches `main`.
For the **first** Stable promotion after this change, prepare the candidate
manually using the command above and review the result before merging.
Do not merge a direct PR from `dev-mcphub` without the required audit section.
Keep the existing release history intact.