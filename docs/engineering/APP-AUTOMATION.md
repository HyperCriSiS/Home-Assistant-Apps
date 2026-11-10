# App automation: one contract for every App

Every App in this repository is handled by the same chain of GitHub Actions.
This page is the single reference for that chain, for the timings every App
must share, and for the checklist that makes a new App behave identically from
its first day. Branch semantics are described in [BRANCHING.md](../../BRANCHING.md).

## The chain

```text
upstream release
  -> update-<app>.yml           opens a bot PR against dev-<app>      (daily)
  -> validate-<app>.yml         full validation of the PR commit      (dispatched)
  -> merge-due-updates.yml      merges the bot PR after 12 hours      (hourly)
  -> sync-dev-store.yml         publishes dev-store for HA testing    (on push)
  -> auto-promote-<app>.yml     releases dev-<app> to main            (every 3 hours)
  -> sync-dev-bases.yml         merges main back into every dev-*     (on push to main)
```

Every step is fail closed: a step that cannot prove its precondition skips or
puts the pull request on hold with the label `hold`. Removing the label resumes
the automation. Scheduled workflows run only from `main`; a workflow that exists
only on a development branch never runs on its schedule.

A release reaches `main` as one squashed commit, so `sync-dev-bases.yml` can
meet a conflict in the App changelog that the release pull request reworded.
`resolve_release_changelog.py` settles exactly that case: when only App
changelogs conflict and the App is otherwise identical on both sides, the
branch has nothing unreleased and takes the released text from `main`. Any
other conflict, including a development branch that already moved on, fails
the run for that branch only and needs a manual merge; the remaining branches
and the development store are still synced.

## Shared timings and settings

| Setting | Value | Where it lives |
| --- | --- | --- |
| Update check | daily, `17 4 * * *` (Trilium, MCPHub), `23 7 * * *` (Calibre), `47 4 * * *` (Inbox Zero) | `update-*.yml` |
| Bot PR merge delay into `dev-<app>` | 12 hours after the PR was opened | `merge_due_updates.py` `DELAY` |
| Due-update merge check | hourly, `23 * * * *` | `merge-due-updates.yml` |
| Minimum upstream release age | 48 hours | `auto_promote_*.py` `RELEASE_AGE` (`COMMIT_AGE` for Inbox Zero, which follows fork commits) |
| Soak time on `dev-<app>` before release | 36 hours after the newest update reached the branch | `auto_promote_*.py` `SOAK` |
| Distance to the previous stable release | 24 hours (MCPHub only) | `auto_promote_mcphub.py` `COOLDOWN` |
| Promotion check | every 3 hours, offset per App (`13`, `37`, `43`) | `auto-promote-*.yml` |
| Promotion switch | repository variable `<APP>_AUTO_PROMOTE=true` | repository settings, variables |
| Pause one PR | label `hold` on the update or release PR | GitHub labels |
| Bot identity | `github-actions[bot]`, `github.token` | every workflow |
| Merge method | squash only on `main`; fast-forward and deletion blocked on `dev-*` and `dev-store` | repository rulesets |

The release gates accept only commits produced by the trusted updater of that
App (version pins, generated build arguments, changelog lines). Any other commit
on `dev-<app>` keeps the manual release flow in `promote.yml`; the automation
then skips silently every three hours until a manual release has been made.

## Per-App status

| App | Updater | Merge into dev | Auto-promote | Images |
| --- | --- | --- | --- | --- |
| Trilium Notes | `update-trilium.yml` | yes | `auto-promote-trilium.yml`, `TRILIUM_AUTO_PROMOTE` | published to GHCR before the merge |
| MCPHub | `update-mcphub.yml`, `update-mcphub-tunnel-clients.yml` | yes | `auto-promote-mcphub.yml`, `MCPHUB_AUTO_PROMOTE` | published to GHCR before the merge |
| Calibre AIO | `update-calibre-aio.yml` | on `dev-calibre` only | `auto-promote-calibre.yml`, `CALIBRE_AUTO_PROMOTE`, on `dev-calibre` only | published to GHCR before the merge |
| Inbox Zero | `update-inbox-zero.yml` | yes | `auto-promote-inbox-zero.yml`, `INBOX_ZERO_AUTO_PROMOTE` | published to GHCR before the merge, on top of `inbox-zero-base:<commit>` built by `build-inbox-zero-base.yml` |

"On `dev-calibre` only" means the files exist on the development branch but not
yet on `main`. They become active with the next manual Calibre release and the
variable `CALIBRE_AUTO_PROMOTE=true`.

## Prebuilt images

Every App installs a prebuilt image from GHCR. Home Assistant must never build
an App on the host: the Supervisor exports a locally built image into every
backup (several hundred megabytes per App) and rebuilds it on every update.

- `config.yaml` carries `image:` (`ghcr.io/hypercrisis/{arch}-<app>` per
  architecture, or one multi-arch manifest as MCPHub does).
- `publish-<app>-images.yml` builds both architectures from the exact
  candidate, runs an acceptance check on the built artifact, pushes immutable
  version tags and verifies anonymous access. An existing tag is never replaced
  with different content; the App version must be bumped instead.
- The tag is published before anything advertises it: `sync-dev-store.yml`
  pushes `dev-store` only after every publisher succeeded, `promote.yml`
  publishes before the release PR exists, and `auto-promote-<app>.yml` refuses
  the merge while the tag is not public.
- A new GHCR package is private after its first push. Set it to public once,
  otherwise the anonymous-access check fails on purpose.
- Source tests on Home Assistant OS remove `image:` only from their disposable
  local copy, so unreleased commits are still built and tested.

## Checklist for a new App

Copy the Trilium files as the template; they are the smallest complete set,
and shape the folder after [APP-STANDARDS.md](APP-STANDARDS.md).

1. Create `dev-<app>` from `main` and add it to the ruleset
   "App development branches" (blocks deletion and force pushes).
2. Add the branch to `sync-dev-bases.yml`, `sync-dev-store.yml` (checkout,
   `git rm` list and generator), `lint-workflows.yml` push branches and
   `BRANCHING.md`.
3. Add `validate-<app>.yml` with `pull_request`, `push` to `main` and
   `dev-<app>`, and `workflow_dispatch`. The dispatched run is what the merge
   and release gates look for.
4. Add `update-<app>.yml`: daily schedule, checkout of `dev-<app>`, the trusted
   updater taken from `main`, branch name `automation/<app>-<version>`, title
   `chore: update <App> to <version>`, dispatch of the validation, close
   superseded PRs.
5. Add a `Kind` for the App in `.github/scripts/merge_due_updates.py` with the
   exact file list the updater may touch, and a test in
   `.github/tests/test_merge_due_updates.py`.
6. Add `.github/scripts/auto_promote_<app>.py` reusing the shared helpers from
   `auto_promote_mcphub.py` with `RELEASE_AGE = 48 * HOUR` and
   `SOAK = 36 * HOUR`, plus `auto-promote-<app>.yml` with
   `if: vars.<APP>_AUTO_PROMOTE == 'true' && github.ref == 'refs/heads/main'`,
   the concurrency group `promote-app-development-main` and a cron offset that
   does not collide with the other Apps.
7. Add the App to `promote.yml` (`workflow_dispatch` choice and `workflow_run`
   list) for manual releases.
8. Add `publish-<app>-images.yml` as a `workflow_call` used by
   `sync-dev-store.yml` (the Dev store waits for it), `promote.yml` and
   `auto-promote-<app>.yml` (the merge requires the public tag), and
   `image:` in `config.yaml`. Every App installs prebuilt images; see
   [Prebuilt images](#prebuilt-images).
9. Set the repository variable `<APP>_AUTO_PROMOTE=true` only after the first
   manual release has proven the chain.
10. Add the App row to this page and to the README table.
