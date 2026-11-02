# Current Work — Home-Assistant-Apps

Last reviewed: 2026-10-08. Authoritative integrated branch: `main`. This is the common work-resumption entry point, **not** a synthetic roadmap or an approval to merge pending implementation.

## Live sources

- [README](../../README.md) and [documentation index](../DOCUMENTATION.md) — project-specific directions.
- [Agent instructions](../../AGENTS.md) — local engineering and safety policy.
- [Open pull requests](https://github.com/HyperCriSiS/Home-Assistant-Apps/pulls) and [issues](https://github.com/HyperCriSiS/Home-Assistant-Apps/issues) — actual work queue; always recheck the current state.
- [CI and Actions](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions) — build, security and release evidence.

## Current scope and resumption

This is a multi-add-on repository. For an add-on change, inspect its directory, `repository.json`, integration/deployment workflows, and open dependency PRs. There is no repo-wide roadmap; do not invent a completed or in-progress phase.

## Verification and update policy

MCPHub prebuilt-image work is implemented on `chore/mcphub-prebuilt-images` in
the isolated `.work-mcphub-prebuilt` checkout. See [publication and rollout](MCPHUB-IMAGES.md).
All 73 local automation tests, workflow/YAML lint, shell syntax and stable
changelog checks pass; 73 of 77 MCPHub tests pass on Windows. Container builds, registry
publication and a prebuilt-image HAOS smoke test remain pending; the Windows
session cannot access Docker. Four existing MCPHub test failures depend on Unix
paths/permissions or OpenSSL availability. No stable release is claimed.
Push/PR creation also remains pending because this session has no usable GitHub
credentials; the GitHub connector requires an unavailable approval.

Compare the proposed change with the latest `main` and relevant upstream changes. Review actual tests and unfinished PRs; record verified findings and next steps here with evidence links. Avoid claiming all work is complete from a green documentation check, or adding a repo-wide roadmap merely to populate a template. Leave task-specific history in its existing documents.
