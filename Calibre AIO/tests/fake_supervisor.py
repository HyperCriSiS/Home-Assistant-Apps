"""Minimal Supervisor fixture for booting the image with its real /init."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path


class Supervisor(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/addons/self/info', '/apps/self/info'):
            data = {
                'slug': 'local_calibre-aio',
                'ingress_entry': '/api/hassio_ingress/aio-test',
                'ingress_url': '/api/hassio_ingress/aio-test',
            }
        elif self.path in ('/addons/self/options/config', '/apps/self/options/config'):
            data = json.loads(Path('/aio-tests/boot-options.json').read_text())
        else:
            self.send_error(404)
            return
        body = json.dumps({'result': 'ok', 'data': data}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(('0.0.0.0', 80), Supervisor).serve_forever()
