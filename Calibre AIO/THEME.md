# Modern theme integration

The theme assets live in `rootfs/opt/ha-cwa/theme`. They use native CWA links,
upload permissions, multipart upload handling, duplicate actions and Isotope
sorting. They do not call Home Assistant or Shelfmark APIs.

`modern_theme.py` is the AIO deployment adapter. For an upstream submission,
integrate its template hooks into CWA's native theme selection instead of copying
the AIO launcher. The hooks are:

- Load the Modern stylesheet after CWA's base styles and the deferred script once.
- Add `aio-modern` to the HTML element and `aio-main` to the main content column.
- Render `aio-list-page` on list pages before any JavaScript runs, including the
  Series overview. This prevents the initial oversized caliBlur marker.
- Render the current page title in the navbar brand location.
- Render the final `aio-page-header` and its `aio-page-tools` in the templates,
  moving the existing native sort controls there before the response is sent.
  Reserve the same sort-control widths before and after SVG enhancement.
  Render the final sort SVGs there as well; JavaScript preserves these symbols
  and only supplies them as a fallback for other views. Give every SVG explicit
  width and height attributes so it remains compact without the stylesheet.
- Render the search symbols and navigation section buttons in the layout so
  their dimensions do not change when the deferred script starts.
- Render the compact duplicate-resolution disclosure and initial selection count
  in the template rather than rebuilding that panel after the first paint.
- Wrap the existing permitted upload input in the plus menu and add a folder
  action. The script passes supported selected files to the original input;
  filenames remain basenames and browser directory paths are not server paths.
- Remove the redundant Downloads explanatory heading while retaining the empty
  state. The deployment adapter supplies the localized empty-state text.
- Use native `fitRows` for the Series grid with matching initial flex rows.
  The adapter serves the pinned upstream `filter_grid.js` with only its layout
  mode changed; sorting, filtering and saved preferences remain native.
- Align pagination with the shared title band and give navigation headings and
  links the same row spacing on desktop and mobile.
  On paginated mobile views reserve a separate row above the sorting strip so
  page controls cannot overlap it, including during scrolling.

The script enhances the server-rendered controls and retains a header fallback
for other native views. It preserves their links and action handlers.
Navigation sections keep their native
list items so CWA can still relocate the navigation between desktop and mobile.
Collapsed section preferences use optional local browser storage. Back uses the
browser history with a previous library entry validated against its native home
URL prefix. History state preserves that entry across reloads; session storage
provides a tab-local fallback when the host suppresses referrers.

The browser fixture renders the pinned upstream templates, including Series list
and grid views, duplicate groups, Magic Shelves and uploads. It delays the theme
script to compare visible geometry before and after enhancement, including a
paginated book view. Its upload endpoint
is a local fixture; the container acceptance tests cover the actual ingest path.
An upstream submission still needs integration with upstream's theme switcher
and review there; this document does not imply upstream acceptance.
