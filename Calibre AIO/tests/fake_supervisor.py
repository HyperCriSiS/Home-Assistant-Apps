"""Minimal Supervisor fixture for booting the image with its real /init."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Supervisor(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/addons/self/info', '/apps/self/info'):
            self.send_error(404)
            return
        body = json.dumps({'result': 'ok', 'data': {
            'ingress_entry': '/api/hassio_ingress/aio-test',
            'ingress_url': '/api/hassio_ingress/aio-test',
        }}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(('0.0.0.0', 80), Supervisor).serve_forever()
