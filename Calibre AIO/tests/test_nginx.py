"""Linux CI integration test for the unmodified production nginx ACL."""

import http.client
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest


@unittest.skipUnless(os.environ.get('CWA_TEST_NGINX') == '1',
                     'requires nginx and 172.30.32.2 on loopback (Linux CI)')
class NginxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Backend(BaseHTTPRequestHandler):
            def do_POST(self):
                remaining = int(self.headers['Content-Length'])
                digest = hashlib.sha256()
                while remaining:
                    block = self.rfile.read(min(remaining, 65536))
                    if not block:
                        raise AssertionError('Upload was truncated')
                    digest.update(block)
                    remaining -= len(block)
                body = digest.hexdigest().encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                body = json.dumps(dict(self.headers) | {'__path__': self.path}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        cls.backend = ThreadingHTTPServer(('127.0.0.1', 8083), Backend)
        cls.shelfmark = ThreadingHTTPServer(('127.0.0.1', 8085), Backend)
        cls.shelfmark_thread = threading.Thread(target=cls.shelfmark.serve_forever, daemon=True)
        cls.shelfmark_thread.start()
        cls.thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.thread.start()
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        template = (Path(__file__).resolve().parents[1]
                    / 'rootfs/etc/nginx/cwa-ingress.conf.template').read_text()
        config = template.replace('__CWA_INGRESS_PATH__', '/api/hassio_ingress/test')
        config = config.replace('/run/nginx.pid', str(root / 'nginx.pid'))
        paths = '\n'.join(f'{name}_temp_path {root / name};'
                          for name in ('client_body', 'proxy', 'fastcgi', 'uwsgi', 'scgi'))
        config = config.replace('http {', 'http {\n' + paths)
        cls.config = root / 'nginx.conf'
        cls.config.write_text(config)
        subprocess.run(['nginx', '-t', '-c', str(cls.config)], check=True)
        cls.log = open(root / 'nginx.log', 'w+')
        cls.proc = subprocess.Popen(['nginx', '-c', str(cls.config), '-g', 'daemon off;'],
                                    stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', 8084), timeout=.1):
                    return
            except OSError:
                if cls.proc.poll() is not None:
                    cls.log.seek(0)
                    raise RuntimeError(cls.log.read())
                time.sleep(.05)
        raise RuntimeError('nginx did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.log.close()
        cls.backend.shutdown()
        cls.backend.server_close()
        cls.shelfmark.shutdown()
        cls.shelfmark.server_close()
        cls.shelfmark_thread.join(timeout=5)
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self, source, headers, path='/library/'):
        conn = http.client.HTTPConnection('127.0.0.1', 8084, timeout=5,
                                          source_address=(source, 0))
        try:
            conn.request('GET', path, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_non_supervisor_denied_even_with_forged_headers(self):
        status, _ = self.request('127.0.0.1', {
            'X-Forwarded-For': '172.30.32.2', 'X-CWA-Ingress': '1',
            'X-Remote-User-Id': 'a' * 32, 'X-Remote-User-Groups': 'system-admin'})
        self.assertEqual(status, 403)

    def test_25_mib_upload_reaches_backend_without_truncation(self):
        body = b'Calibre AIO upload fixture\n' * (25 * 1024 * 1024 // 25 + 1)
        self.assertGreater(len(body), 25 * 1024 * 1024)
        for path in ('/library/upload', '/shelfmark/api/upload'):
            with self.subTest(path=path):
                connection = http.client.HTTPConnection('127.0.0.1', 8084, timeout=30,
                                                       source_address=('172.30.32.2', 0))
                try:
                    connection.request('POST', path, body=body,
                                       headers={'Content-Type': 'application/octet-stream'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read().decode(), hashlib.sha256(body).hexdigest())
                finally:
                    connection.close()

    def test_supervisor_identity_forwarded_and_marker_overwritten(self):
        status, body = self.request('172.30.32.2', {
            'X-CWA-Ingress': 'forged', 'X-Remote-User-Id': 'b' * 32,
            'X-Remote-User-Groups': 'system-users,system-admin'})
        self.assertEqual(status, 200)
        headers = json.loads(body)
        self.assertEqual(headers['X-CWA-Ingress'], '1')
        self.assertEqual(headers['X-Remote-User-Id'], 'b' * 32)
        self.assertEqual(headers['X-Remote-User-Groups'], 'system-users,system-admin')
        self.assertEqual(headers['X-Script-Name'], '/api/hassio_ingress/test/library')

    def test_shelfmark_prefix_and_websocket_headers(self):
        status, body = self.request('172.30.32.2', {
            'X-Remote-User-Id': 'a' * 32, 'Upgrade': 'websocket', 'Connection': 'Upgrade'},
            '/shelfmark/socket.io/?EIO=4&transport=websocket')
        self.assertEqual(status, 200)
        headers = json.loads(body)
        self.assertEqual(headers['Upgrade'], 'websocket')
        self.assertEqual(headers['__path__'],
                         '/api/hassio_ingress/test/shelfmark/socket.io/?EIO=4&transport=websocket')
