# Changelog

## v2026.11.10-2

### Fixed

- The managed Home Assistant MCP servers are pinged once a minute instead of every five seconds, which flooded the `ha-mcp` access log with a `POST /mcp` line every five seconds.
- README and DOCS links open the GitHub documents instead of reloading the App page in Home Assistant.

## v2026.11.10

### Commits in this Dev build

- [`7082ea6`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/7082ea687422020a8b75cb392b7817f79584644e) Merge remote-tracking branch 'origin/main' into dev-mcphub
