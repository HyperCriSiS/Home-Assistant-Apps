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
- Wrap the existing permitted upload input in the plus menu and add a folder
  action. The script passes supported selected files to the original input;
  filenames remain basenames and browser directory paths are not server paths.
- Remove the redundant Downloads explanatory heading while retaining the empty
  state. The deployment adapter supplies the localized empty-state text.

The script moves existing headings and controls into a shared page band without
recreating their links or action handlers. Navigation sections keep their native
list items so CWA can still relocate the navigation between desktop and mobile.
Collapsed section preferences use optional local browser storage. Back uses the
browser history only for a referrer within the library's native home URL prefix.

The browser fixture renders the pinned upstream templates, including Series list
and grid views, duplicate groups, Magic Shelves and uploads. Its upload endpoint
is a local fixture; the container acceptance tests cover the actual ingest path.
An upstream submission still needs integration with upstream's theme switcher
and review there; this document does not imply upstream acceptance.
