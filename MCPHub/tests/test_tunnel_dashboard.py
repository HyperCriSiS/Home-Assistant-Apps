"""Dashboard entry, log sanitization and tunnel-scoped admin API regression tests."""
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(module_name, file):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NavigationTests(unittest.TestCase):
    def test_mcphub_topbar_gets_only_an_ingress_tunnel_link(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY ha_tunnel_nav.js /app/frontend/dist/mcphub-ha-nav.js", dockerfile)
        self.assertIn("RUN python3 /usr/local/bin/inject_tunnel_nav.py", dockerfile)
        self.assertIn("COPY tunnel_dashboard.html", dockerfile)
        self.assertIn("COPY tunnel_dashboard.js", dockerfile)

        script = (ROOT / "ha_tunnel_nav.js").read_text(encoding="utf-8")
        # The link is computed from the Ingress session path and nothing else.
        self.assertIn(r"\/api\/hassio_ingress\/[^/]+", script)
        self.assertIn("if (!match) return;", script)
        self.assertIn('"/_mcphub_tunnels/"', script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("fetch(", script)

    def test_shell_injection_is_exact_and_idempotency_is_enforced(self):
        module = load("mcphub_inject_nav", "inject_tunnel_nav.py")
        html = "<html><body><div id=\"root\"></div></body></html>"
        result = module.inject_shell(html)
        self.assertEqual(result.count(module.TAG), 1)
        self.assertLess(result.index(module.TAG), result.index("</body>"))
        with self.assertRaises(ValueError):
            module.inject_shell(result)
        with self.assertRaises(ValueError):
            module.inject_shell("<html><div></div></html>")


class LiveLogsTests(unittest.TestCase):
    def test_redact_secret_values_and_header_credentials(self):
        module = load("mcphub_log_redaction", "tunnel_diagnostics.py")
        text = "Bearer abc123.token access_token=xyz? username=harmless TOPSECRETXYZ"
        clean = module.redact(text, ["TOPSECRETXYZ"])
        self.assertNotIn("abc123.token", clean)
        self.assertNotIn("xyz", clean)
        self.assertNotIn("TOPSECRETXYZ", clean)
        self.assertIn("harmless", clean)

    def test_bounded_log_buffer_and_subprocess_capture(self):
        module = load("mcphub_log_capture", "tunnel_diagnostics.py")
        logs = module.TunnelLog()
        for i in range(250):
            logs.add("entry-" + str(i))
        self.assertEqual(len(logs.snapshot()["lines"]), module.MAX_LINES)
        self.assertNotIn("entry-0", logs.snapshot()["lines"][0])
        proc = Mock()
        proc.stdout = StringIO("live log one\napi_key=sensitive-secret\n")
        logs.follow(proc)
        for _ in range(100):
            if any("live log one" in x for x in logs.snapshot()["lines"]):
                break
            time.sleep(0.01)
        transcript = "\n".join(logs.snapshot()["lines"])
        self.assertIn("live log one", transcript)
        self.assertNotIn("sensitive-secret", transcript)

    def test_subprocess_output_is_echoed_redacted_to_app_log(self):
        module = load("mcphub_log_echo", "tunnel_diagnostics.py")
        stream = StringIO()
        logs = module.TunnelLog("cloudflare-tunnel", stream=stream)
        logs.add("lifecycle only")
        proc = Mock()
        proc.stdout = StringIO("connected\ntoken=TOPSECRETXYZ value\nraw TOPSECRETXYZ\n")
        logs.follow(proc, ("TOPSECRETXYZ",))
        for _ in range(100):
            if stream.getvalue().count("\n") >= 3:
                break
            time.sleep(0.01)
        echoed = stream.getvalue()
        self.assertIn("[cloudflare-tunnel] connected\n", echoed)
        self.assertNotIn("TOPSECRETXYZ", echoed)
        self.assertNotIn("lifecycle only", echoed)
        self.assertEqual(echoed.count("[cloudflare-tunnel] "), 3)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = load("mcphub_dashboard_ui", "tunnel_control.py")

    def test_separate_cards_and_optional_diagnostics(self):
        page = self.dashboard.PAGE
        script = self.dashboard.SCRIPT
        openai = page.index('id="t-openai"')
        remote = page.index('id="t-remote"')
        self.assertLess(openai, remote)
        self.assertGreater(page.index("OpenAI Secure Tunnel"), openai)
        self.assertGreater(page.index('id="remote-check"'), remote)
        # Only the OpenAI tunnel is a managed process with diagnostics and logs.
        self.assertEqual(page.count('data-panel="diagnostics"'), 1)
        self.assertEqual(page.count('data-panel="logs"'), 1)
        self.assertEqual(page.count('data-action="start"'), 1)
        self.assertIn("Show logs", page)
        self.assertIn('href="../"', page)
        self.assertIn("if (!section.open) return;", script)
        self.assertNotIn("JSON.stringify", script)
        self.assertNotIn("Cloudflare Access", page)

    def test_local_logs_endpoint_is_separate_and_unrecognized_modes_forbidden(self):
        manager = Mock()
        manager.logs.side_effect = lambda mode: {"lines": ["openai-one"]}
        manager.diagnostics.side_effect = lambda mode: {"mode": mode}
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     self.dashboard.handler_for(manager))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def get(path):
            connection = HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request("GET", path)
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()
        try:
            status, value = get("/api/logs/openai")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(value)["lines"], ["openai-one"])
            status, value = get("/api/diagnostics/openai")
            self.assertEqual(json.loads(value)["mode"], "openai")
            self.assertEqual(get("/api/logs/cloudflare")[0], 404)
            self.assertEqual(get("/api/diagnostics/cloudflare")[0], 404)
            self.assertEqual(get("/api/logs/serve")[0], 404)
            self.assertEqual(get("/api/diagnostics/funnel")[0], 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()