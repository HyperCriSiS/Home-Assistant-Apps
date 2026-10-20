"""Regression tests for HTTPS verification and remote access configuration."""

from __future__ import annotations

import importlib.util
import json
import ssl
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, APP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HomeAssistantProxyTlsTests(unittest.TestCase):
    def setUp(self):
        self.proxy = load_module("prepare_proxy_config")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ca_root = Path(self.temp.name) / "ssl"
        self.ca_root.mkdir()
        patcher = patch.object(self.proxy, "CUSTOM_CA_ROOT", self.ca_root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.options = {
            "home_assistant_mcp_enabled": True,
            "home_assistant_mcp_auth_mode": "restricted_user",
            "home_assistant_mcp_user_token": "eyJtest_restricted_user_token_0123456789",
        }

    def test_http_requires_no_cert_even_if_optional_ca_invalid(self):
        self.options.update(
            home_assistant_mcp_url="http://192.168.10.5:8123/api/mcp",
            home_assistant_mcp_ca_file="/ssl/does-not-exist.pem",
        )
        nginx = self.proxy.home_assistant_mcp_server_block(self.options)
        self.assertIn("proxy_pass http://192.168.10.5:8123/api/mcp;", nginx)
        self.assertNotIn("proxy_ssl_verify", nginx)
        self.assertNotIn("proxy_ssl_trusted_certificate", nginx)

    def test_https_uses_system_ca_and_verification(self):
        self.options["home_assistant_mcp_url"] = "https://ha.example.org/api/mcp"
        nginx = self.proxy.home_assistant_mcp_server_block(self.options)
        for directive in (
            "proxy_ssl_verify on;",
            "proxy_ssl_server_name on;",
            "proxy_ssl_verify_depth 5;",
            "proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;",
            "proxy_pass https://ha.example.org/api/mcp;",
        ):
            self.assertIn(directive, nginx)
        self.assertNotIn("proxy_ssl_verify off", nginx)

    def test_valid_private_ca_and_malformed_ca(self):
        ca_file = self.ca_root / "home-ca.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(self.ca_root / "key.pem"), "-out", str(ca_file),
             "-subj", "/CN=Local MCP Test CA", "-days", "1"],
            check=True, capture_output=True, timeout=15,
        )
        self.options.update(
            home_assistant_mcp_url="https://ha.lan:8123/api/mcp",
            home_assistant_mcp_ca_file="/ssl/home-ca.pem",
        )
        nginx = self.proxy.home_assistant_mcp_server_block(self.options)
        self.assertIn(f"proxy_ssl_trusted_certificate {ca_file};", nginx)
        self.assertIn("proxy_ssl_verify on;", nginx)

        ca_file.write_text("not a PEM certificate", encoding="utf-8")
        denied = self.proxy.home_assistant_mcp_server_block(self.options)
        self.assertIn("return 502;", denied)
        self.assertNotIn("Authorization", denied)
        self.assertNotIn("proxy_pass", denied)

    def test_untrusted_cert_and_wrong_hostname_never_disable_checks(self):
        self.options["home_assistant_mcp_url"] = "https://home.example.org/api/mcp"
        nginx = self.proxy.home_assistant_mcp_server_block(self.options)
        self.assertIn("proxy_ssl_verify on;", nginx)
        self.assertNotIn("proxy_ssl_verify off;", nginx)
        self.assertIn("proxy_pass https://home.example.org/api/mcp;", nginx)
        self.assertNotIn("proxy_ssl_name", nginx)

    def test_invalid_ca_paths_fail_closed(self):
        self.options["home_assistant_mcp_url"] = "https://ha.lan/api/mcp"
        for ca in ("/etc/passwd", "/ssl/../etc/passwd", "/ssl/missing.pem"):
            with self.subTest(ca=ca):
                self.options["home_assistant_mcp_ca_file"] = ca
                nginx = self.proxy.home_assistant_mcp_server_block(self.options)
                self.assertIn("return 502;", nginx)
                self.assertNotIn("proxy_pass", nginx)

    def test_url_parser_accepts_lan_and_rejects_unsafe_urls(self):
        for url in (
            "http://homeassistant:8123/api/mcp",
            "http://192.168.1.20:8123/api/mcp",
            "http://[fd00::1234]:8123/api/mcp",
            "https://ha.example.org/api/mcp",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.proxy.validate_home_assistant_mcp_url(url), url)
        for url in (
            "ftp://ha.example.org/api/mcp",
            "http://user:secret@ha.example.org/api/mcp",
            "http://ha.example.org/api/mcp?token=leak",
            "https://ha.example.org/private",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.proxy.validate_home_assistant_mcp_url(url)


class RemoteAccessConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.prepare = load_module("prepare_config")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        mapping = {
            "DATA_DIR": root / "mcphub",
            "SECRET_DIR": root / "secrets",
            "OPTIONS_FILE": root / "options.json",
            "SETTINGS_FILE": root / "mcphub" / "mcp_settings.json",
            "MANAGED_HOME_ASSISTANT_NAME_FILE":
                root / "mcphub" / ".managed_home_assistant_mcp_name",
            "MANAGED_BASE_URL_FILE": root / "mcphub" / ".managed_install_base_url",
        }
        for name, value in mapping.items():
            patcher = patch.object(self.prepare, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in (
            "JWT_SECRET_FILE", "OPENAI_TOKEN_FILE", "OPENAI_AUTH_FILE",
            "HA_INGRESS_PROXY_SECRET_FILE", "LEGACY_INGRESS_TOKEN_FILE",
            "GITHUB_TOKEN_FILE",
        ):
            patcher = patch.object(self.prepare, name, root / "secrets" / name.lower())
            patcher.start()
            self.addCleanup(patcher.stop)

    def set_options(self, **kwargs):
        self.prepare.OPTIONS_FILE.write_text(json.dumps(kwargs), encoding="utf-8")

    def settings(self):
        return json.loads(self.prepare.SETTINGS_FILE.read_text(encoding="utf-8"))

    def key_names(self):
        return [key["name"] for key in self.settings()["bearerKeys"]]

    def base_url(self):
        return self.settings()["systemConfig"].get("install", {}).get("baseUrl")

    def test_disabled_tunnel_ignores_invalid_old_path(self):
        self.set_options(tunnel_enabled=False, tunnel_mcp_path="/mcp/")
        self.prepare.main()
        self.assertNotIn(self.prepare.OPENAI_KEY_NAME, self.key_names())

    def test_enabled_invalid_route_fails_closed_without_startup_failure(self):
        self.set_options(tunnel_enabled=True, tunnel_mcp_path="/mcp/")
        self.prepare.main()
        self.assertNotIn(self.prepare.OPENAI_KEY_NAME, self.key_names())

    def test_valid_enabled_key_stays_scoped_and_disable_clears_it(self):
        self.set_options(tunnel_enabled=True, tunnel_mcp_path="/mcp/room")
        self.prepare.main()
        self.assertIn(self.prepare.OPENAI_KEY_NAME, self.key_names())
        key = next(k for k in self.settings()["bearerKeys"]
                   if k["name"] == self.prepare.OPENAI_KEY_NAME)
        self.assertNotEqual(key["accessType"], "all")
        self.set_options(tunnel_enabled=False, tunnel_mcp_path="/mcp/")
        self.prepare.main()
        self.assertNotIn(self.prepare.OPENAI_KEY_NAME, self.key_names())

    def test_removed_remote_origins_lose_keys_and_secrets(self):
        self.prepare.SECRET_DIR.mkdir(parents=True)
        self.prepare.DATA_DIR.mkdir(parents=True)
        for name in self.prepare.OBSOLETE_SECRET_FILES:
            (self.prepare.SECRET_DIR / name).write_text("old-secret", encoding="utf-8")
        self.prepare.SETTINGS_FILE.write_text(json.dumps({"bearerKeys": [
            {"id": "1", "name": "Home Assistant Cloudflare Tunnel", "token": "mcf_x"},
            {"id": "2", "name": "Home Assistant Tailscale MCP Gateway", "token": "mts_x"},
            {"id": "3", "name": "My laptop", "token": "user-key"},
        ]}), encoding="utf-8")
        self.set_options(cloudflare={"cloudflare_tunnel_enabled": True},
                         tailscale={"tailscale_funnel_enabled": True})
        self.prepare.main()
        self.assertEqual(self.key_names(), ["My laptop"])
        for name in self.prepare.OBSOLETE_SECRET_FILES:
            self.assertFalse((self.prepare.SECRET_DIR / name).exists(), name)

    def test_external_url_sets_and_clears_only_its_own_base_url(self):
        self.set_options(remote_access={"external_url": "https://MCP.example.com/"})
        self.prepare.main()
        self.assertEqual(self.base_url(), "https://mcp.example.com")
        self.set_options(remote_access={"external_url": "http://192.168.1.10:3001"})
        self.prepare.main()
        self.assertEqual(self.base_url(), "http://192.168.1.10:3001")
        self.set_options(remote_access={"external_url": ""})
        self.prepare.main()
        self.assertIsNone(self.base_url())

    def test_manual_base_url_survives_when_option_is_unset(self):
        self.prepare.DATA_DIR.mkdir(parents=True)
        self.prepare.SETTINGS_FILE.write_text(json.dumps({
            "systemConfig": {"install": {"baseUrl": "https://manual.example.com"}},
        }), encoding="utf-8")
        self.set_options(remote_access={"external_url": ""})
        self.prepare.main()
        self.assertEqual(self.base_url(), "https://manual.example.com")

    def test_invalid_external_url_never_changes_base_url(self):
        normalize = self.prepare.normalize_external_url
        for value in ("ftp://mcp.example.com", "https://mcp.example.com/mcp",
                      "https://user:pw@mcp.example.com", "https://mcp.example.com?x=1",
                      "https://mcp.example.com:99999", "javascript:alert(1)",
                      "https://" + "a" * 250 + ".com"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize(value)
        self.set_options(remote_access={"external_url": "https://mcp.example.com/mcp"})
        self.prepare.main()
        self.assertIsNone(self.base_url())


if __name__ == "__main__":
    unittest.main()
