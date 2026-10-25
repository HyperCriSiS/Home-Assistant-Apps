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
5. Authenticate both through HA. Automatically map HA administrators to app
   administrators; normal users get separate identities. Validate roles and
   IDs at the trust boundary, reject cookie/API-key/header impersonation and
   preserve the optional explicit ID selection for existing policies.
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
- Do not modify other apps or generated `dev-store`. Publish the new app on
  its feature branch for testing and prepare a draft PR before promotion.

## Verification record

Implementation and checks are recorded here only after they actually run.
Full HAOS acceptance and authenticated Real-Debrid downloads require a real
installation and operator credentials; automated tests must not claim those.
