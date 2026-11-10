# Current Work — Home-Assistant-Apps

Last reviewed: 2026-11-03. Authoritative integrated branch: `main`. This is the common work-resumption entry point, **not** a synthetic roadmap or an approval to merge pending implementation.

## Live sources

- [README](../../README.md) and [documentation index](../DOCUMENTATION.md) — project-specific directions.
- [Agent instructions](../../AGENTS.md) — local engineering and safety policy.
- [Open pull requests](https://github.com/HyperCriSiS/Home-Assistant-Apps/pulls) and [issues](https://github.com/HyperCriSiS/Home-Assistant-Apps/issues) — actual work queue; always recheck the current state.
- [CI and Actions](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions) — build, security and release evidence.

## Current scope and resumption

This is a multi-add-on repository. For an add-on change, inspect its directory, `repository.json`, integration/deployment workflows, and open dependency PRs. There is no repo-wide roadmap; do not invent a completed or in-progress phase.

## Verification and update policy

MCPHub prebuilt-image installation is tracked in [PR #151](https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/151).
The public `v2026.11.02` images passed both architecture container tests and
anonymous registry verification in [publication CI](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/41517218976).
The [HAOS 18.4 installation test](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/41519886711)
installed the published image without a Dockerfile and verified restart, Ingress,
LAN authentication and tools from both Home Assistant MCP servers. Linux unit
tests also pass. See [publication and rollout](MCPHUB-IMAGES.md); use the actual
`main` and generated `dev-store` metadata to determine which version is offered.

Inbox Zero was added as a fourth App on 2026-11-09. Its automation is on `main`;
the App folder lives on `dev-inbox-zero` until the first manual release through
`promote.yml` (app `inbox-zero`). Before that release: the three GHCR packages
`inbox-zero-base`, `amd64-inbox-zero` and `aarch64-inbox-zero` must be public,
`dev-inbox-zero` must be in the ruleset "App development branches", and the App
must have been installed from the Dev store. `INBOX_ZERO_AUTO_PROMOTE` stays unset
until that release has proven the chain. Only amd64 was booted locally; aarch64
is covered by the native runner in `validate-inbox-zero.yml`.

Open pull requests: [#215](https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/215)
adds the App to `dev-inbox-zero`;
[#216](https://github.com/HyperCriSiS/Home-Assistant-Apps/pull/216) brings the
automation to `main` and must merge after #215 and after the packages are public.

Compare the proposed change with the latest `main` and relevant upstream changes. Review actual tests and unfinished PRs; record verified findings and next steps here with evidence links. Avoid claiming all work is complete from a green documentation check, or adding a repo-wide roadmap merely to populate a template. Leave task-specific history in its existing documents.
