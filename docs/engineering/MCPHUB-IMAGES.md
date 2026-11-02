# MCPHub prebuilt images

MCPHub uses `ghcr.io/hypercrisis/mcphub:<App version>`. One manifest contains
`linux/amd64` and `linux/arm64` (`aarch64` in Home Assistant metadata).
The slug, persistent paths, ports, privileges and supported architectures stay
the same. Existing installations receive the prebuilt image as a normal update.

## Publication

`validate-mcphub.yml` publishes only after validation succeeds, for `main` and
the same-repository `release/mcphub-candidate` branch. This includes candidate
PR validation and the candidate workflow dispatch used by automatic promotion.
Publish the candidate successfully before merging it: the version must already
be available when main advertises it. Main rechecks the existing image instead
of overwriting it. Ordinary PRs and forks cannot publish packages.

`sync-dev-store.yml` generates the development version and saves the candidate
as the existing immutable store bundle used for Calibre publication. Both image
publishers consume that same bundle; the generated store is pushed only after
both have succeeded, including anonymous access checks. MCPHub publication is
serialized across both workflows. Store generation is not
cancelled while running. Changed sources use the workflow run number (or the
next stored revision, whichever is higher), avoiding reuse of a tag published
by a run that failed before pushing the store. Retry an unchanged failed run
after resolving the cause; use a new run after changing the source.

The shared publisher builds both architectures with Buildx, runs the container
integration test and bundled-client startup checks for each (ARM64 under QEMU),
then pushes the per-architecture images and creates the versioned manifest.
No `latest` tag is used. Anonymous registry requests check both manifest entries
and their actual configuration labels, including version, architecture and a
SHA-256 fingerprint of the Dockerfile, build metadata and copied runtime files.
Existing version tags with different build inputs cause an error requiring a
new App version. Release-note-only changes and merge commit IDs do not force a
rebuild of identical packaged code. Each new image includes its original source
commit in its OCI revision label and the startup log. For development-store
images this is the bundled candidate commit that is later pushed to `dev-store`.

## First rollout

1. Ensure the updated shared store workflow is present on `main`, `dev-mcphub`,
   `dev-trilium` and `dev-calibre` before allowing a development branch to generate a
   store containing the new `image:` configuration. Older workflow copies do
   not publish images and must not advertise new prebuilt versions.
2. Run validation/publication for the release candidate. The workflow token
   needs `packages: write`; no personal registry token is needed.
3. GitHub initially creates a new container package as **Private**. After the
   first push, set the `mcphub` package visibility to **Public** in GitHub package
   settings. The anonymous-access check deliberately fails until this is done.
   Rerun publication to verify the already-published image without rebuilding it.
4. Verify candidate CI and the existing HAOS source tests. Install the candidate
   prebuilt image on a test Home Assistant system and check startup, Ingress,
   LAN MCP access, restart and retained configuration before the stable merge.
5. After merging, verify main validation/publication and the generated Dev store.

GitHub's default package visibility and Home Assistant's version/tag mapping are
documented in [GitHub Container Registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
and [Home Assistant publication documentation](https://contributors.home-assistant.io/apps/guides/publishing/).

## Source tests and local development

The existing HAOS harnesses remove `image:` only from their disposable local App
copy. They still build and test the exact selected source commit, including PRs
that have no published image. The checked-in App metadata retains `image:`.
These source tests do not replace a prebuilt-image installation smoke test.
Run `haos-qemu-mcphub.yml` with `prebuilt: true` after publication to exercise
the anonymous GHCR installation path. This mode removes the Dockerfile only
from the disposable VM copy, so a successful installation proves Supervisor
pulled the published image. It retains the start/restart, Ingress, LAN and
official/unofficial Home Assistant MCP tool checks used by the source test.
