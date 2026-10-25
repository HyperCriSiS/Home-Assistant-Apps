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

The scheduled `update-calibre-aio.yml` runs weekly after this app is merged
to the default branch and creates/updates a draft PR. The script can also be
run manually on a development branch. Since GitHub does not normally trigger
new workflows from PRs created with its own `GITHUB_TOKEN`, the update workflow
explicitly dispatches `validate-calibre-aio.yml` on the proposal branch. This
starts the tests and both architecture builds automatically. A failed dispatch
fails the updater; never assume an update is tested merely because the PR
exists. Verify the validation run belongs to the proposal's current commit
before promotion. Automatic merge is disabled.

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
Live HAOS acceptance remains required for releases; unit/container checks
cannot validate your Supervisor version, mount layout or private providers.

Python/runtime and container-build infrastructure pins are maintained
separately when required by an upstream change. `uv.lock` is respected for
Shelfmark; CWA keeps its upstream requirements in a separate venv. This avoids
forcing two unrelated dependency stacks into one environment.
