# Calibre AIO verification

## Automated checks

```sh
python -m pip install -r 'Calibre AIO/tests/requirements.txt'
python 'Calibre AIO/scripts/upstreams.py' check
python -m unittest discover -s 'Calibre AIO/tests' -v
```

The workflow also uses the real pinned CWA login library, tests nginx routing
from the actual Supervisor source address, checks a root-to-unprivileged
transition with real file permissions, and builds the complete image on
native amd64 and arm64 runners. Container probes exercise the real CWA and
Shelfmark processes, UI prefixes, reader/admin access and Socket.IO. A real
upstream Socket.IO client verifies stale admin sessions are replaced with
the current reader's scope. A generated EPUB goes through Shelfmark's native
folder output and CWA's native ingest processor; the probe checks the final
Calibre database for that book. This offline probe does not contact providers.

The additional `boot-smoke.sh` starts the image using its actual `/init`,
without manually creating `/config` or starting services. A minimal Supervisor
HTTP fixture supplies the ingress entry. The production ingress ACL stays
unchanged, and requests originate from the fixture at `172.30.32.2`. The test
checks both applications after first boot and restart with persistent volumes.

## Live HAOS acceptance

1. Add the repository (or the PR branch for pre-merge tests), install
   **Calibre AIO** and verify the app
   name/version. Use the default separate `calibre-aio/` test folders.
2. Set `sso.admin_username` to the test administrator's HA login name and start
   the app. Open the interface with that account. Both tabs must work without
   another login; confirm Shelfmark settings and CWA admin access.
3. Check a normal HA user gets its own Shelfmark request account and CWA
   reader account. Try a second HA admin (a normal app user unless selected)
   and a same-browser user switch. Change `sso.admin_username`, restart the app
   and verify the old selected account loses app admin rights. Reusing a login
   name with another HA ID must not inherit its existing administrator binding.
4. Configure your actual source/indexer and debrid/download account in
   Shelfmark. Request/download a book you may access. Watch the completed
   file arrive in CWA's import folder, then appear in the library. Test a
   cover, reading, download and a CSRF-protected CWA operation.
5. Restart the app and HA. Accounts, settings, library contents and source
   credentials must persist; temporary files must not be imported as books.
6. Verify both application ports reject access from other containers/LAN.
   Only Supervisor may reach the ingress listener. Forged HA headers outside
   that boundary must not grant access.
7. Back up private app data and the separate library share. Restore on a test
   installation and verify both app settings and the library.
8. Test a manifest-generated upstream update in a separate proposal branch.
   Both architecture builds and probes must pass. Do not promote a version
   solely because the updater generated a PR.

Real provider accounts and live HAOS behavior cannot be certified by unit
tests. Record HAOS/Supervisor versions, architecture and results in the PR.
The initial release remains experimental until these checks have passed.
