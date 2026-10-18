"""Regression tests for OpenAI tunnel control and the remote access dashboard."""
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, ROOT / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TunnelControllerTests(unittest.TestCase):
    def setUp(self):
        self.mod = load("mcphub_tunnel_dashboard_test", "tunnel_control.py")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        directory = Path(tmp.name)
        self.mod.OPTIONS = directory / "options.json"
        self.mod.OPENAI_STATE = directory / "secret" / "openai_state"
        self.mod.OPENAI_KEY_FILE = directory / "secret" / "openai_key"
        self.mod.OPENAI_AUTH_FILE = directory / "auth"
        self.mod.OPENAI_AUTH_FILE.write_text("Bearer test-auth", encoding="utf-8")
        self.set_options()

    def set_options(self, **options):
        self.mod.OPTIONS.write_text(json.dumps(options), encoding="utf-8")

    def controller(self):
        controller = self.mod.Controls()
        controller.remote.status = Mock(return_value={"external_url": ""})
        return controller

    def test_openai_and_remote_cards_and_stale_openai_is_unhealthy(self):
        controller = self.controller()
        controller.openai.desired = True
        controller.openai.state = "ready"
        controller.openai.checked = self.mod.time.monotonic() - 35
        snapshot = controller.snapshot()
        self.assertEqual(set(snapshot), {"openai", "remote"})
        self.assertEqual(snapshot["openai"]["state"], "stale")
        self.assertFalse(snapshot["openai"]["transport_ready"])
        for mode in ("cloudflare", "tailscale", "funnel"):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    controller.command(mode, "start")
                with self.assertRaises(ValueError):
                    controller.logs(mode)
                with self.assertRaises(ValueError):
                    controller.diagnostics(mode)

    def test_no_bundled_cloudflare_or_tailscale_code(self):
        source = (ROOT / "tunnel_control.py").read_text(encoding="utf-8")
        for gone in ("cloudflared", "CloudflareTunnel", "TailscaleGateway",
                     "rotate_client_key", "/api/client-key", "/api/tailscale"):
            self.assertNotIn(gone, source)
        self.assertFalse((ROOT / "tailscale_gateway.py").exists())
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("cloudflared", dockerfile)
        self.assertNotIn("CLOUDFLARED_VERSION", dockerfile)
        self.assertIn("COPY remote_access.py /usr/local/bin/remote_access.py", dockerfile)

    def test_status_does_not_wait_for_slow_health_probes(self):
        self.set_options(openai={
            "tunnel_enabled": True,
            "openai_runtime_api_key": "test-private-key",
            "tunnel_id": "tunnel_" + "a" * 32,
        })
        controller = self.controller()
        entered, release = threading.Event(), threading.Event()

        def slow_check(*_args, **_kwargs):
            entered.set()
            release.wait(5)
            return True

        with patch.object(self.mod.subprocess, "Popen") as spawn, \
             patch.object(self.mod, "check", side_effect=slow_check):
            spawn.return_value.poll.return_value = None
            controller.openai.tick(100.0)  # starts the process
            worker = threading.Thread(target=controller.openai.tick, args=(110.0,), daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5))
            done = threading.Event()
            threading.Thread(target=lambda: (controller.snapshot(), done.set()),
                             daemon=True).start()
            self.assertTrue(done.wait(1), "status blocked behind a health probe")
            release.set()
            worker.join(5)

    def test_dashboard_has_openai_and_remote_access_cards(self):
        page = self.mod.PAGE
        self.assertIn('id="t-openai"', page)
        self.assertIn('id="t-remote"', page)
        self.assertNotIn('id="t-cloudflare"', page)
        self.assertNotIn('id="t-tailscale"', page)
        self.assertIn("Configuration", page)
        self.assertIn('data-link="cloudflared"', page)
        self.assertIn('data-link="tailscale"', page)
        self.assertIn('rel="noopener noreferrer"', page)
        self.assertIn("additional_hosts", page)
        self.assertIn("Copy client config", page)
        self.assertNotIn("client key", page.lower())

    def test_dashboard_is_independent_and_diagnostics_are_optional(self):
        page, script = self.mod.PAGE, self.mod.SCRIPT
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('href="../"', page)
        self.assertIn("Tunnels and remote access", page)
        self.assertIn("Show diagnostics", page)
        self.assertIn("Show logs", page)
        self.assertIn('data-panel="diagnostics"', page)
        self.assertIn('data-panel="logs"', page)
        self.assertIn("setInterval(refresh, 10000)", script)
        self.assertIn("if (!section.open) return;", script)
        self.assertNotIn("JSON.stringify", script)
        self.assertNotIn("innerHTML", script)
        # App links come from the server but are only used for my.home-assistant.io.
        self.assertIn(r"/^https:\/\/my\.home-assistant\.io\//.test(app.link)", script)
        self.assertIn("COPY tunnel_dashboard.html", dockerfile)
        self.assertIn("COPY tunnel_dashboard.js", dockerfile)

    def test_http_controls_deny_missing_headers_and_unknown_tunnels(self):
        manager = Mock()
        manager.snapshot.return_value = {"openai": {"state": "ready"}, "remote": {}}
        manager.command.return_value = {"state": "stopped"}
        manager.remote.check.return_value = {"result": "reachable", "age_seconds": 0}
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.mod.handler_for(manager))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, route, body=None, headers=None):
            conn = HTTPConnection(*server.server_address, timeout=5)
            try:
                conn.request(method, route, body=body, headers=headers or {})
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        allowed = {"Content-Type": "application/json", "X-MCPHub-Tunnel-Control": "1"}
        try:
            status, body = request("GET", "/api/status")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["openai"]["state"], "ready")
            status, _ = request("POST", "/api/control/openai/stop", "{}",
                                {"Content-Type": "application/json"})
            self.assertEqual(status, 403)
            for mode in ("cloudflare", "tailscale", "funnel"):
                status, _ = request("POST", "/api/control/%s/start" % mode, "{}", allowed)
                self.assertEqual(status, 403)
            manager.command.assert_not_called()
            status, body = request("POST", "/api/control/openai/stop", "{}", allowed)
            self.assertEqual(status, 200)
            manager.command.assert_called_once_with("openai", "stop")
            # The outbound address check needs the dashboard header.
            self.assertEqual(request("GET", "/api/remote/check")[0], 403)
            manager.remote.check.assert_not_called()
            status, body = request("GET", "/api/remote/check",
                                   headers={"X-MCPHub-Tunnel-Control": "1"})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["result"], "reachable")
            manager.remote.check.side_effect = ValueError("No external address is configured")
            status, body = request("GET", "/api/remote/check",
                                   headers={"X-MCPHub-Tunnel-Control": "1"})
            self.assertEqual(status, 409)
            self.assertIn(b"No external address", body)
            for route in ("/api/client-key", "/api/tailscale/client-key",
                          "/api/tailscale/gate", "/api/logs/cloudflare",
                          "/api/diagnostics/tailscale"):
                self.assertEqual(request("GET", route, headers=allowed)[0], 404, route)
            for route in ("/api/client-key/rotate", "/api/tailscale/client-key/rotate"):
                self.assertEqual(request("POST", route, "{}", allowed)[0], 403, route)
        finally:
            server.shutdown()
            server.server_close()


class OpenAITunnelTests(unittest.TestCase):
    """Lifecycle, backoff and health of the OpenAI tunnel-client."""

    def setUp(self):
        self.mod = load("mcphub_openai_tunnel_test", "tunnel_control.py")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        self.mod.OPTIONS = home / "options.json"
        self.mod.OPENAI_KEY_FILE = home / "secret" / "key"
        self.mod.OPENAI_AUTH_FILE = home / "auth"
        self.mod.OPENAI_STATE = home / "secret" / "openai_state"
        self.mod.OPENAI_AUTH_FILE.write_text("Bearer test-auth")
        self.values = {"openai": {
            "tunnel_enabled": True,
            "openai_runtime_api_key": "test-private-key",
            "tunnel_id": "tunnel_" + "a" * 32,
            "tunnel_mcp_path": "/mcp",
        }, "logging": {"tunnel_log_level": "info"}}
        self.write_options()
        self.process = Mock()
        self.process.pid = 71
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        patcher = patch.object(self.mod.subprocess, "Popen", return_value=self.process)
        self.popen = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(self.mod, "check", return_value=True)
        self.probe = patcher.start()
        self.addCleanup(patcher.stop)
        self.manager = self.mod.OpenAITunnel()

    def write_options(self):
        self.mod.OPTIONS.write_text(json.dumps(self.values))

    @staticmethod
    def unready(url, expected=200):
        return url.endswith("/healthz")

    def test_start_and_ready_then_stop_without_stopping_mcphub(self):
        self.manager.tick(100)
        self.assertEqual(self.manager.status(100)["state"], "starting")
        self.assertEqual(self.mod.OPENAI_KEY_FILE.read_text(), "test-private-key")
        self.assertEqual(self.mod.OPENAI_KEY_FILE.stat().st_mode & 0o777, 0o600)
        env = self.popen.call_args.kwargs["env"]
        self.assertEqual(env["MCP_SERVER_URL"], "http://127.0.0.1:3000/mcp")
        self.assertEqual(env["HEALTH_LISTEN_ADDR"], "127.0.0.1:8080")
        self.assertNotIn("test-private-key", str(self.popen.call_args.args))
        self.manager.tick(105)
        self.assertEqual(self.manager.status(105)["state"], "ready")
        self.assertTrue(self.manager.status(105)["transport_ready"])
        self.assertNotIn("test-private-key", json.dumps(self.manager.status(105)))
        self.manager.command("stop")
        self.process.terminate.assert_called_once()
        self.manager.tick(120)
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.manager.status(120)["state"], "stopped")

    def test_crash_retries_exponential_backoff(self):
        self.manager.tick(100)
        self.process.poll.return_value = 12
        self.manager.tick(110)
        self.assertEqual(self.manager.failed, 1)
        self.assertEqual(self.manager.retry_at, 115)
        self.manager.tick(114)
        self.assertEqual(self.popen.call_count, 1)
        self.process.poll.return_value = None
        self.manager.tick(115)
        self.assertEqual(self.popen.call_count, 2)
        self.process.poll.return_value = 2
        self.manager.tick(118)
        self.assertEqual(self.manager.retry_at, 128)

    def test_temporarily_unready_is_not_restarted(self):
        self.manager.tick(100)
        self.probe.side_effect = self.unready
        self.manager.tick(110)
        self.manager.tick(250)
        self.assertEqual(self.manager.status(250)["state"], "degraded")
        self.process.terminate.assert_not_called()

    def test_too_long_unready_is_restarted_after_grace(self):
        self.manager.tick(100)
        self.probe.side_effect = self.unready
        self.manager.tick(110)
        self.manager.tick(711)
        self.assertEqual(self.manager.status(711)["state"], "retrying")
        self.process.terminate.assert_called_once()

    def test_health_endpoint_missing_long_enough_retries(self):
        self.manager.tick(100)
        self.probe.return_value = False
        self.manager.tick(110)
        self.manager.tick(171)
        self.assertEqual(self.manager.state, "retrying")

    def test_invalid_credentials_fail_safe_without_exposing_secret(self):
        self.values["openai"]["tunnel_id"] = "bad"
        self.write_options()
        self.manager.tick(100)
        self.popen.assert_not_called()
        self.assertEqual(self.manager.state, "error")
        self.assertFalse(self.manager.desired)
        self.assertNotIn("test-private-key", self.manager.error)

    def test_reload_picks_up_new_configuration(self):
        self.manager.tick(100)
        self.values["openai"]["tunnel_mcp_path"] = "/mcp/development"
        self.write_options()
        self.manager.command("reload")
        self.assertEqual(self.popen.call_count, 2)
        self.assertEqual(self.popen.call_args.kwargs["env"]["MCP_SERVER_URL"],
                         "http://127.0.0.1:3000/mcp/development")

    def test_flat_options_are_still_accepted(self):
        self.mod.OPTIONS.write_text(json.dumps(
            self.values["openai"] | {"tunnel_log_level": "warn"}))
        self.manager.tick(100)
        self.assertEqual(self.popen.call_args.kwargs["env"]["LOG_LEVEL"], "warn")

    def test_disabled_option_gates_dashboard_start(self):
        self.values["openai"]["tunnel_enabled"] = False
        self.write_options()
        manager = self.mod.OpenAITunnel()
        self.assertFalse(manager.desired)
        status = manager.command("start")
        self.popen.assert_not_called()
        self.assertEqual(status["state"], "error")
        self.assertFalse(status["configured"])
        self.assertFalse(self.mod.OPENAI_STATE.exists())

    def test_stop_persists_across_restart(self):
        self.manager.tick(100)
        self.manager.command("stop")
        self.assertEqual(self.mod.OPENAI_STATE.read_text(), "stopped")
        self.assertEqual(self.mod.OPENAI_STATE.stat().st_mode & 0o777, 0o600)
        restarted = self.mod.OpenAITunnel()
        restarted.tick(200)
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(restarted.status(200)["state"], "stopped")
        restarted.command("start")
        self.assertEqual(self.mod.OPENAI_STATE.read_text(), "running")
        self.assertEqual(self.popen.call_count, 2)
        self.assertTrue(self.mod.OpenAITunnel().desired)


if __name__ == "__main__":
    unittest.main()