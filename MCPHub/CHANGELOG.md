# Changelog

## v2026.11.05

### Changed

- Updated MCPHub from 1.1.15 to 1.2.0.
- Updated MCPHub from 1.2.0 to 1.2.1.
- The unofficial ha-mcp server is pinned to release 9.1.0 and updated together with the App. Restarts no longer install the newest PyPI release unreviewed.

### Fixed

- The Ingress `/config` response rejects an Ingress path header that is not a plain path instead of embedding it unescaped in JSON.
- The tunnel dashboard reads the ha-mcp option group like the other groups.
- README and option descriptions no longer claim read-only Supervisor access, a download of the GitHub CLI on demand, or an MCP-only gateway without the `/health` check.
- An invalid or missing token, address or server name for the managed Home Assistant MCP bridge or the ha-mcp server no longer prevents MCPHub from starting. The affected server is left disabled with a warning in the log while Ingress, the LAN gateway and all other servers keep running.

## v2026.11.02

### Commits in this Dev build

- [`abdc7fb`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/abdc7fb7d4ddada8764569f14081b1e02df8b478) Merge remote-tracking branch 'origin/main' into dev-mcphub
- [`3036573`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/3036573789071ecd2aeef87b021c9aa25e123636) Merge remote-tracking branch 'origin/main' into dev-mcphub
- [`e871570`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/e871570a317e3ef87fee0e2d9a8ca535d9ee6982) chore: document the shared App automation and fix store sync deletions (#167)
