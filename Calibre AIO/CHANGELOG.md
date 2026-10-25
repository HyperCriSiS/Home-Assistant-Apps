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
