"""Regression checks for the LAN MCP gateway on container port 3001."""
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LAN_ROUTE = r"^/mcp(?:/[A-Za-z0-9._$-]+){0,2}$"


def lan_block() -> str:
    text = (ROOT / "ingress.conf").read_text()
    return text.split("server {\n    listen 3001;", 1)[1]


class LanAccessTests(unittest.TestCase):
    def test_lan_mcp_port_enabled_by_default(self):
        config = yaml.safe_load((ROOT / "config.yaml").read_text())
        self.assertEqual(config["ports"]["3001/tcp"], 3001)
        description = config["ports_description"]["3001/tcp"]
        self.assertIn("default port 3001", description)
        self.assertIn("only /mcp", description)
        self.assertIn("Leave blank", description)
        self.assertTrue(config["ingress"])
        self.assertTrue(config["panel_admin"])
        self.assertFalse(config.get("host_network", False))

    def test_lan_serves_only_mcp_routes(self):
        lan = lan_block()
        self.assertIn(f'location ~ "{LAN_ROUTE}" {{', lan)
        # Forward the normalized URI so raw dot-segment paths never reach MCPHub.
        self.assertIn("proxy_pass http://127.0.0.1:3000$uri$is_args$args;", lan)
        self.assertIn("location = /health {", lan)
        self.assertIn("location / {\n        return 404;\n    }", lan)
        # Exactly two upstream proxies: health and the MCP route.
        self.assertEqual(lan.count("proxy_pass "), 2)

    def test_lan_route_pattern_accepts_mcp_and_rejects_management(self):
        route = re.compile(LAN_ROUTE)
        for path in ("/mcp", "/mcp/home", "/mcp/$smart", "/mcp/$smart/home"):
            with self.subTest(path=path):
                self.assertTrue(route.fullmatch(path))
        for path in ("/", "/api/servers", "/api/better-auth/user", "/login",
                     "/sse", "/messages", "/mcpx", "/mcp/a/b/c", "/mcp/",
                     "/_mcphub_tunnels/", "/mcp/a b"):
            with self.subTest(path=path):
                self.assertFalse(route.fullmatch(path))

    def test_lan_proxy_has_no_ingress_privilege(self):
        text = (ROOT / "ingress.conf").read_text()
        ingress = text.split("server {\n    listen 3001;", 1)[0]
        lan = lan_block()
        self.assertIn("allow 172.30.32.2;", ingress)
        self.assertIn("__HA_INGRESS_PROXY_SECRET__", ingress)
        self.assertNotIn("__HA_INGRESS_PROXY_SECRET__", lan)
        for header in (
            "X-MCPHub-HA-Proxy-Secret", "X-Remote-User-Id",
            "X-Remote-User-Name", "X-Remote-User-Display-Name",
            "X-Remote-User-Email", "X-Remote-User-Groups",
            "X-Forwarded-Prefix", "Proxy-Authorization",
        ):
            self.assertIn(f'proxy_set_header {header} "";', lan)
        # The client's own MCPHub bearer key passes through unchanged.
        self.assertNotIn("proxy_set_header Authorization \"Bearer", lan)

    def test_native_auth_remains_enabled(self):
        prepare = (ROOT / "prepare_config.py").read_text()
        self.assertIn('routing["skipAuth"] = False', prepare)
        self.assertIn('routing["enableBearerAuth"] = True', prepare)

    def test_hot_backup_skips_package_caches(self):
        config = yaml.safe_load((ROOT / "config.yaml").read_text())
        self.assertEqual(config["backup"], "hot")
        self.assertIn("cache/*", config["backup_exclude"])

    def test_gateway_is_the_only_remote_origin(self):
        # Cloudflared and Tailscale Apps forward to port 3001; the App no longer
        # renders separate Cloudflare or Tailscale origins with their own keys.
        proxy = (ROOT / "prepare_proxy_config.py").read_text()
        template = (ROOT / "ingress.conf").read_text()
        self.assertNotIn("127.0.0.1:3000", proxy)
        for gone in ("8098", "listen 3002", "__CLOUDFLARE_SERVER_BLOCK__",
                     "__TAILSCALE_SERVER_BLOCK__"):
            self.assertNotIn(gone, template)
            self.assertNotIn(gone, proxy)
        config = yaml.safe_load((ROOT / "config.yaml").read_text())
        self.assertEqual(list(config["ports"]), ["3001/tcp"])

    def test_gateway_marks_its_responses_for_the_address_check(self):
        self.assertIn('add_header X-MCPHub-Gateway "mcp-only" always;', lan_block())


if __name__ == "__main__":
    unittest.main()
