# 1.2.5

- Prevent titles, sorting controls and the search field from shifting while library views load.
- Keep the Duplicates layout steady while its controls initialize.

# 1.2.4

- Add a folder picker to the Add Books menu, including supported ebooks in subfolders.
- Align Browse and Duplicates titles and sort controls in a shared page header.
- Show the current page title on mobile, with a horizontally scrollable sort bar and compact separators.
- Make navigation sections collapsible on desktop and mobile, with larger text in the mobile menu.
- Compact duplicate groups and place automatic resolution in an expandable panel.
- Simplify Magic Shelves headers to sorting, refresh and edit controls, and remove the Downloads explanation text.
- Fix Series grid cards being affected by list-row styles.
- Make Back return through the library's browser history.

# 1.2.3

- Refuse an empty or absolute `library_dir` or `ingest_dir`, dot segments and
  identical folders instead of using `/share` itself or container-local paths.
- Verify the Calibre and kepubify downloads against pinned SHA-256 checksums
  from `upstream.json`.
- Keep the service definitions owned by root instead of the service account.
- Send `Cache-Control: no-store` only for the App's own shell page; CWA and
  Shelfmark assets keep their own caching headers.
- Treat a failed registry check as an error instead of a missing release tag
  when publishing installation images.
- Explain the GitHub release check of CWA's init script; bring the German
  documentation up to date with the English one.
- Center sort controls beside the page title and compact the author/category
  list icons, letter filters and rows without changing native filtering.
- Align the library search icon, input and submit button in a dark field.
- Explain the user-download overview and show an empty state when no Calibre
  Web downloads have been recorded; Shelfmark imports are separate.

# 1.2.2

- Keep version labels and deployment files after large package/ownership layers,
  so small updates can reuse the Calibre, Python and Chromium downloads.
- Verify identical filesystem layers when only the build version changes.

# 1.2.1

- Install prebuilt, tested amd64/aarch64 images from GHCR instead of building
  Calibre, Shelfmark and Chromium on the Home Assistant host.
- Publish development updates only after both public image versions are ready.

# 1.2.0

- Add the first Modern library theme: restrained graphite surfaces, muted gold
  accents, denser book grids, compact controls and consistent sort symbols.
- Sort direction now uses a separate up/down arrow; alphabetical labels stay
  upright. Native sort links and tooltips remain available, including on mobile.
- Set `library_theme: upstream` to return to the original CWA appearance.

# 1.1.4

- Fix library ownership behind the persistent storage symlink, including
  metadata.db created on first boot, so CWA can import Shelfmark downloads.
- Verify database and library-directory write access as the service user
  before starting CWA; report inaccessible network shares clearly.

# 1.1.3

- Remove the retired local browser service from existing installs, so Shelfmark
  uses its built-in browser after updating.

# 1.1.2

- Fix the book import service restart loop: upstream CWA service scripts are
  now executable, so completed downloads reach the library.

# 1.1.1

- Give Shelfmark's internal browser the writable runtime paths it needs as the
  service user, so bypass requests can start it.
- Start automatically as a regular application and let the Home Assistant
  watchdog restart the app when its web server stops responding.
- Stop the app during backups so its databases are captured consistently.

# 1.1.0

- Include Shelfmark's browser stack and Chromium, so browser-challenge sources
  work without an extra service. The image grows accordingly.
- Move to the Debian trixie Home Assistant base image required by that Chromium.
- Unlock Shelfmark's bypass settings unless `shelfmark.external_bypass_url` is set.

# 1.0.1

- Remove the tagline from the navigation bar.

# 1.0.0

- First stable release; the experimental designation is removed.
- Add store icon and logo.
- Upstream updates are now proposed daily, merged into the development
  branch after 12 hours with passing validation and released to stable
  after another 36 hours. Major upstream versions stay manual.
- Upgrading from 0.1.2: an empty administrator setting is now filled
  automatically with the signed-in HA administrator when the interface is
  first opened; an existing assignment is kept.

# 0.1.7

- Update CWA to v4.0.8 and Shelfmark to v1.5.1.

# 0.1.6

- Enable Supervisor ingress streaming so POST uploads larger than 16 MiB reach
  the app instead of failing in Supervisor's request-body buffer.
- Verify uploads over 25 MiB through both production nginx backend routes.

# 0.1.5

- Keep Shelfmark's native Go To Library link inside the shared AIO workspace,
  retaining navigation and avoiding an extra browser tab on a normal click.
- Automatically reload after administrator setup once the configured shell
  and both applications are reachable. Wait through temporary startup failures
  and stop polling with a clear message if readiness cannot be confirmed.

# 0.1.4

- Fix administrator setup: use HA's supervisor/api WebSocket transport and its
  unwrapped responses, matching the native HA app configuration interface.
- Automatically configure the signed-in HA administrator on first opening an
  unconfigured installation; preserve existing administrator assignments.
- Show the failed setup step and offer retry after an error. No new API permission.
- Cover denied writes, empty successful responses, existing configuration and
  missing login names in browser regression tests.

# 0.1.3

- Add German and English HA option labels, navigation and setup.
- Start safely with an empty administrator setting and offer to adopt the
  signed-in HA administrator using HA's permission-checked APIs.
- Keep manual setup available without granting the app HA API access.
- Develop on dev-calibre and publish separately through the shared dev store.

# 0.1.2

- Use a compact navigation bar with Bibliothek first.
- Open the library by default; make the initial page configurable with start_page.
- Hide the administrator-only Shelfmark setup wizard for reader sessions.
- Select the app administrator by sso.admin_username, automatically bind the
  login to its HA ID, and ignore group headers. Works on stable Supervisor
  without additional HA API access. Configure the login name before starting.

# 0.1.1

- Fix first boot: wait for HA storage and ingress preparation before CWA init.
- Test the actual s6 container boot and restart with persistent storage on both architectures.
- Remove the manual administrator ID list from the HA options; roles come from HA automatically.

# 0.1.0

- Introduce Calibre AIO with Shelfmark discovery/downloads and CWA library
  management in a shared Home Assistant ingress interface.
- Carry forward automatic HA roles, separate reader identities and the
  Supervisor options permission fix from the CWA SSO feature branch.
- Use independent Python environments and private state for each application.
- Stage downloads separately and deliver completed ebooks to CWA's ingest path.
- Pin upstream source commits/checksums in one manifest and add automated
  update proposals, adapter tests, architecture builds and container probes.
- Initial core Shelfmark image; browser-challenge sources use an optional
  external bypass service. Real provider credentials and live HAOS testing
  remain operator-side acceptance steps.
