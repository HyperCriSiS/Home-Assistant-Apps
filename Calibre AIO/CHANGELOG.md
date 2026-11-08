# 1.2.22

- Random picks fill exactly one row per screen width (2 to 12 cards); set "No. of Random Books to Display" to 12 in the CWA admin view for wide screens.

# 1.2.21

- Phones: the grid no longer starts under the band on pages with page navigation, the drawer sits flush with the viewport instead of 15px off the left edge, and the random picks show only a full row.
- Hide the logout entry; ingress signs the user in again anyway.

# 1.2.20

- Label the random picks above the library as their own section so their partial row no longer looks like a hole in the grid.
- Drawer: the section plus follows its heading, the Magic Shelves heading drops the extra upstream gap, and shelf emoji share the icon column.

# 1.2.19

- Extend the standalone theme to the secondary pages: tokens for selects, checkbox labels, progress bars, tabs, tooltips, modal and panel headers, contextual text and buttons, the CWA statistics cards, and skins for bootstrap-table, x-editable, bootstrap-select, typeahead, the date picker and the query builder.
- Define the caliBlur-only CSS variables that CWA templates reference inline.
- The error and shelf download pages load the theme as well.

# 1.2.18

- Cover the read marker on book cards with a fixture scenario: a small disc inside the lower left of the cover.

# 1.2.17

- Make the Modern theme standalone: CWA's caliBlur theme is no longer loaded; the library pages, sidebar, navbar, search, upload menu, pagination, list pages, series grid and duplicates are styled on CWA's standard templates with the viewport as the only scroll container.
- Covers and titles open the book page instead of the detail modal; a history-driven back arrow sits beside the search box.
- The browse navigation joins the navbar drawer below 768 px.
- Fix the stray glyph in the upload menu on phones.

# 1.2.16

- Keep the scrollbar gutter of the content column stable, so the book grid is laid out at the same width before and after Isotope measures it where scrollbars take layout space (Android WebView, desktop).
- Render the page navigation before the list, so the title band has its final height at first paint.

# 1.2.15

- Update CWA to v4.0.8 and Shelfmark to v1.6.1.

# 1.2.14

- Lay book and series grids out without the Isotope slide animation, so relayouts after a viewport change no longer glide into place.

# 1.2.13

- Follow Shelfmark 1.6.1, which registers its Socket.IO handlers and proxy authentication as closures; the ingress session refresh now takes them from the Flask and Flask-SocketIO registries.

# 1.2.12

- Keep the page title in the desktop sidebar and remove its repeat from the content band; sorting stays centered in the band.

# 1.2.11

- Refuse a library folder inside the ingest folder or the reverse, not only identical folders.
- Keep the Supervisor token out of every upstream CWA service and the ingress proxy.
- Start Shelfmark only after the library database has been prepared and repaired.
- Forward the HTTPS scheme reported by the Supervisor instead of the proxy's own.
- Validate `shelfmark.external_bypass_url` in Shelfmark only, so a bad value no longer stops the library.
- Document the folder rules in English, folder upload and mobile layout in German, and mark the integration plan as history.

# 1.2.10

- Follow the Shelfmark 1.6 Chromium 156 pin, Python 3.14.9 and uv 0.13.6 so the upstream updater can propose Shelfmark releases again.

# 1.2.9

- Use the Modern system font for navigation section headings instead of the inherited bold caliBlur face.
- Remove the decorative sparkle from the Magic Shelves label; its plus action stays.
- Hide the duplicate desktop sidebar title and keep the title band and mobile navbar title.

# 1.2.8

- Replace separate shelf creation entries with plus actions beside Shelves and Magic Shelves.
- Make navigation section headings slightly larger than their menu items on desktop and mobile.

# 1.2.7

- Keep Series grid rows in place while the view loads.
- Vertically center page numbers and navigation arrows in the desktop title bar.
- Place mobile sorting below a separate page-navigation row when a view has multiple pages.
- Match the spacing below navigation section headings to the spacing between menu items.
- Keep Back navigation working when the browser suppresses referrers, including after a reload.

# 1.2.6

- Show Modern sorting icons immediately when switching library views.
- Keep the search icon compact while the page loads.

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
