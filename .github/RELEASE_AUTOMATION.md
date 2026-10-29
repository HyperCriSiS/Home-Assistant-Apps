# App release automation

Trilium uses a dedicated release-candidate branch, `dev-trilium`. MCPHub uses `dev-mcphub`. Both feed the shared generated `dev-store`, while `main` remains the user-facing stable repository.

## Timing at a glance

| Step | Trilium | MCPHub |
| --- | --- | --- |
| Detect new upstream release | daily 04:17 UTC (`Update Trilium`) | daily 04:17 UTC (upstream) and 05:37 UTC (OpenAI tunnel-client) |
| Bot PR → `dev-*` | **12 hours** after the PR was opened, once full CI passed for the exact commit (`Merge due App updates`, hourly) | same |
| `dev-*` → `main` | **36 hours** after the newest update reached `dev-trilium` (`Auto-promote Trilium updates`, every 3 hours) | **36 hours** after the newest update reached `dev-mcphub` (`Auto-promote MCPHub updates`, every 3 hours), plus a Home Assistant OS QEMU test and at least 24 hours since the previous stable release |

## Bot update pull requests → development branch

1. The update workflows open one pull request per new upstream version against the App development branch and dispatch full validation for it. A newer upstream release closes the older, not yet merged PR.
2. `Merge due App updates` (`.github/scripts/merge_due_updates.py`) runs hourly from `main` and merges a bot PR only when:
   - it was opened by `github-actions[bot]` from this repository for a known automation branch with the expected title;
   - its HEAD tree is byte for byte what the trusted updater on `main` produces from the current development branch;
   - the full App validation passed for exactly that HEAD commit;
   - it has been open for at least 12 hours.
3. A PR that fell behind its development branch is regenerated on the current base with the original PR date and validated again; the 12 hours still count from the opening of the PR.
4. Anything unexpected (different content, failed validation) labels the PR `hold` with a comment. Remove the label after fixing it, or add it yourself to stop a PR.

## Development branch → `main`

Both Apps are promoted automatically only when the development branch contains nothing but bot version bumps (plus clean merges of `main`) since the last release, the newest update has been on the development branch for 36 hours (12 hours as an open PR plus 36 hours on the branch, about 48 hours in total), the upstream release is at least 48 hours old and the exact development commit passed validation. Major upstream versions, any manual change and the optional HAOS gate keep the manual release PR flow.

- Releases are **squash-merged** into `main` (the only method the `main` ruleset allows). A clean sync merge of `main` back into the development branch marks everything before it as released.
- After a merge the workflows start `main` validation, `Sync development branch bases` and the development store. If `main` validation fails, a revert PR and an issue are opened; nothing is reverted automatically.
- Pause: set the repository variable `TRILIUM_AUTO_PROMOTE` or `MCPHUB_AUTO_PROMOTE` to anything but `true`, or label the release pull request `hold`.

Manual releases stay available through `Promote app development branches to main`.

## Validation

Trilium CI validates metadata, amd64/aarch64 images, native and cross-platform builds, Home Assistant-style Ingress proxying, WebSockets, browser E2E, restart persistence, and database upgrades from the stable version currently on `main`. The `Lint repository` workflow also runs the unit tests for every update, merge and promotion gate.

## Dependency ownership

- Trilium Docker releases are owned by `Update Trilium`.
- MCPHub dependencies target `dev-mcphub`.
- Trilium browser-test npm dependencies target `dev-trilium`.
- Shared GitHub Actions dependency PRs target `main` because they are repository infrastructure rather than an App release.

## Branch protection

`dev-trilium`, `dev-mcphub`, and `dev-store` are permanent protected branches. Deletion and non-fast-forward updates are blocked. `main` keeps its stricter pull-request-only protection.

## Optional HAOS gate

If `HAOS_E2E_ENABLED=true`, Trilium and MCPHub each use their own dedicated HAOS integration workflow before release promotion. Trilium is then promoted manually only.
