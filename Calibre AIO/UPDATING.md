# Updating upstream components

`upstream.json` is the source of truth for CWA and Shelfmark release tags,
immutable commits and archive SHA-256 checksums. It also records Calibre,
kepubify and Shelfmark's independent Python version. `build.yaml` is generated;
never edit its pin values independently.

```sh
python 'Calibre AIO/scripts/upstreams.py' update
python 'Calibre AIO/scripts/upstreams.py' check
```

Use `update --component cwa` or `update --component shelfmark` to isolate an
upgrade. The script resolves stable releases via GitHub, verifies the tag's
commit, downloads the exact archive, hashes it, updates the manifest and
generated HA build arguments, bumps the app patch version and adds release
notes. It refuses prereleases, downgrades and changed provenance for an
already-pinned release. Network/provenance failures stop the proposal.

`update --cwa-version vX.Y.Z --shelfmark-version vX.Y.Z` pins exact releases
instead of the latest ones; the automation uses it to reproduce a proposal.

### Automated update releases

Like MCPHub and Trilium, upstream updates move to stable without manual work
when every gate passes:

1. `update-calibre-aio.yml` runs daily against `dev-calibre`. For a new stable
   CWA or Shelfmark release it opens a ready-for-review PR from
   `automation/calibre-aio-cwa-<version>-shelfmark-<version>` titled
   `chore(calibre-aio): update CWA to … and Shelfmark to …`, and dispatches
   `validate-calibre-aio.yml` (tests, native amd64/aarch64 builds, container
   acceptance and real s6 boot/restart) on that branch.
2. `merge-due-updates.yml` squash-merges the PR into `dev-calibre` once it has
   been open for 12 hours, the validation dispatched by the bot passed for its
   exact HEAD, and its content is byte for byte what main's trusted updater
   produces for those two versions. A PR that fell behind is regenerated and
   validated again; anything unexpected gets the `hold` label. The merged
   candidate appears as **Calibre AIO (Dev)** in `#dev-store`.
3. `auto-promote-calibre.yml` merges `dev-calibre` into `main` when
   `dev-calibre` contains only such bot updates (plus clean merges of `main`),
   the diff changes only the CWA/Shelfmark pins, the generated `build.yaml`,
   the App patch version and the generated changelog lines, each new upstream
   release is a stable release at least 48 hours old, the newest update has
   been on `dev-calibre` for 48 hours, and validation passed for that exact
   commit. A failing stable validation after the merge opens a revert PR and an
   issue; the revert is never merged automatically.

Major upstream versions and any other change (adapters, Dockerfile, Calibre,
kepubify or Python pins) stay on the manual release PR (`promote.yml`, app
`calibre`) after the live HAOS checks in [TESTING.md](TESTING.md). Enable
automatic promotion with the repository variable `CALIBRE_AUTO_PROMOTE=true`;
pause it with `false` or by labelling the release PR or an update PR `hold`.

Our adapters, nginx routes, s6 services and navigation shell live under
`rootfs/`; upstream sources are fetched during the image build and remain
unmodified. There is no source patch rebase or blind three-way merge. The
integration tests check the upstream hooks and actual applications; if an
upstream contract changes, the failing check identifies the adapter to fix.
The eight CWA background/bootstrap service entry points are thin forwarding
wrappers into the pinned upstream source tree. Their implementation updates
automatically with CWA; HA-specific service dependencies remain in this repo.
The image build checks that each required upstream script exists and parses.
CWA's in-app source replacement endpoint is blocked: update the HA App image
so versions and provenance stay aligned with the manifest.

The validation workflow checks the manifest, auth/permission tests and real
nginx routing, then builds on native amd64 and arm64 runners and exercises
both applications inside the final image. New pins must pass those checks.
Live HAOS acceptance remains required for manual releases; unit/container
checks cannot validate your Supervisor version, mount layout or private
providers.

Python/runtime and container-build infrastructure pins are maintained
separately when required by an upstream change. `uv.lock` is respected for
Shelfmark; CWA keeps its upstream requirements in a separate venv. This avoids
forcing two unrelated dependency stacks into one environment.
