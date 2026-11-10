# Branching workflow

This repository uses separate long-lived development branches per Home Assistant App.
The update, merge and release automation shared by every App, its timings and the
checklist for a new App are documented in
[docs/engineering/APP-AUTOMATION.md](docs/engineering/APP-AUTOMATION.md).

## `main`

`main` is the stable Home Assistant repository consumed by normal users. Only validated changes that are ready for release belong here.

## `dev-trilium`

Long-lived release-candidate branch for **Trilium Notes only**. Trilium changes are validated and tested here before promotion to `main`.

## `dev-mcphub`

Long-lived release-candidate branch for **MCPHub only**. MCPHub changes are validated and tested here before promotion to `main`.

## `dev-calibre`

Long-lived release-candidate branch for **Calibre AIO only**. App changes and
upstream update proposals target this branch. Bot-only upstream updates are
promoted to `main` automatically (see below); everything else is a separate
manual release after testing.

## `dev-inbox-zero`

Long-lived release-candidate branch for **Inbox Zero only**. App changes and
the daily fork commit proposals target this branch. Bot-only commit bumps are
promoted to `main` automatically (see below); everything else is a separate
manual release after testing.

Development branches periodically merge the latest `main` so they inherit already released changes from the other Apps without inheriting their unreleased work.

## `dev-store`

`dev-store` is a generated Home Assistant testing repository. It is composed from:

- `TriliumNext Notes/` from `dev-trilium`
- `MCPHub/` from `dev-mcphub`
- `Calibre AIO/` from `dev-calibre`
- `Inbox Zero/` from `dev-inbox-zero`
- shared repository content from `main`

Home Assistant development repository URL:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

Old repository URLs are kept operational by GitHub redirects after the rename. For new Home Assistant installations, use the new `Home-Assistant-Apps` URL; existing installations should not register both URL variants, because Home Assistant derives different repository IDs from them.

The generator adds `(Dev)`, `-dev.<run>`, and `stage: experimental` metadata so test installations are clearly distinguishable.

Every App uses prebuilt images. The generator tests and publishes both
architectures and verifies anonymous access before pushing the Dev store.
Trilium publishes `ghcr.io/hypercrisis/{arch}-trilium:<version>` the same way
Calibre does (see below); the common rules are in
[docs/engineering/APP-AUTOMATION.md](docs/engineering/APP-AUTOMATION.md#prebuilt-images).
Release-candidate validation publishes stable images before the main merge;
main verifies the existing immutable tag. See [MCPHub image publication](docs/engineering/MCPHUB-IMAGES.md)
for the initial package visibility setup and rollout order.

**Never edit `dev-store` manually and never merge it into `main`.**

## Release flows

```text
Trilium work -> dev-trilium -> dev-store -> HA test -> main
MCPHub work  -> dev-mcphub  -> dev-store -> HA test -> main
Calibre work -> dev-calibre -> dev-store -> HA test -> main
Inbox Zero work -> dev-inbox-zero -> dev-store -> HA test -> main
```

A Trilium release PR is always `dev-trilium -> main`. An MCPHub release PR is always `dev-mcphub -> main`. This prevents one App's unreleased work from being published with the other App.

### Automatic MCPHub update releases

`auto-promote-mcphub.yml` merges `dev-mcphub` into `main` without manual review only when every gate in `.github/scripts/auto_promote_mcphub.py` passes:

- `dev-mcphub` contains nothing but GitHub-signed squash merges of bot PRs titled `chore(mcphub): update upstream to …` or `chore(mcphub): update OpenAI tunnel client`, plus clean, unedited merges of `main`.
- The diff to `main` is only those version bumps and their generated changelog lines. Major version updates stay manual.
- The new MCPHub and tunnel-client releases are stable and at least 48 hours old. The newest update has been on `dev-mcphub` for at least 36 hours (about 48 hours after the update PR was opened). The previous stable MCPHub release is at least 24 hours old.
- `validate-mcphub.yml` and the Home Assistant OS test (`haos-qemu-mcphub.yml`) both passed for that exact commit. That test boots a disposable official Home Assistant OS VM on a GitHub-hosted runner, installs, builds, starts and restarts MCPHub, and probes Ingress and the LAN MCP port.
- The release candidate is validated again and merged only if `main`, `dev-mcphub` and the candidate commit are unchanged. If stable validation fails after the merge, a revert PR and an issue are opened; the revert is never merged automatically.

Any other change on `dev-mcphub` keeps the manual release PR. Enable with the repository variable `MCPHUB_AUTO_PROMOTE=true`; pause by setting it to `false` or by labelling the release PR `hold`.

Use short-lived `feature/*`, `fix/*`, `refactor/*`, `test/*`, `docs/*`, `chore/*`, and `hotfix/*` branches where useful, targeting the corresponding App development branch.

## Calibre AIO development installation

Calibre images are built and acceptance-tested on native amd64/aarch64 runners
before publication to `ghcr.io/hypercrisis/{arch}-calibre-aio:<version>`.
The generated Dev store waits for both public version tags before advertising
the candidate, so Home Assistant pulls the image instead of building locally.
Candidates are handed between jobs as a Git bundle; the installed version,
build label and registry tag use the same generated version. Existing tags
cannot be replaced with different app contents. Shared store publication is
serialized so an older candidate cannot overwrite a newer one.

`publish-calibre-images.yml` can also publish the current `main` or
`dev-calibre` version manually. The manual Calibre promotion workflow publishes
both tested images before opening a Stable release PR. The app configuration
must contain `image: "ghcr.io/hypercrisis/{arch}-calibre-aio"` to enable pulls.
New GHCR packages must be public: publication checks anonymous registry access
and fails before updating the Dev store if access is restricted. Private app
settings and library data never enter the build context.

Refresh the existing `#dev-store` repository and install **Calibre AIO (Dev)**.
The generated version uses `-dev.<revision>` and separate default library/import
folders under `/share/calibre-aio-dev`. Never run stable and development apps
against the same writable library/import paths. Existing configured paths are
not migrated. The regular Calibre app on `main` changes only on a separate release.

The daily Calibre updater opens ready-for-review PRs against `dev-calibre`,
never directly against `main`. `merge-due-updates.yml` merges them after 12
hours with passing validation, exactly like MCPHub and Trilium updates.

### Automatic Calibre AIO update releases

`auto-promote-calibre.yml` merges `dev-calibre` into `main` without manual
review only when every gate in `.github/scripts/auto_promote_calibre.py` passes:
`dev-calibre` holds nothing but GitHub-signed squash merges of bot PRs titled
`chore(calibre-aio): update CWA to … and Shelfmark to …` plus clean merges of
`main`; the diff changes only the CWA/Shelfmark pins, the generated build
arguments, the App patch version and generated changelog lines; major upstream
versions stay manual; each new upstream release is stable and at least 48 hours
old; the newest update has been on `dev-calibre` for 36 hours; and
`validate-calibre-aio.yml` passed for that exact commit. A failing stable
validation after the merge opens a revert PR and an issue.

Any other change keeps the manual release PR prepared by `promote.yml` (app
`calibre`) after live HAOS testing. Enable with the repository variable
`CALIBRE_AUTO_PROMOTE=true`; pause by setting it to `false` or by labelling the
release PR `hold`.

## Inbox Zero

Inbox Zero packages the fork
[HyperCriSiS/inbox-zero](https://github.com/HyperCriSiS/inbox-zero), which
publishes no releases and no images. The App therefore pins one commit of the
fork's `main` branch:

- `build-inbox-zero-base.yml` builds the fork's own `docker/Dockerfile.prod` at
  that commit for both architectures and publishes
  `ghcr.io/hypercrisis/inbox-zero-base:<commit>` once per commit.
  `validate-inbox-zero.yml` calls it, so the base image exists before a pull
  request can be merged.
- `Inbox Zero/Dockerfile` starts `FROM` that image and adds PostgreSQL, Redis,
  the Redis HTTP adapter and the scheduler. `publish-inbox-zero-images.yml`
  publishes it as `ghcr.io/hypercrisis/{arch}-inbox-zero:<version>`.
- `update-inbox-zero.yml` proposes the newest fork commit daily against
  `dev-inbox-zero` and names the newest upstream release that commit contains.

All three GHCR packages must be public.

### Automatic Inbox Zero update releases

`auto-promote-inbox-zero.yml` merges `dev-inbox-zero` into `main` without manual
review only when every gate in `.github/scripts/auto_promote_inbox_zero.py`
passes: `dev-inbox-zero` holds nothing but GitHub-signed squash merges of bot
PRs titled `chore(inbox-zero): update to <commit> (<base version>)` plus clean
merges of `main`; the diff changes only the commit pin, the base version, the
App version and generated changelog lines; a new upstream major version stays
manual; the new commit continues the history of the released one, is on the
fork's `main` branch and is at least 48 hours old; the newest update has been
on `dev-inbox-zero` for 36 hours; and `validate-inbox-zero.yml` passed for that
exact commit. A failing stable validation after the merge opens a revert PR and
an issue.

Any other change keeps the manual release PR prepared by `promote.yml` (app
`inbox-zero`) after testing in Home Assistant. Enable with the repository
variable `INBOX_ZERO_AUTO_PROMOTE=true`; pause by setting it to `false` or by
labelling the release PR `hold`.
