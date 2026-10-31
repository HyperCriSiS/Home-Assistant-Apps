"""Tests for the App-started unofficial Home Assistant MCP server."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_config", ROOT / "prepare_config.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UnofficialHaMcpTests(unittest.TestCase):
    def test_enabled_adds_loopback_server(self):
        servers = {}
        MODULE.apply_ha_mcp_server(servers, {"ha_mcp_enabled": True})
        entry = servers[MODULE.HA_MCP_SERVER_NAME]
        self.assertEqual(entry["url"], "http://127.0.0.1:8096/mcp")
        self.assertIn("Unofficial", entry["description"])

    def test_disabled_removes_only_managed_entry(self):
        servers = {}
        MODULE.apply_ha_mcp_server(servers, {"ha_mcp_enabled": True})
        MODULE.apply_ha_mcp_server(servers, {"ha_mcp_enabled": False})
        self.assertEqual(servers, {})

        own = {MODULE.HA_MCP_SERVER_NAME: {"url": "http://example.test/mcp"}}
        MODULE.apply_ha_mcp_server(own, {"ha_mcp_enabled": False})
        self.assertIn(MODULE.HA_MCP_SERVER_NAME, own)
        with self.assertRaises(ValueError):
            MODULE.apply_ha_mcp_server(own, {"ha_mcp_enabled": True})

    def test_restricted_user_needs_token_and_plain_address(self):
        good = {
            "ha_mcp_auth_mode": "restricted_user",
            "ha_mcp_user_token": "a" * 32,
            "ha_mcp_url": "http://homeassistant:8123",
        }
        MODULE.validate_ha_mcp_options(good)
        for change in (
            {"ha_mcp_user_token": ""},
            {"ha_mcp_url": "http://homeassistant:8123/api"},
            {"ha_mcp_url": "ftp://homeassistant"},
            {"ha_mcp_auth_mode": "other"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                MODULE.validate_ha_mcp_options({**good, **change})

    def test_run_sh_keeps_ha_mcp_on_loopback_without_app_secrets(self):
        text = (ROOT / "run.sh").read_text(encoding="utf-8")
        self.assertIn('MCP_HOST="127.0.0.1"', text)
        self.assertIn("unset JWT_SECRET HA_INGRESS_PROXY_SECRET", text)
        self.assertIn("ha-mcp@latest ha-mcp-web", text)


if __name__ == "__main__":
    unittest.main()
