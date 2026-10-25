# Trilium Notes

**Self-hosted hierarchical notes and personal knowledge base inside Home Assistant.**

[![Validate Trilium](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate.yml)
[![Trilium version](https://img.shields.io/badge/Trilium-v0.106.1-6E56CF)](https://github.com/TriliumNext/Trilium/releases/tag/v0.106.1)
![Architecture amd64](https://img.shields.io/badge/amd64-supported-success)
![Architecture aarch64](https://img.shields.io/badge/aarch64-supported-success)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-App-41BDF5?logo=homeassistant&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

This Home Assistant App runs [Trilium Notes](https://github.com/TriliumNext/Trilium), a hierarchical note-taking application for building a personal knowledge base. It supports rich text and Markdown, encryption, synchronization, scripting, and extensive organization features.

> [!IMPORTANT]
> Home Assistant Apps require **Home Assistant OS** or a **Supervised** installation. Older Home Assistant versions may still use the term **Add-ons** instead of **Apps**.

## Installation

### Stable

[![Add stable repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps)

1. Add the stable repository using the button above.
2. Install **Trilium Notes** from the App store.
3. Start the App and open its web interface through Home Assistant Ingress.
4. Complete Trilium's initial setup and choose a strong password.

**Existing Trilium installations:** If you originally added `Home-Assistant-Addons`, keep the existing repository entry. GitHub redirects it to this repository so updates can continue. Do not remove/re-add it or register both the old and new URLs, as Home Assistant assigns them different repository IDs.

### Development testing

To test the current `dev-trilium` candidate before it is promoted to `main`, add the shared generated
development store:

[![Add development repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps%23dev-store)

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

The development App is shown as **Trilium Notes (Dev)** under
**HyperCriSiS Apps (Dev)**, so it can be distinguished from the stable App at a glance.

> [!WARNING]
> Development builds may contain breaking changes. Create a Home Assistant backup before
> testing a development update.

## Configuration

| Option | Description | Default |
| --- | --- | --- |
| `timezone` | IANA timezone used by the container | `Europe/Berlin` |
| `log_retention_days` | Number of days Trilium keeps log files | `90` |

The legacy `log_level` and `https_only` options are retained only for upgrade compatibility and are no longer used. TLS is terminated by Home Assistant Ingress or an external reverse proxy.

## Data and backups

Persistent data is stored in `/home/node/trilium-data` and mapped to the Home Assistant App data volume. Home Assistant backups include this directory. The App uses **cold backups**: Home Assistant stops Trilium briefly while the backup is created, so the SQLite database is always captured in a consistent state. Trilium can also create its own backups under **Options → Backup**; these are stored in the same data volume and are therefore included in Home Assistant backups as well.

Before upgrading, create a current Home Assistant backup. Database migrations are performed by Trilium during startup and downgrading across database schema versions may not be supported.

## Network access

Ingress is enabled by default. Port `8080` is also exposed for optional direct access. Trilium trusts only the Home Assistant Ingress reverse proxy at `172.30.32.2` for forwarded client information instead of globally trusting arbitrary `X-Forwarded-For` headers.

> [!TIP]
> Direct access on port `8080` bypasses Home Assistant authentication and is protected only by Trilium's own login. If you only use Ingress or the Trilium desktop/mobile sync through a reverse proxy, clear the host port under **Settings → Apps → Trilium Notes → Configuration → Network** to disable it. Never forward this port to the internet without TLS.

## Troubleshooting

- Review the App logs under **Settings → Apps → Trilium Notes → Logs**.
- If the interface does not load after an update, restart the App and clear the browser cache.
- If startup fails after an upgrade, restore the pre-upgrade backup and attach the complete log when opening an issue.

## Support

For App-specific issues, use the [issue tracker](https://github.com/HyperCriSiS/Home-Assistant-Apps/issues). For Trilium application issues, use the [upstream project](https://github.com/TriliumNext/Trilium/issues).

## License

This App packaging is licensed under the MIT License. Trilium Notes is licensed under the GNU Affero General Public License v3.0.
