import importlib.util
import json
from pathlib import Path
import sys
import unittest
from werkzeug.test import Client
from werkzeug.wrappers import Request, Response

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rootfs/opt/ha-cwa'))
from shelfmark_gateway import IngressIdentity
from ingress_sso import read_options
from prepare_aio import validate_prefix


class GatewayTest(unittest.TestCase):
    def setUp(self):
        @Request.application
        def upstream(request):
            return Response(json.dumps({
                'user': request.headers.get('X-AIO-User'),
                'groups': request.headers.get('X-AIO-Groups'),
                'authorization': request.headers.get('Authorization'),
                'key': request.headers.get('X-Api-Key'),
            }), content_type='application/json')
        self.options = read_options({'sso': {'enabled': True}})
        self.client = Client(IngressIdentity(upstream, self.options), Response)

    def test_missing_identity_and_websocket_handshakes_denied(self):
        for path in ('/', '/api/auth/me', '/socket.io/?EIO=4&transport=polling'):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_aliases_and_api_keys_cannot_override_ha(self):
        response = self.client.get('/', headers={
            'X-CWA-Ingress': '1', 'X-Remote-User-Id': 'a' * 32,
            'X-Remote-User-Groups': 'system-users', 'X-AIO-Groups': 'system-admin',
            'X-AIO-User': 'admin', 'Authorization': 'Bearer forged', 'X-Api-Key': 'forged'})
        self.assertEqual(response.json, dict(user='ha_' + 'a' * 32,
                                            groups='system-users', authorization=None, key=None))

    def test_same_role_policy_as_cwa(self):
        headers = {'X-CWA-Ingress': '1', 'X-Remote-User-Id': 'b' * 32,
                   'X-Remote-User-Groups': 'system-admin'}
        self.assertEqual(self.client.get('/', headers=headers).json['groups'], 'system-admin')
        self.options['admin_users'] = ['a' * 32]
        self.assertEqual(self.client.get('/', headers=headers).json['groups'], 'system-users')

    def test_health_is_only_locally_exempt(self):
        self.assertEqual(self.client.get('/api/health').status_code, 403)
        self.assertEqual(self.client.get('/api/health', environ_overrides={
            'REMOTE_ADDR': '127.0.0.1'}).status_code, 200)


class DeploymentTest(unittest.TestCase):
    def test_prefix_validation_rejects_configuration_injection(self):
        for value in ('', '/', '/api/hassio_ingress/x;allow all', '/x', '/api/hassio_ingress/x/../'):
            with self.assertRaises(ValueError):
                validate_prefix(value)
        self.assertEqual(validate_prefix('/api/hassio_ingress/abc_123-'), '/api/hassio_ingress/abc_123-')

    def test_manifest_is_the_only_build_pin_source(self):
        spec = importlib.util.spec_from_file_location('upstreams', ROOT / 'scripts/upstreams.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.render(module.load_manifest()), (ROOT / 'build.yaml').read_text())

    def test_downloads_stage_separately_and_deliver_to_ingest(self):
        text = (ROOT / 'rootfs/opt/ha-cwa/shelfmark_wsgi.py').read_text()
        self.assertIn("'TMP_DIR': '/data/shelfmark-staging'", text)
        self.assertIn("'INGEST_DIR': '/cwa-book-ingest'", text)
