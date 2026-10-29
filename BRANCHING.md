# Branching workflow

This repository uses separate long-lived development branches per Home Assistant App.

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

Development branches periodically merge the latest `main` so they inherit already released changes from the other Apps without inheriting their unreleased work.

## `dev-store`

`dev-store` is a generated Home Assistant testing repository. It is composed from:

- `TriliumNext Notes/` from `dev-trilium`
- `MCPHub/` from `dev-mcphub`
- `Calibre AIO/` from `dev-calibre`
- shared repository content from `main`

Home Assistant development repository URL:

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

Old repository URLs are kept operational by GitHub redirects after the rename. For new Home Assistant installations, use the new `Home-Assistant-Apps` URL; existing installations should not register both URL variants, because Home Assistant derives different repository IDs from them.

The generator adds `(Dev)`, `-dev.<run>`, and `stage: experimental` metadata so test installations are clearly distinguishable.

**Never edit `dev-store` manually and never merge it into `main`.**

## Release flows

```text
Trilium work -> dev-trilium -> dev-store -> HA test -> main
MCPHub work  -> dev-mcphub  -> dev-store -> HA test -> main
Calibre work -> dev-calibre -> dev-store -> HA test -> main
```

A Trilium release PR is always `dev-trilium -> main`. An MCPHub release PR is always `dev-mcphub -> main`. This prevents one App's unreleased work from being published with the other App.

### Automatic MCPHub update releases

`auto-promote-mcphub.yml` merges `dev-mcphub` into `main` without manual review only when every gate in `.github/scripts/auto_promote_mcphub.py` passes:

- `dev-mcphub` contains nothing but GitHub-signed squash merges of bot PRs titled `chore(mcphub): update upstream to …` or `chore(mcphub): update OpenAI tunnel client`, plus clean, unedited merges of `main`.
- The diff to `main` is only those version bumps and their generated changelog lines. Major version updates stay manual.
- The new MCPHub and tunnel-client releases are stable and at least 48 hours old. The newest update has been on `dev-mcphub` for at least 48 hours. The previous stable MCPHub release is at least 24 hours old.
- `validate-mcphub.yml` and the Home Assistant OS test (`haos-qemu-mcphub.yml`) both passed for that exact commit. That test boots a disposable official Home Assistant OS VM on a GitHub-hosted runner, installs, builds, starts and restarts MCPHub, and probes Ingress and the LAN MCP port.
- The release candidate is validated again and merged only if `main`, `dev-mcphub` and the candidate commit are unchanged. If stable validation fails after the merge, a revert PR and an issue are opened; the revert is never merged automatically.

Any other change on `dev-mcphub` keeps the manual release PR. Enable with the repository variable `MCPHUB_AUTO_PROMOTE=true`; pause by setting it to `false` or by labelling the release PR `hold`.

Use short-lived `feature/*`, `fix/*`, `refactor/*`, `test/*`, `docs/*`, `chore/*`, and `hotfix/*` branches where useful, targeting the corresponding App development branch.

## Calibre AIO development installation

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
old; the newest update has been on `dev-calibre` for 48 hours; and
`validate-calibre-aio.yml` passed for that exact commit. A failing stable
validation after the merge opens a revert PR and an issue.

Any other change keeps the manual release PR prepared by `promote.yml` (app
`calibre`) after live HAOS testing. Enable with the repository variable
`CALIBRE_AUTO_PROMOTE=true`; pause by setting it to `false` or by labelling the
release PR `hold`.
