import contextlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from server import Controller, handler
from storage import read, write


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        write(self.directory / "options.json", json.loads((ROOT / "default-options.json").read_text()))
        self.c = Controller(self.directory)
        self.c.action("credentials", {"client_id": "client"})
        self.c.device = {"device_code": "private", "started": time.time(), "expires_in": 600,
                         "interval": 5, "last_poll": 0}

    def tearDown(self):
        self.c.shutdown()
        self.temp.cleanup()

    def test_poll_pending_slowdown_and_expiry(self):
        response = Mock(status_code=429)
        with patch("server.requests.post", return_value=response) as post:
            self.assertTrue(self.c.action("trakt-poll", {})["pending"])
            self.assertEqual(self.c.device["interval"], 10)
            self.c.action("trakt-poll", {})
            post.assert_called_once()
        self.c.device["started"] = 0
        with patch("server.requests.post") as post, self.assertRaises(ValueError):
            self.c.action("trakt-poll", {})
        post.assert_not_called()

    def test_denial_and_revocation_require_fresh_device_code(self):
        with patch("server.requests.post", return_value=Mock(status_code=418)):
            with self.assertRaises(ValueError):
                self.c.action("trakt-poll", {})
        self.assertIsNone(self.c.device)
        self.assertFalse((self.directory / ".pytrakt.json").exists())

    def test_changing_client_removes_old_secret_token_and_approval(self):
        self.c.action("credentials", {"client_secret": "old-secret"})
        for name in (".pytrakt.json", "approval.json", "analysis.json"):
            write(self.directory / name, {"dummy": True})
        self.c.action("credentials", {"client_id": "new-client"})
        self.assertNotIn("client_secret", self.c.credentials())
        for name in (".pytrakt.json", "approval.json", "analysis.json"):
            self.assertFalse((self.directory / name).exists())

    def test_plex_auth_error_never_persists_credentials_as_error_text(self):
        self.c.action("credentials", {"plex_token": "sensitive-test-token"})
        with patch("plexapi.server.PlexServer", side_effect=requests.ConnectionError("sensitive-test-token")):
            with self.assertRaises(requests.ConnectionError):
                self.c.action("plex-test", {})
        self.assertNotIn("sensitive-test-token", json.dumps(self.c.status()))

    def test_operational_logs_include_no_credentials(self):
        self.c.action("credentials", {"plex_token": "sensitive-test-token"})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.c.run("sync")  # Blocked before any network access.
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(events[-1]["event"], "job_failed")
        self.assertNotIn("sensitive-test-token", output.getvalue())
        self.assertIsNotNone(Controller(self.directory).error)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        write(self.directory / "options.json", json.loads((ROOT / "default-options.json").read_text()))
        self.c = Controller(self.directory)
        self.servers = []

    def tearDown(self):
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.c.shutdown()
        self.temp.cleanup()

    def serve(self, ingress=False):
        base = handler(self.c)
        if ingress:
            # Only emulate the network source; exercise the actual HTTP/CSRF code.
            class Ingress(base):
                def permitted(self):
                    return True
            base = Ingress
        server = ThreadingHTTPServer(("127.0.0.1", 0), base)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    def test_direct_access_and_spoofed_forwarded_headers_are_denied(self):
        url = self.serve()
        headers = {"X-Forwarded-For": "172.30.32.2", "X-Ingress-Path": "/", "X-CSRF-Token": self.c.csrf}
        self.assertEqual(requests.get(url + "/api/status", headers=headers, timeout=5).status_code, 403)
        self.assertEqual(requests.post(url + "/api/pause", headers=headers, json={"paused": True}, timeout=5).status_code, 403)

    def test_ingress_csrf_and_credential_storage(self):
        url = self.serve(ingress=True)
        status = requests.get(url + "/api/status", timeout=5)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.headers["Cache-Control"], "no-store")
        self.assertEqual(requests.post(url + "/api/credentials", json={"plex_token": "secret"}, timeout=5).status_code, 403)
        headers = {"X-CSRF-Token": status.json()["csrf"]}
        self.assertEqual(requests.post(url + "/api/credentials", headers=headers,
                                       json={"plex_token": "secret"}, timeout=5).status_code, 200)
        self.assertEqual(self.c.credentials()["plex_token"], "secret")
        self.assertNotIn("secret", requests.get(url + "/api/status", timeout=5).text)

    def test_upstream_exception_body_is_not_returned(self):
        url = self.serve(ingress=True)
        with patch.object(self.c, "action", side_effect=requests.HTTPError("token=private")):
            response = requests.post(url + "/api/plex-test", json={}, headers={"X-CSRF-Token": self.c.csrf}, timeout=5)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "HTTPError"})


if __name__ == "__main__":
    unittest.main()
