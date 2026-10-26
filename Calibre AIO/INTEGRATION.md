# Calibre AIO integration plan

## Starting point

Copy of `calibre-web-automated/` from
`HyperCriSiS/hassio-addons-by-conallob`, branch `feature/cwa-ingress-sso`,
commit `44bd2067714f6dd513fe09b48085e849f25f3c7b` (test version 4.0.6.2).
Includes HA role-based SSO, stable internal ID bindings and the verified
Supervisor options permission fix. Original add-on attribution is retained.

## Design

1. Give the new app its own `calibre-aio` slug, version, data directories and
   store entry. Existing CWA installations are not migrated or overwritten.
2. Pin CWA v4.0.6 and Shelfmark v1.4.0. Build their frontends/dependencies at
   image build time. Keep CWA's Python environment and Shelfmark's Python 3.14
   environment independent on the official HA Debian base.
3. Supervise CWA and Shelfmark independently with s6. Bind both backends to
   loopback. Expose only the Supervisor-restricted ingress listener.
4. Provide a shared, responsive navigation shell: Discover (Shelfmark) and
   Library (CWA). Preserve each application's native interface and configure
   real URL prefixes, redirects, static assets, cookies and WebSockets.
5. Authenticate both through HA. Configure one HA login name as administrator,
   automatically bind it to its stable HA ID and share that binding between
   both applications. Other users get separate normal identities. This works
   with stable Supervisor versions without group headers or additional API
   access. Reject cookie/API-key/header impersonation. Changes to HA roles do
   not automatically change the configured app administrator.
6. Keep private CWA and Shelfmark state separate under `/data`. Shelfmark
   stages downloads privately and delivers completed files to CWA's ingest
   folder. Configure Real-Debrid and other sources in Shelfmark's native UI;
   no account credentials belong in source control or browser bootstrap data.
7. Test identity/roles, URL prefixes, uploads/downloads, WebSocket routing,
   shared delivery, process startup/restart and persistent state. Add image
   build and container smoke checks, then document live HAOS acceptance.
8. Keep upstream sources untouched. A central `upstream.json` manifest pins
   versions, commits and archive checksums. An update script regenerates build
   arguments from that manifest, and scheduled CI proposes update PRs rather
   than rewriting adapters or merging untested versions. The same build and
   integration checks gate upstream changes. Compatibility failures stay visible.

## Initial scope and limits

- All-in-one packaging and interface, not a replacement for either upstream UI.
- Ingress SSO is required for this initial AIO version. Native login/device
  sync endpoints do not become an additional network entry point.
- Start with Shelfmark's core download stack (including Real-Debrid). Sources
  requiring browser-based challenge handling need the supported external
  bypass service; do not embed an outdated pinned Chromium merely to hide
  this dependency. Document this limitation in the app UI/docs.
- Do not modify other apps or generated `dev-store`. Develop on `dev-calibre`;
  shared automation publishes Calibre AIO (Dev). Promote to `main` separately
  after operator testing.

## Verification record

- The application, shared interface, HA adapters and update automation are
  implemented on `feature/calibre-aio`; draft PR #103 tracks acceptance.
- Native amd64 and aarch64 image builds and real CWA/Shelfmark startup,
  identity, URL-prefix and Socket.IO checks passed at `fa4a209` in
  [validation run 40179062659](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/runs/40179062659).
- The updater was exercised against real upstream releases in an isolated
  copy. It resolved CWA v4.0.8 and Shelfmark v1.5.1, verified their archive
  checksums and generated consistent build arguments and app revision 0.1.1.
  These are update proposals; the initial tested integration pins remain
  CWA v4.0.6 and Shelfmark v1.4.0 from the starting design.
- Current-head CI results and the generated-book delivery/import probe are
  recorded in the PR. Check the run's commit before relying on its result.

Full HAOS acceptance and authenticated Real-Debrid downloads require a real
installation and operator credentials; automated tests must not claim those.

## Current development work

- German/English HA option labels and AIO navigation/setup are implemented.
- Empty administrator configuration now opens setup without granting admin.
  Automatic setup uses the signed-in HA administrator's permission-checked
  auth-list and app-options APIs; the app receives no extra HA API permission.
- Local adapter suite: 58 tests, with 5 Linux/root checks skipped on Windows.
  Browser regression covers admin setup, denied access, normal users, restart
  failure, missing HA context, both languages and compact mobile navigation.
- Native image builds and real s6 boot/restart remain required in CI for this
  candidate. Actual frontend embedding in the user's HA installation remains
  operator acceptance; manual login-name configuration stays available.

### Administrator setup correction (0.1.4)

- Replaced unsupported REST app-management calls with the native HA frontend's
  `supervisor/api` WebSocket messages. Responses are unwrapped by HA; successful
  writes need not return a result wrapper. The previous mock incorrectly accepted
  REST calls and wrapped responses, so its green result did not cover this bug.
- Setup runs automatically only for an HA administrator on an unconfigured
  installation, preserves an assignment found during the fresh options read,
  and identifies the failed step without exposing raw API errors or credentials.
- Browser regression now rejects the old REST transport and covers automatic
  setup, denied identity/write access, restart failure, existing assignment,
  unavailable login/context, normal users and German/English navigation.

### Navigation and setup completion (0.1.5)

- The deployment shell handles same-origin links from Shelfmark to its own
  CWA library inside the workspace; upstream sources remain unmodified.
- Successful setup polls the uncached shell and both backends before reload.
  Temporary connection errors are retried; polling is bounded and never
  resubmits setup options or restarts the app again.
- Browser regression covers the native target=_blank library link and
  automatic reload through a temporary ingress startup failure.
