"""HA identity boundary around upstream Shelfmark, including Socket.IO."""
from ingress_sso import USER_ID, is_home_assistant_admin
from ha_admin import is_configured_admin, AdminBindingUnavailable


class IngressIdentity:
    def __init__(self, app, options):
        self.app = app
        self.options = options

    def __call__(self, environ, start_response):
        if (environ.get('PATH_INFO') == '/api/health'
                and environ.get('REMOTE_ADDR') == '127.0.0.1'):
            return self.app(environ, start_response)
        uid = environ.get('HTTP_X_REMOTE_USER_ID', '')
        if environ.get('HTTP_X_CWA_INGRESS') != '1' or not USER_ID.fullmatch(uid):
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            return [b'Home Assistant ingress authentication required']
        environ.pop('HTTP_AUTHORIZATION', None)
        environ.pop('HTTP_X_API_KEY', None)
        environ['HTTP_X_AIO_USER'] = 'ha_' + uid
        selected = self.options['admin_users']
        if 'admin_username' in self.options:
            try:
                admin = is_configured_admin(uid, environ.get('HTTP_X_REMOTE_USER_NAME', ''),
                                            self.options['admin_username'])
            except AdminBindingUnavailable:
                start_response('503 Service Unavailable', [('Content-Type', 'text/plain')])
                return [b'Home Assistant administrator binding is unavailable']
        else:
            admin = (uid in selected if selected else is_home_assistant_admin(
                environ.get('HTTP_X_REMOTE_USER_GROUPS', '')))
        environ['HTTP_X_AIO_GROUPS'] = 'system-admin' if admin else 'system-users'
        return self.app(environ, start_response)
