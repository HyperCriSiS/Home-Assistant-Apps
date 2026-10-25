"""Run the pinned CWA release with optional Home Assistant ingress SSO."""

import json
import os
import sys

from ingress_sso import install, read_options


def load_options_and_drop_privileges(path='/data/options.json', account='abc'):
    # Supervisor protects options.json from unprivileged processes. Read and
    # validate it before dropping privileges; never relax that file's mode.
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle)
    options = read_options(document)
    # AIO never derives privileges from a group header: stable Supervisors do
    # not supply or sanitize that header. Require the configured HA login name.
    options['admin_username'] = options.get('admin_username', '')
    if options['enabled'] and not options['admin_username']:
        raise ValueError('Set sso.admin_username to your Home Assistant login name (not a user ID)')
    os.environ.pop('SUPERVISOR_TOKEN', None)
    os.environ.pop('HASSIO_TOKEN', None)
    bypass = document.get('shelfmark', {}).get('external_bypass_url', '')
    if bypass:
        from urllib.parse import urlsplit
        parsed = urlsplit(bypass)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or any(c.isspace() for c in bypass):
            raise ValueError('shelfmark.external_bypass_url must be an HTTP(S) URL')
    options['external_bypass_url'] = bypass
    import pwd
    user = pwd.getpwnam(account)
    os.initgroups(user.pw_name, user.pw_gid)
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)
    return options


def main():
    options = load_options_and_drop_privileges()
    # No CWA code is imported or executed until privileges have been dropped.
    if options['enabled']:
        policy = ('configured Home Assistant login name' if 'admin_username' in options
                  else 'explicit ID list' if options['admin_users'] else 'automatic Home Assistant roles')
        print('[ha-cwa] Ingress SSO enabled; admin policy: ' + policy, flush=True)
    else:
        print('[ha-cwa] Ingress SSO disabled; using CWA login', flush=True)
    sys.path.insert(0, '/app/calibre-web-automated')
    # Match cps.py's import/working-directory behavior.
    os.chdir('/app/calibre-web-automated')
    if options['enabled']:
        # CLI binding overrides CWA defaults. Never expose the trusted backend.
        sys.argv = [sys.argv[0], '-i', '127.0.0.1']
        os.environ['CWA_PORT_OVERRIDE'] = '8083'
        # Disable systemd socket activation, which otherwise bypasses -i.
        os.environ.pop('LISTEN_FDS', None)
        os.environ.pop('LISTEN_PID', None)
        os.environ.pop('CALIBRE_UNIX_SOCKET', None)
    import cps.main
    if options['enabled']:
        create_app = cps.main.create_app

        def create_ingress_app():
            app = create_app()
            from cps import config, constants, ub, usermanagement, web_server
            install(app, config, constants, ub, usermanagement, options)
            # The ingress proxy talks HTTP on this fixed loopback port.
            web_server.listen_address = '127.0.0.1'
            web_server.listen_port = 8083
            web_server.ssl_args = None
            return app

        cps.main.create_app = create_ingress_app
    cps.main.main()


if __name__ == '__main__':
    main()
