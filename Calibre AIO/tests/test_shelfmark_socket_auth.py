from functools import wraps
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from flask import Flask, request, session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
from shelfmark_socket_auth import install_socket_auth


class SocketIdentityTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only'
        self.handlers = {}
        self.seen = []

        def proxy_auth_middleware():
            if not request.headers.get('X-AIO-User'):
                return 'denied', 401
            session['user_id'] = request.headers['X-AIO-User']
            session['is_admin'] = request.headers.get('X-AIO-Groups') == 'system-admin'

        def observe():
            self.seen.append((session['user_id'], session['is_admin']))

        def registered(handler):
            # Flask-SocketIO stores a wrapper that keeps the handler in __wrapped__.
            @wraps(handler)
            def _handler(sid, *args):
                raise AssertionError('server-level wrapper must not be called')
            return _handler

        install_socket_auth(SimpleNamespace(
            app=SimpleNamespace(before_request_funcs={None: [proxy_auth_middleware]}),
            socketio=SimpleNamespace(
                on_event=self.handlers.__setitem__,
                server=SimpleNamespace(handlers={'/': {
                    'connect': registered(observe),
                    'request_status': registered(observe)}}))))

    def test_old_admin_session_is_replaced_before_each_status_handler(self):
        for event in ('connect', 'request_status'):
            with self.app.test_request_context('/socket.io/', headers={
                'X-AIO-User': 'ha_reader', 'X-AIO-Groups': 'system-users',
            }):
                session.update(user_id='ha_admin', is_admin=True)
                self.handlers[event]()
        self.assertEqual(self.seen, [('ha_reader', False)] * 2)

    def test_rejected_proxy_identity_never_reaches_native_handler(self):
        with self.app.test_request_context('/socket.io/'):
            session.update(user_id='ha_admin', is_admin=True)
            self.assertIs(self.handlers['connect'](), False)
        self.assertEqual(self.seen, [])
