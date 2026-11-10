# Changelog

## v2026.11.10

### Security

- MCP servers started by MCPHub and the OpenAI tunnel client no longer inherit the Home Assistant Supervisor token or the MCPHub signing and Ingress secrets. A server you added yourself that relied on the inherited `SUPERVISOR_TOKEN`, or that uses `${SUPERVISOR_TOKEN}` or `${JWT_SECRET}` in its URL, headers, arguments or environment, now needs its own Home Assistant token in its server configuration; the placeholder otherwise expands to an empty value. The managed Home Assistant MCP servers are not affected.

## v2026.11.07-1

### Commits in this Dev build

- [`01c31f9`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/01c31f9df78302dc49c09486fda3324d4450ac68) fix(mcphub): keep Supervisor token and hub secrets out of child processes (#218)
