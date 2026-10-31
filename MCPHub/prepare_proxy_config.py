#!/usr/bin/env python3
"""Generate local Nginx adapters without exposing MCPHub directly."""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


OPTIONS_FILE = Path("/data/options.json")
TEMPLATE_FILE = Path("/etc/nginx/mcphub.conf.template")
OUTPUT_FILE = Path("/etc/nginx/conf.d/mcphub.conf")

HA_INGRESS_PROXY_SECRET_FILE = Path("/data/secrets/mcphub_ha_ingress_proxy_secret")

HA_MCP_PATH_PATTERN = re.compile(r"^/api/mcp(?:/[A-Za-z0-9._~-]+)?$")
ACCESS_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{20,4096}$")
SYSTEM_CA_FILE = Path("/etc/ssl/certs/ca-certificates.crt")
CUSTOM_CA_ROOT = Path("/ssl")
# Only allow PEM files within the read-only Home Assistant SSL share.
CUSTOM_CA_PATTERN = re.compile(r"^/ssl/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.pem$")


def flatten_grouped_options(data: dict) -> dict:
    """Read legacy flat and grouped options."""
    result = dict(data)
    for group in ("openai", "remote_access", "home_assistant", "ha_mcp", "github", "logging"):
        section = data.get(group)
        if isinstance(section, dict):
            result.update(section)
    return result


def load_options() -> dict:
    """Load Home Assistant App options."""
    with OPTIONS_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("options.json must contain a JSON object")

    return flatten_grouped_options(data)


def read_secret(path: Path) -> str:
    """Read one generated runtime secret."""
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"Secret file is empty: {path}")
    return value


def validate_home_assistant_mcp_url(value: str) -> str:
    """Validate and normalize a direct Home Assistant MCP endpoint."""
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("home_assistant_mcp_url must use http or https")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("home_assistant_mcp_url must contain only a host and port")
    if parsed.query or parsed.fragment:
        raise ValueError("home_assistant_mcp_url must not contain query or fragment data")
    if not HA_MCP_PATH_PATTERN.fullmatch(parsed.path):
        raise ValueError(
            "home_assistant_mcp_url path must be /api/mcp or /api/mcp/<api-id>"
        )

    try:
        port = parsed.port
    except ValueError as err:
        raise ValueError("home_assistant_mcp_url contains an invalid port") from err

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def trusted_home_assistant_ca_file(configured: str) -> Path:
    """Select a verified CA bundle without falling back to insecure HTTPS."""
    if not configured:
        return SYSTEM_CA_FILE
    if not CUSTOM_CA_PATTERN.fullmatch(configured):
        raise ValueError("home_assistant_mcp_ca_file must be a PEM file below /ssl")
    try:
        ca_file = (CUSTOM_CA_ROOT / configured.removeprefix("/ssl/")).resolve(strict=True)
        ca_file.relative_to(CUSTOM_CA_ROOT.resolve())
        if not ca_file.is_file():
            raise ValueError("home_assistant_mcp_ca_file must be a regular file")
        ssl.create_default_context(cafile=str(ca_file))
    except (OSError, ValueError, ssl.SSLError) as err:
        raise ValueError("home_assistant_mcp_ca_file is invalid or unreadable") from err
    return ca_file


def unavailable_home_assistant_mcp_block() -> str:
    """Fail closed for invalid CA settings without taking down Ingress."""
    return """server {
    listen 127.0.0.1:8097;
    access_log off;
    location / { return 502; }
}"""


def home_assistant_mcp_server_block(options: dict) -> str:
    """Build a loopback-only bridge to Home Assistant's MCP endpoint."""
    if not bool(options.get("home_assistant_mcp_enabled", False)):
        return """server {
    listen 127.0.0.1:8097;
    access_log off;

    location / {
        return 404;
    }
}"""

    mode = str(
        options.get("home_assistant_mcp_auth_mode", "restricted_user")
    ).strip()

    if mode == "supervisor":
        token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
        upstream = "http://supervisor/core/api/mcp"
        mode_label = "Supervisor"
    elif mode == "restricted_user":
        token = str(options.get("home_assistant_mcp_user_token", "")).strip()
        upstream = validate_home_assistant_mcp_url(
            str(
                options.get(
                    "home_assistant_mcp_url",
                    "http://homeassistant:8123/api/mcp",
                )
            )
        )
        mode_label = "dedicated Home Assistant user"
    else:
        raise ValueError(
            "home_assistant_mcp_auth_mode must be restricted_user or supervisor"
        )

    if not ACCESS_TOKEN_PATTERN.fullmatch(token):
        raise ValueError(
            f"{mode_label} token is missing or contains unexpected characters"
        )

    # HTTPS must verify the CA and hostname; LAN HTTP needs no TLS settings.
    ssl_directives = ""
    if upstream.startswith("https://"):
        try:
            ca_file = trusted_home_assistant_ca_file(
                str(options.get("home_assistant_mcp_ca_file", "")).strip()
            )
        except ValueError as err:
            print(f"[WARN] Home Assistant MCP HTTPS unavailable: {err}", file=sys.stderr)
            return unavailable_home_assistant_mcp_block()
        ssl_directives = (
            "        proxy_ssl_server_name on;\n"
            "        proxy_ssl_verify on;\n"
            f"        proxy_ssl_trusted_certificate {ca_file};\n"
            "        proxy_ssl_verify_depth 5;"
        )

    return f"""server {{
    listen 127.0.0.1:8097;

    access_log /dev/stdout;
    error_log /dev/stderr warn;

    client_max_body_size 16m;

    location = /mcp {{
        proxy_pass {upstream};
        proxy_http_version 1.1;

        proxy_set_header Authorization "Bearer {token}";
        proxy_set_header Host $proxy_host;
        proxy_set_header X-Real-IP "";
        proxy_set_header X-Forwarded-For "";
        proxy_set_header X-Forwarded-Proto "";

{ssl_directives}

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }}

    location / {{
        return 404;
    }}
}}"""


def main() -> None:
    options = load_options()
    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    ha_ingress_proxy_secret = read_secret(HA_INGRESS_PROXY_SECRET_FILE)
    home_assistant_block = home_assistant_mcp_server_block(options)

    rendered = template.replace(
        "__HA_INGRESS_PROXY_SECRET__",
        ha_ingress_proxy_secret,
    ).replace(
        "__HOME_ASSISTANT_MCP_SERVER_BLOCK__",
        home_assistant_block,
    )

    # Atomic configuration swap, so Nginx never reads a partially written file.
    tmp = OUTPUT_FILE.with_suffix(".conf.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        os.chmod(tmp, 0o600)
        os.replace(tmp, OUTPUT_FILE)
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
