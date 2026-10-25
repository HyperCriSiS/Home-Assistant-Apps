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
Shelfmark processes, UI prefixes, reader/admin access and Socket.IO.

## Live HAOS acceptance

1. Add the feature repository, install **Calibre AIO** and verify the app
   name/version. Use the default separate `calibre-aio/` test folders.
2. Open the interface as an HA administrator. Both tabs must work without
   another login; confirm Shelfmark settings and CWA admin access.
3. Check a normal HA user gets its own Shelfmark request account and CWA
   reader account. Try a second admin and a same-browser user switch. Revoke
   a test admin's HA role, open a fresh HA session and verify reader rights.
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
