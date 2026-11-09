# Home Assistant Apps

Home Assistant Apps maintained by HyperCriSiS.

[![Validate Trilium](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate.yml)
[![Validate MCPHub](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-mcphub.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-mcphub.yml)
[![Validate Calibre AIO](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-calibre-aio.yml)

## 📦 Install the repository

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps)

> [!NOTE]
> **Repository renamed:** Existing Home Assistant installations that use
> `https://github.com/HyperCriSiS/Home-Assistant-Addons` should **keep their
> existing repository entry**. GitHub redirects the old address to this repository;
> re-adding it under the new URL would create a different repository ID and
> potentially duplicate the Apps. New installations should use the new URL above.

If the button does not open the repository dialog, add it manually:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps
```

> [!IMPORTANT]
> Home Assistant Apps require **Home Assistant OS** or a **Supervised** installation. The Apps support `amd64` and `aarch64`.

&nbsp;

## 🧩 Available Apps

| | App | Purpose | Status | Documentation |
| :---: | --- | --- | --- | --- |
| <img src="MCPHub/icon.png" alt="" width="32"> | **MCPHub** | Central management for local and remote Model Context Protocol servers | ✅ Stable | [README](MCPHub/README.md) · [Documentation](MCPHub/DOCS.md) |
| <img src="TriliumNext%20Notes/icon.png" alt="" width="32"> | **Trilium Notes** | Self-hosted hierarchical notes and personal knowledge base | ✅ Stable | [README](TriliumNext%20Notes/README.md) |
| <img src="Calibre%20AIO/icon.png" alt="" width="32"> | **Calibre AIO** | Shelfmark book discovery/downloads and Calibre-Web Automated library in one interface | ✅ Stable | [README](Calibre%20AIO/README.md) · [Documentation](Calibre%20AIO/DOCS.md) |

&nbsp;

### <img src="MCPHub/icon.png" alt="MCPHub" width="28" align="absmiddle"> MCPHub

**MCPHub** brings a central MCP control plane into Home Assistant.

✨ **Highlights:**

- Manage local stdio and remote MCP servers from one dashboard
- Discover servers through the MCPHub Market / Registry
- Home Assistant Ingress with single sign-on
- Persistent MCPHub configuration and package caches
- Optional OpenAI Secure MCP Tunnel for ChatGPT
- Remote access for Claude, Cursor, VS Code, and other MCP clients through the Cloudflared or Tailscale App
- Optional managed GitHub CLI MCP server
- Optional managed Home Assistant MCP server
- MCP-only LAN gateway on port 3001 (bearer key required, no web interface)
- Hot backups that keep MCPHub running
- No Docker socket, privileged mode or host networking; Supervisor API access is read-only (App status for remote access)

See [MCPHub/README.md](MCPHub/README.md) for installation and [MCPHub/DOCS.md](MCPHub/DOCS.md) for configuration, remote access, security, and troubleshooting.

&nbsp;

### <img src="TriliumNext%20Notes/icon.png" alt="Trilium Notes" width="28" align="absmiddle"> Trilium Notes

**Trilium Notes** runs [TriliumNext/Trilium](https://github.com/TriliumNext/Trilium) as a Home Assistant App.

✨ **Highlights:**

- Hierarchical note-taking and personal knowledge management
- Home Assistant Ingress
- Persistent data stored in the Home Assistant App data volume
- Home Assistant backup support
- Supervisor watchdog
- Optional direct TCP access on port `8080`
- Restricted trusted reverse-proxy handling for Home Assistant Ingress

See [TriliumNext Notes/README.md](TriliumNext%20Notes/README.md) for installation, configuration, backups, networking, and troubleshooting.

&nbsp;

## 🧪 Development builds

A shared development repository is available for testing upcoming releases of both Apps:

[![Add development repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps%23dev-store)

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

Home Assistant displays it as **HyperCriSiS Apps (Dev)**.

> [!WARNING]
> Development builds may contain incomplete or breaking changes. Use the stable repository for normal installations and keep a current backup before testing development updates.

&nbsp;

## 💬 Support

For Home Assistant App integration issues, configuration problems, or packaging bugs, open an issue in this repository.

For application-specific bugs in Trilium or MCPHub itself, use the corresponding upstream project where appropriate.

&nbsp;

## 🛠️ Maintainer documentation

Repository branching and release mechanics are documented separately in [BRANCHING.md](BRANCHING.md).
