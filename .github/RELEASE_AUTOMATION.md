# App release automation

Trilium uses a dedicated release-candidate branch, `dev-trilium`. MCPHub uses `dev-mcphub`. Both feed the shared generated `dev-store`, while `main` remains the user-facing stable repository.

## Timing at a glance

| Step | Trilium | MCPHub |
| --- | --- | --- |
| Detect new upstream release | hourly at minute 17 (`Update Trilium`) | hourly at minute 7 (upstream) and minute 37 (OpenAI tunnel-client) |
| Bot PR → `dev-*` | As soon as full CI passed for the exact commit, no waiting period (`Merge due App updates`, hourly at minute 23) | same |
| `dev-*` → `main` | **3 hours** after the newest update reached `dev-trilium` (`Auto-promote Trilium updates`, hourly at minute 53), released by the release agent | **3 hours** after the newest update reached `dev-mcphub` (`Auto-promote MCPHub updates`, hourly at minute 43), plus a Home Assistant OS QEMU test, released by the release agent |

## Bot update pull requests → development branch

1. The update workflows open one pull request per new upstream version against the App development branch and dispatch full validation for it. A newer upstream release closes the older, not yet merged PR.
2. `Merge due App updates` (`.github/scripts/merge_due_updates.py`) runs hourly from `main` and merges a bot PR only when:
   - it was opened by `github-actions[bot]` from this repository for a known automation branch with the expected title;
   - its HEAD tree is byte for byte what the trusted updater on `main` produces from the current development branch;
   - the full App validation passed for exactly that HEAD commit.
3. A PR that fell behind its development branch is regenerated on the current base with the original PR date and validated again.
4. Anything unexpected (different content, failed validation) labels the PR `hold` with a comment. Remove the label after fixing it, or add it yourself to stop a PR.

## Development branch → `main`

Both Apps are handed to the release agent only when the development branch contains nothing but bot version bumps (plus clean merges of `main`) since the last release, the newest update has been on the development branch for 3 hours, and the exact development commit passed validation. Major upstream versions and any manual change keep the manual release PR flow. The agent also finishes a release it left half done, as long as only bot commits are unreleased.

- Releases are **squash-merged** into `main` (the only method the `main` ruleset allows). A clean sync merge of `main` back into the development branch marks everything before it as released.
- After a merge the workflows start `main` validation, `Sync development branch bases` and the development store. If `main` validation fails, a revert PR and an issue are opened; nothing is reverted automatically.
- Pause: set the repository variable `TRILIUM_AUTO_PROMOTE` or `MCPHUB_AUTO_PROMOTE` to anything but `true`, or label the release pull request `hold`.

Manual releases stay available through `Promote app development branches to main`.

## Release agent

`Repair App updates` (`.github/workflows/repair-app-updates.yml`) runs a coding agent in GitHub Actions. When an auto-promote gate passes, it tidies the changelog, runs `promote.yml` and merges the release to `main`. It also fixes a failed update, validation or promotion run and bot PRs that are stuck or were put on `hold` by the automation. It needs the repository secret `CLAUDE_CODE_OAUTH_TOKEN`; `APP_REPAIR=false` switches it off and restores the built-in merge.

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
