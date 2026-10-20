"""Read-only remote access status: external Apps, gateway address and address check."""
import importlib.util
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("mcphub_remote_access", ROOT / "remote_access.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = load()


def fake_supervisor(responses):
    calls = []

    def info(path):
        calls.append(path)
        return responses.get(path)

    return info, calls


class AppStatusTests(unittest.TestCase):
    def test_running_app_reports_state_version_and_installed_slug_link(self):
        info, calls = fake_supervisor({
            "/addons/9074a9fa_cloudflared/info": {
                "version": "6.0.1", "state": "started", "update_available": True,
            },
        })
        status = MOD.app_status("cloudflared", info)
        self.assertEqual(status["state"], "started")
        self.assertEqual(status["version"], "6.0.1")
        self.assertTrue(status["update_available"])
        # The installed (older repository) slug is linked, not the default one.
        self.assertIn("addon=9074a9fa_cloudflared", status["link"])
        self.assertEqual(calls[0], "/addons/396f0234_cloudflared/info")

    def test_missing_app_links_to_install_with_repository(self):
        info, _ = fake_supervisor({})
        status = MOD.app_status("tailscale", info, supervisor_ok=True)
        self.assertEqual(status["state"], "not_installed")
        query = parse_qs(urlsplit(status["link"]).query)
        self.assertEqual(query["addon"], ["a0d7b954_tailscale"])
        self.assertEqual(query["repository_url"], ["https://github.com/hassio-addons/repository"])
        self.assertTrue(status["link"].startswith("https://my.home-assistant.io/"))

    def test_unreachable_supervisor_is_unknown_not_missing(self):
        info, _ = fake_supervisor({})
        self.assertEqual(MOD.app_status("cloudflared", info, supervisor_ok=False)["state"],
                         "unknown")

    def test_store_entry_without_version_counts_as_not_installed(self):
        info, _ = fake_supervisor({"/addons/a0d7b954_tailscale/info": {
            "version": None, "installed": False, "state": "unknown"}})
        self.assertEqual(MOD.app_status("tailscale", info)["state"], "not_installed")

    def test_gateway_address_uses_primary_ipv4_and_published_port(self):
        info, _ = fake_supervisor({"/network/info": {"interfaces": [
            {"primary": False, "ipv4": {"address": ["10.0.0.2/24"]}},
            {"primary": True, "ipv4": {"address": ["192.168.1.10/24"]}},
        ]}})
        own = {"network": {"3001/tcp": 3005}}
        self.assertEqual(MOD.gateway_address(info, own),
                         {"host_ip": "192.168.1.10", "host_port": 3005})
        self.assertEqual(MOD.gateway_address(info, {"network": {"3001/tcp": None}})["host_port"],
                         None)


class ExternalUrlTests(unittest.TestCase):
    def test_only_plain_origins_are_used(self):
        self.assertEqual(MOD.external_url_from({"external_url": "https://mcp.example.com/"}),
                         ("https://mcp.example.com", False))
        self.assertEqual(MOD.external_url_from({}), ("", False))
        for value in ("https://mcp.example.com/mcp", "ftp://x.example.com",
                      "https://user:pw@x.example.com", "https://x.example.com?a=1"):
            with self.subTest(value=value):
                self.assertEqual(MOD.external_url_from({"external_url": value}), ("", True))


class AddressCheckTests(unittest.TestCase):
    """The probe runs against a local HTTP server standing in for the tunnel."""

    def serve(self, status, headers):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                seen.append((self.path, self.headers.get("Authorization")))
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%d" % server.server_address[1], seen

    def test_gateway_marker_with_401_means_reachable_without_credentials(self):
        url, seen = self.serve(401, {"X-MCPHub-Gateway": "mcp-only"})
        self.assertEqual(MOD.check_external(url)["result"], "reachable")
        self.assertEqual(seen, [("/mcp", None)])

    def test_other_service_and_redirect_are_not_reachable(self):
        url, _ = self.serve(401, {})
        self.assertEqual(MOD.check_external(url)["result"], "other_service")
        url, seen = self.serve(302, {"Location": "https://login.example.com/"})
        result = MOD.check_external(url)
        self.assertEqual(result["result"], "redirect")
        self.assertEqual(result["detail"], "https://login.example.com/")
        self.assertEqual(len(seen), 1)  # never followed

    def test_unreachable_address(self):
        self.assertEqual(MOD.check_external("http://127.0.0.1:9", timeout=2)["result"],
                         "unreachable")


class RemoteAccessTests(unittest.TestCase):
    def test_status_caches_supervisor_calls_and_check_runs_on_request(self):
        options = {"external_url": "https://mcp.example.com"}
        info, calls = fake_supervisor({"/addons/self/info": {"network": {"3001/tcp": 3001}}})
        probes = []
        remote = MOD.RemoteAccess(lambda: options, info=info,
                                  probe=lambda url: probes.append(url) or {"result": "reachable"})
        first = remote.status(now=100)
        self.assertIsNone(first["check"])
        self.assertTrue(first["supervisor_available"])
        count = len(calls)
        remote.status(now=110)
        self.assertEqual(len(calls), count)  # cached
        remote.status(now=100 + MOD.APP_CACHE_SECONDS + 1)
        self.assertGreater(len(calls), count)
        self.assertEqual(probes, [])
        self.assertEqual(remote.check(now=200)["result"], "reachable")
        self.assertEqual(probes, ["https://mcp.example.com"])
        self.assertEqual(remote.status(now=205)["check"]["age_seconds"], 5)
        # A changed address hides the old result.
        options["external_url"] = "https://other.example.com"
        self.assertIsNone(remote.status(now=206)["check"])

    def test_check_without_address_is_refused(self):
        remote = MOD.RemoteAccess(lambda: {}, info=lambda _path: None,
                                  probe=lambda _url: self.fail("must not probe"))
        with self.assertRaises(ValueError):
            remote.check()


if __name__ == "__main__":
    unittest.main()
