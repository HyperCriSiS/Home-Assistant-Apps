# App standards: the shape of every App folder

Every App in this repository ships the same set of files, in the same shape, so
that readers, Home Assistant and the shared automation find the same things in
the same places. This page is the reference for that shape. The release chain
and its checklist live in [APP-AUTOMATION.md](APP-AUTOMATION.md); branch
semantics in [BRANCHING.md](../../BRANCHING.md). Trilium Notes is the smallest
complete example, MCPHub the most complete one.

## Folder layout

| File | Required | Purpose |
| --- | --- | --- |
| `config.yaml` | yes | Home Assistant App manifest (see below) |
| `build.yaml` | if the image is built from a pinned base | Pinned `build_from` per architecture |
| `publish-<app>-images.yml` (in `.github/workflows`) | yes | Builds, tests and publishes immutable version tags to GHCR; `image:` in `config.yaml` points at them, Home Assistant never builds locally |
| `Dockerfile` | yes | Build of the App image |
| `README.md` | yes | Installation and overview for the GitHub and store page (see skeleton) |
| `DOCS.md` | yes | Configuration reference shown in the Home Assistant "Documentation" tab |
| `CHANGELOG.md` | yes | Release notes, newest first (see format) |
| `LICENSE` | yes | MIT license of the wrapper code maintained here |
| `NOTICE.md` | if third-party software is packaged | Third-party components with packaged versions and licenses |
| `LICENSE-<component>` | if an upstream license must ship alongside | Verbatim upstream license texts |
| `translations/en.yaml`, `translations/de.yaml` | yes | Option names and descriptions for the HA configuration form |
| `icon.png`, `logo.png` | yes | Store icon (square) and logo; keep `logo.svg` when a vector source exists |
| `tests/` | yes when the App has own code | Unit tests and container checks run by `validate-<app>.yml` |
| `rootfs/`, `scripts/` | as needed | Container file system overlay and maintenance scripts |
| Further `*.md` | optional | App specific design, testing or update notes, each linked from the App README and from `docs/DOCUMENTATION.md` |

Localized documentation (`DOCS.de.md`) is optional; when it exists, the English
`DOCS.md` links to it in its first lines and both stay in sync.

## config.yaml

- Key order: `name`, `description`, `version`, `slug`, `url`, `image` (when
  prebuilt images are published), then `init`, `arch`, panel and startup keys,
  `backup`, `backup_exclude`, ingress and port keys, `map`, `options`, `schema`.
- `description` names the packaged upstream version(s), for example
  `Trilium v0.106.1 - ...` or `CWA 4.0.8 and Shelfmark 1.6.1 - ...`, so the
  store entry shows what is installed.
- `version` is quoted. The repository scheme is CalVer `vYYYY.MM.DD`, with
  `-N` for a second release on the same day; development stores add
  `-dev.<n>`. An App that still uses another scheme documents the reason in its
  README "Versioning" section and converts at its next release.
- `url` points at `https://github.com/HyperCriSiS/Home-Assistant-Apps/tree/main/<folder>`.
- `options` and `schema` list the same keys in the same order; related options
  are grouped in a map (`sso:`, `shelfmark:`). Every option appears in every
  translation file.
- `backup` is `cold` when the App keeps SQLite databases, otherwise `hot`.
  `backup_exclude` lists caches and transient folders, and the App DOCS state
  what the App backup contains and what lives under `/share`.

## README skeleton

1. The App icon, centered, 128 px wide, as an absolute
   `raw.githubusercontent.com` URL, then `# <App name>` and a one-line bold
   tagline.
2. Badge row: validate workflow, one upstream version badge per packaged
   upstream (linked to the upstream release), `amd64`, `aarch64`, Home
   Assistant, `license-MIT`.
3. Intro paragraph, then `> [!IMPORTANT]` notes (HAOS or Supervised required;
   legal notes where downloads are involved).
4. `## Installation` with `### Stable` and `### Development testing`, each
   with the my.home-assistant.io button and the plain repository URL, and the
   `> [!WARNING]` about development builds.
5. App specific sections (first start, features, access).
6. `## Configuration` or a pointer to `DOCS.md`, `## Data and backups`,
   `## Troubleshooting`, `## Support` (issues link), `## License` (wrapper
   license plus a pointer to `NOTICE.md` for third-party components).
   MCPHub adds `## Versioning` and `## Updating`; add them when the App's
   scheme or update path needs explanation.
7. Every `##` heading in the README and in `DOCS*.md` starts with an emoji.
   Fixed ones: ✨ Features, 📦 Installation, 🚀 First start / Getting started,
   ⚙️ Configuration / App options, 💾 Data and backups / Persistence,
   🩺 Troubleshooting, 💬 Support, 📄 License, 🏷️ Versioning, 🔄 Updating.
   Other sections get a fitting emoji of their own, never one twice per file.
   Anchors then start with `-` (`#-troubleshooting`); avoid emojis with a
   variation selector (⚙️, 🛠️) on headings that are linked by anchor.

Links in the README and in DOCS files are absolute GitHub URLs, in-page anchors included
(`https://github.com/HyperCriSiS/Home-Assistant-Apps/blob/main/<folder>/<file>`).
Home Assistant renders the README on the App page and `DOCS.md` in the
Documentation tab and resolves relative links against its own address, so
`DOCS.md` would only reopen the same page.

## DOCS.md structure

- `# <App name> documentation`.
- Getting started, then one `### \`option\`` heading per option (grouped
  options as `### \`group.option\``), each with default, allowed values and
  effect. A YAML example of the full options block precedes the headings.
- Persistence and backups with a table of container paths, then
  Troubleshooting. Keep release history out of DOCS; it belongs in the
  changelog.

## CHANGELOG format

```markdown
# Changelog

## v2026.11.09

### Changed

- ...

### Fixed

- ...
```

Newest release first, the first `##` heading equals `config.yaml` `version`.
Updater bots add their line under `### Changed`. Versions carry no dates in
the heading; the date is the version.

## Translations

`translations/<lang>.yaml` holds `configuration:` with `name` and
`description` per option and `fields:` for grouped options; `network:` for
exposed ports. English and German are required; the German text uses the
informal "Du".

## Licensing and attribution

The wrapper code is MIT licensed (`LICENSE`, copyright HyperCriSiS). Packaged
third-party software is listed in `NOTICE.md` as "Third-party components" with
project link, version currently packaged and license, and its license text is
shipped as `LICENSE-<component>` where the upstream license requires it. The
README license section repeats this in two sentences.

## Validation

`validate-<app>.yml` runs on pull requests, on pushes to `main` and
`dev-<app>` and on dispatch, and covers at least: yamllint, hadolint for the
Dockerfile, the manifest assertions (slug, version format, description prefix,
`backup`, `map`), the changelog head, README badges, translations covering
every option, the App's unit tests and a container smoke test. Trigger paths
include the App folder, `.yamllint`, `.github/tests/**` and the scripts the
workflow uses.

## Language and style

Everything in the repository is American English: code, comments, commits,
pull requests, documentation and UI strings. German exists only in
`translations/de.yaml` and in an optional `DOCS.de.md`. No em dash character.
