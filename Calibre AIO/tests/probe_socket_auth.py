"""Check real upstream Socket.IO hooks against a stale administrator session."""
import sys

sys.path.insert(0, '/opt/ha-cwa')
from shelfmark_wsgi import app, upstream

# This isolated process uses upstream's in-process Socket.IO client. It does
# not change the running web service's cookie settings or download queue.
app.config['SESSION_COOKIE_PATH'] = '/'
client = app.test_client()
with client.session_transaction() as state:
    state.update(user_id='ha_' + 'a' * 32, is_admin=True)

scopes = []
upstream.backend.queue_status = lambda user_id=None: scopes.append(user_id) or {}
socket = upstream.socketio.test_client(app, flask_test_client=client, headers={
    'X-AIO-User': 'ha_' + 'b' * 32, 'X-AIO-Groups': 'system-users',
})
assert socket.is_connected()
assert len(scopes) == 1 and scopes[0] is not None, scopes
socket.emit('request_status')
assert len(scopes) == 2 and scopes[1] == scopes[0], scopes
reader = upstream.user_db.get_user(username='ha_' + 'b' * 32)
assert scopes[0] == reader['id'], (scopes, reader)
socket.disconnect()
print('Real Shelfmark Socket.IO replaced stale admin session with reader scope')
