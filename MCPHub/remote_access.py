#!/usr/bin/env python3
"""Read-only remote access status for the tunnel dashboard.

Remote access runs through the separate Home Assistant Cloudflared and
Tailscale Apps against MCPHub's MCP-only gateway on container port 3001. This
module never controls those Apps. It only reads their state through
Supervisor info calls (allowed for the default App role), reports the host
address the Apps should forward to, and checks on request whether the
configured external address really reaches this gateway.
"""
from __future__ import annotations

import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SUPERVISOR = 'http://supervisor'
GATEWAY_PORT = '3001/tcp'
GATEWAY_MARKER = ('X-MCPHub-Gateway', 'mcp-only')
APP_CACHE_SECONDS = 30
MY_HA_APP = 'https://my.home-assistant.io/redirect/supervisor_addon/?addon='

# Candidate slugs: the current repository first, then the previous one that
# existing installations may still use.
APPS = {
    'cloudflared': {
        'name': 'Cloudflared',
        'slugs': ('396f0234_cloudflared', '9074a9fa_cloudflared'),
        'repository': 'https://github.com/homeassistant-apps/repository',
    },
    'tailscale': {
        'name': 'Tailscale',
        'slugs': ('a0d7b954_tailscale',),
        'repository': 'https://github.com/hassio-addons/repository',
    },
}


def app_link(slug, repository=None):
    """my.home-assistant.io link that opens (or offers to add) the App."""
    link = MY_HA_APP + quote(slug, safe='')
    if repository:
        link += '&repository_url=' + quote(repository, safe='')
    return link


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def supervisor_info(path, token=None, timeout=2):
    """GET one Supervisor info endpoint and return its data object, or None."""
    token = token if token is not None else os.environ.get('SUPERVISOR_TOKEN', '')
    if not token:
        return None
    request = Request(SUPERVISOR + path, headers={'Authorization': 'Bearer ' + token})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            body = json.loads(response.read(262144))
    except (HTTPError, URLError, OSError, ValueError, TimeoutError):
        return None
    data = body.get('data') if isinstance(body, dict) else None
    return data if isinstance(data, dict) else None


def app_status(key, info=supervisor_info, supervisor_ok=True):
    """State of one external App: started, stopped, not_installed or unknown."""
    spec = APPS[key]
    for slug in spec['slugs']:
        data = info('/addons/%s/info' % slug)
        if not data:
            continue
        if not data.get('version') or data.get('installed') is False:
            continue
        state = data.get('state')
        return {
            'name': spec['name'],
            'state': state if state in ('started', 'stopped', 'error') else 'unknown',
            'version': str(data.get('version') or ''),
            'update_available': data.get('update_available') is True,
            'link': app_link(slug),
        }
    return {
        'name': spec['name'],
        'state': 'not_installed' if supervisor_ok else 'unknown',
        'version': '',
        'update_available': False,
        'link': app_link(spec['slugs'][0], spec['repository']),
    }


def gateway_address(info=supervisor_info, own=None):
    """Host IPv4 address and published host port of the MCP gateway."""
    address = None
    network = info('/network/info') or {}
    for interface in network.get('interfaces') or []:
        if not isinstance(interface, dict) or not interface.get('primary'):
            continue
        for value in (interface.get('ipv4') or {}).get('address') or []:
            if isinstance(value, str) and value:
                address = value.split('/', 1)[0]
                break
        if address:
            break
    port = None
    own = own if own is not None else (info('/addons/self/info') or {})
    mapped = (own.get('network') or {}).get(GATEWAY_PORT)
    if isinstance(mapped, int) and 0 < mapped < 65536:
        port = mapped
    return {'host_ip': address, 'host_port': port}


def check_external(url, timeout=6):
    """Probe <url>/mcp without credentials and without following redirects.

    Only a 401 that carries this gateway's marker header proves that the
    address reaches MCPHub's MCP gateway, end to end through any tunnel.
    """
    request = Request(url + '/mcp', headers={'Cache-Control': 'no-store'})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            status, headers = response.status, response.headers
    except HTTPError as error:
        status, headers = error.code, error.headers
        error.close()
    except (URLError, OSError, ValueError, TimeoutError) as error:
        reason = getattr(error, 'reason', error)
        return {'result': 'unreachable', 'status': None, 'detail': str(reason)[:200]}
    marker = headers.get(GATEWAY_MARKER[0]) if headers else None
    if status == 401 and marker == GATEWAY_MARKER[1]:
        return {'result': 'reachable', 'status': status, 'detail': ''}
    if status in (301, 302, 303, 307, 308):
        location = (headers.get('Location') or '')[:200] if headers else ''
        return {'result': 'redirect', 'status': status, 'detail': location}
    return {'result': 'other_service', 'status': status, 'detail': ''}


def external_url_from(options):
    """Validated external address from the App options ('' when unset)."""
    value = str(options.get('external_url') or '').strip()
    if not value:
        return '', False
    parsed = urlsplit(value)
    valid = (parsed.scheme in ('http', 'https') and bool(parsed.hostname)
             and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
             and not parsed.username and not parsed.password and len(value) <= 200)
    return (value.rstrip('/'), False) if valid else ('', True)


class RemoteAccess:
    """Caches App state briefly; external checks run only on request."""

    def __init__(self, get_options, info=supervisor_info, probe=check_external):
        self.lock = threading.Lock()
        self.get_options = get_options
        self.info = info
        self.probe = probe
        self.cached = None
        self.cached_at = 0.0
        self.last_check = None
        self.last_check_at = 0.0
        self.last_check_url = ''

    def _url(self):
        try:
            return external_url_from(self.get_options())
        except (ValueError, OSError):
            return '', False

    def _apps(self, now):
        with self.lock:
            if self.cached is not None and now - self.cached_at < APP_CACHE_SECONDS:
                return self.cached
        # Supervisor calls run outside the lock so status stays responsive.
        own = self.info('/addons/self/info')
        value = {
            'apps': {key: app_status(key, self.info, own is not None) for key in APPS},
            'gateway': gateway_address(self.info, own or {}),
            'supervisor_available': own is not None,
        }
        with self.lock:
            self.cached, self.cached_at = value, now
        return value

    def status(self, now=None):
        now = time.monotonic() if now is None else now
        url, invalid = self._url()
        value = dict(self._apps(now))
        with self.lock:
            check = None
            if self.last_check is not None and self.last_check_url == url:
                check = dict(self.last_check,
                             age_seconds=round(now - self.last_check_at))
        value.update({
            'external_url': url,
            'external_url_invalid': invalid,
            'check': check,
        })
        return value

    def check(self, now=None):
        url, invalid = self._url()
        if not url:
            raise ValueError('Set a valid external address in the App configuration first'
                             if invalid else 'No external address is configured')
        result = self.probe(url)
        now = time.monotonic() if now is None else now
        with self.lock:
            self.last_check, self.last_check_at, self.last_check_url = result, now, url
        return dict(result, age_seconds=0)
