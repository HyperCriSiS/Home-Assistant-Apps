"""Run the pinned CWA release with optional Home Assistant ingress SSO."""

import json
import os
import sys

from ingress_sso import install, read_options
from modern_theme import install_modern_theme


def load_options_and_drop_privileges(path='/data/options.json', account='abc'):
    # Supervisor protects options.json from unprivileged processes. Read and
    # validate it before dropping privileges; never relax that file's mode.
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle)
    options = read_options(document)
    options['library_theme'] = document.get('library_theme', 'modern')
    if options['library_theme'] not in ('modern', 'upstream'):
        raise ValueError('library_theme must be modern or upstream')
    # AIO never derives privileges from a group header: stable Supervisors do
    # not supply or sanitize that header. An empty name grants nobody admin.
    options['admin_username'] = options.get('admin_username', '')
    os.environ.pop('SUPERVISOR_TOKEN', None)
    os.environ.pop('HASSIO_TOKEN', None)
    # Validated by start_shelfmark.py: a bad Shelfmark option must not stop CWA.
    options['external_bypass_url'] = document.get('shelfmark', {}).get('external_bypass_url', '')
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
            if options.get('library_theme', 'modern') == 'modern':
                install_modern_theme(app)
            # The ingress proxy talks HTTP on this fixed loopback port.
            web_server.listen_address = '127.0.0.1'
            web_server.listen_port = 8083
            web_server.ssl_args = None
            return app

        cps.main.create_app = create_ingress_app
    cps.main.main()


if __name__ == '__main__':
    main()
