# Agent instructions

- Start with [README.md](README.md) and [documentation navigation](docs/DOCUMENTATION.md).
- No dedicated repository-wide `ROADMAP.md` is currently present. Do not invent project completion claims or create one automatically.
- Preserve existing behavior, release paths, and any branch conventions. Make implementation changes in a reviewable pull request and verify applicable checks.
- The repository contains multiple Home Assistant add-ons. Check add-on-local build and configuration files before changing one.
- Every add-on ships a prebuilt image: `image:` in `config.yaml` plus a `publish-<app>-images.yml` workflow that builds, tests and publishes immutable version tags to GHCR before `main` or `dev-store` advertise them. Home Assistant must never build an add-on locally, because the Supervisor stores locally built images inside every backup and rebuilds on every update. See [docs/engineering/APP-AUTOMATION.md](docs/engineering/APP-AUTOMATION.md).
