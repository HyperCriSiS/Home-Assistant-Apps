"""Exercise real applications and prefix-aware authentication in the built image."""
import http.client
import json
import os
import time

ADMIN = {'X-Remote-User-Id': 'a' * 32, 'X-Remote-User-Name': 'ha_admin'}
READER = {'X-Remote-User-Id': 'b' * 32, 'X-Remote-User-Name': 'ha_reader',
          'X-Remote-User-Groups': 'system-admin'}  # Forged group must never promote a reader.


def get(path, headers=None, trusted=True):
    target = os.environ.get('AIO_PROBE_HOST', '127.0.0.1')
    source = None if os.environ.get('AIO_PROBE_HOST') else (
        '127.0.0.2' if trusted else '127.0.0.1', 0)
    conn = http.client.HTTPConnection(target, 8084, timeout=10, source_address=source)
    try:
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        return response.status, response.read(), dict(response.getheaders())
    finally:
        conn.close()


for attempt in range(120):
    try:
        status, _, _ = get('/shelfmark/api/health', ADMIN)
        library_status, _, _ = get('/library/', ADMIN)
        if status == 200 and library_status == 200:
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise RuntimeError('Both backends did not become ready')

if not os.environ.get('AIO_PROBE_HOST'):
    assert get('/', trusted=False)[0] == 403
assert get('/library/')[0] == 403
assert get('/shelfmark/')[0] == 403
status, body, _ = get('/')
assert status == 200 and b'Calibre AIO' in body
assert b'/api/hassio_ingress/aio-test/' in body
status, body, _ = get('/shelfmark/', ADMIN)
assert status == 200 and b'/api/hassio_ingress/aio-test/shelfmark/' in body
status, body, headers = get('/library/', ADMIN)
assert status == 200 and b'/api/hassio_ingress/aio-test/library' in body
assert get('/library/', READER)[0] == 200
status, body, _ = get('/shelfmark/api/auth/check', ADMIN)
assert status == 200, (status, body)
assert json.loads(body)['is_admin'] is True
status, body, _ = get('/shelfmark/api/onboarding', ADMIN)
assert status == 200, ('onboarding', status, body)
assert isinstance(json.loads(body)['steps'], list)
status, body, _ = get('/shelfmark/api/auth/check', dict(ADMIN, **{'X-Remote-User-Id': 'c' * 32}))
assert status == 200 and json.loads(body)['is_admin'] is False  # Reused login name, different HA ID.
assert get('/shelfmark/api/onboarding', READER)[0] == 403
status, body, _ = get('/shelfmark/api/config', READER)
assert status == 200 and json.loads(body)['onboarding_complete'] is True
status, body, _ = get('/shelfmark/api/auth/check', READER)
assert status == 200 and json.loads(body)['is_admin'] is False
assert get('/shelfmark/socket.io/?EIO=4&transport=polling', ADMIN)[0] == 200
assert get('/shelfmark/socket.io/?EIO=4&transport=polling')[0] == 403
print('Real CWA + Shelfmark startup, prefixes, HA identities, UI and Socket.IO passed')
