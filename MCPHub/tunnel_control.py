#!/usr/bin/env python3
"""Ingress-only OpenAI tunnel control and remote access status.

One loopback process supervises the optional OpenAI tunnel-client subprocess,
reports read-only status of remote access through the separate Cloudflared and
Tailscale Apps, and serves the dashboard. Only the Nginx Home Assistant Ingress
adapter proxies it. Credentials are never returned through its status, log or
diagnostics API.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from tunnel_diagnostics import TunnelLog
from remote_access import RemoteAccess

OPTIONS = Path('/data/options.json')
OPENAI_KEY_FILE = Path('/data/secrets/openai_runtime_api_key')
OPENAI_AUTH_FILE = Path('/data/secrets/mcphub_tunnel_authorization')
OPENAI_STATE = Path('/data/secrets/mcphub_openai_tunnel_state')
OPENAI_CLIENT = '/usr/local/bin/tunnel-client'
OPENAI_HEALTH = 'http://127.0.0.1:8080'
TUNNEL_ID = re.compile(r'^tunnel_[0-9a-f]{32}$')
PORT = ('127.0.0.1', 8093)
CHECK_INTERVAL = 5
PATH = re.compile(r'^/mcp(?:/[A-Za-z0-9._$-]+){0,2}$')
LOG = logging.getLogger('tunnel-control')


def valid_mcp_route(route):
    return bool(PATH.fullmatch(route)) and all(
        part not in ('.', '..') for part in route.split('/')[2:])


def options():
    data = json.loads(OPTIONS.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Invalid Home Assistant App options')
    value = dict(data)
    for group in ('openai', 'remote_access', 'home_assistant', 'github', 'logging'):
        if isinstance(data.get(group), dict):
            value.update(data[group])
    return value


def check(url, expected=200):
    try:
        with urlopen(Request(url, headers={'Cache-Control': 'no-store'}), timeout=2) as response:
            return response.status == expected
    except HTTPError as error:
        return error.code == expected
    except (URLError, TimeoutError, OSError):
        return False


def save_secret(path, value):
    """Atomically write a 0600 file without ever creating a readable copy."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(value)
        os.chmod(temp, 0o600)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def reap(proc):
    """Terminate a detached tunnel process; callers never hold a tunnel lock."""
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    else:
        proc.wait()


class TunnelProcess:
    """Shared lifecycle for one supervised tunnel subprocess.

    The Home Assistant option is the permission gate. Dashboard Start/Stop is
    persisted separately so it survives App restarts. HTTP probes and process
    termination always run outside the tunnel lock, so status stays responsive.
    """
    name = ''
    label = ''
    process_name = ''
    enabled_option = ''
    route_option = ''
    startup_grace = 35
    stable_after = 0

    def __init__(self, state_file=None):
        self.lock = threading.RLock()
        self.state_file = state_file if state_file is not None else self.default_state_file()
        self.proc = None
        self.desired = False
        self.state = 'stopped'
        self.error = ''
        self.checked = 0.0
        self.retry_at = 0.0
        self.failed = 0
        self.started = 0.0
        self.route = '/mcp'
        self.configured = False
        self.logs = TunnelLog(self.name + '-tunnel')
        self.logs.add(self.label + ' tunnel control started')
        self.reset_health()
        try:
            self.read_config(options())
        except (ValueError, OSError):
            self.configured = False
        self.desired = self.configured and self.load_persisted()
        self.state = 'starting' if self.desired else 'stopped'

    # Subclass hooks -----------------------------------------------------
    def default_state_file(self):
        raise NotImplementedError

    def launch(self, opts):
        """Return (argv, env or None, secrets to redact); raise ValueError."""
        raise NotImplementedError

    def probe(self, route):
        """Run local HTTP health probes; called without holding the lock."""
        raise NotImplementedError

    def assess(self, now, result):
        """Apply probe results under the lock; return a process to reap."""
        raise NotImplementedError

    def reset_health(self):
        pass

    # Shared logic -------------------------------------------------------
    def read_config(self, opts):
        self.configured = opts.get(self.enabled_option) is True
        self.route = str(opts.get(self.route_option) or '/mcp')

    def load_persisted(self):
        try:
            return self.state_file.read_text(encoding='utf-8').strip() == 'running'
        except FileNotFoundError:
            # Nothing persisted yet: an enabled HA option starts the tunnel.
            return self.configured
        except OSError:
            return False

    def persist(self, running):
        try:
            save_secret(self.state_file, 'running' if running else 'stopped')
        except OSError as error:
            LOG.warning('%s: could not persist tunnel state: %s', self.label, error)

    def _detach(self):
        proc, self.proc = self.proc, None
        return proc

    def _start(self, now):
        try:
            opts = options()
            self.read_config(opts)
            if not self.configured:
                raise ValueError('%s tunnel is disabled in the App configuration' % self.label)
            argv, env, secrets_ = self.launch(opts)
            self.proc = subprocess.Popen(
                argv, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors='replace', bufsize=1)
            self.logs.follow(self.proc, secrets_)
            self.logs.add('Tunnel process started')
            self.state = 'starting'
            self.started = now
            self.error = ''
            self.reset_health()
            LOG.info('%s: started tunnel process (pid %s)', self.label, self.proc.pid)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            # Invalid configuration requires a manual change/reload. Do not churn.
            # The persisted Start state is kept so a fixed config resumes on restart.
            self.proc = None
            self.desired = False
            self.state = 'error'
            self.error = str(error)
            self.logs.add('Start failed (check the App configuration)')
            LOG.warning('%s: tunnel not started: %s', self.label, error)

    def _fail(self, message, now):
        proc = self._detach()
        self.failed += 1
        delay = min(5 * 2 ** min(self.failed - 1, 6), 300)
        self.retry_at = now + delay
        self.error = message
        self.state = 'retrying'
        self.reset_health()
        self.logs.add('Error: ' + message)
        LOG.warning('%s: %s; retry in %s seconds', self.label, message, delay)
        return proc

    def command(self, action):
        if action not in ('start', 'stop', 'reload'):
            raise ValueError('Unsupported action')
        with self.lock:
            self.logs.add('Action: ' + action)
            old = None
            if action in ('stop', 'reload'):
                old = self._detach()
                self.desired = False
                self.state = 'stopped'
                self.error = ''
                self.retry_at = 0.0
                self.checked = 0.0
            if action == 'stop':
                self.persist(False)
        reap(old)
        if action == 'stop':
            return self.status()
        with self.lock:
            try:
                self.read_config(options())
            except (ValueError, OSError):
                self.configured = False
            if not self.configured:
                if action == 'start':
                    self.state = 'error'
                    self.error = 'Enable the %s tunnel in the App configuration first' % self.label
                return self.status()
            self.persist(True)
            self.desired = True
            self.failed = 0
            self.retry_at = 0.0
            if self.proc is None:
                self._start(time.monotonic())
        return self.status()

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if not self.desired:
                return
            if self.proc is None:
                if now >= self.retry_at:
                    self._start(now)
                return
            proc, route = self.proc, self.route
            code = proc.poll()
            dead = self._fail('%s exited (code %s)' % (self.process_name, code), now) \
                if code is not None else None
        if dead is not None:
            reap(dead)
            return
        result = self.probe(route)
        with self.lock:
            if self.proc is not proc:
                return  # stopped or restarted while probing
            self.checked = now
            dead = self.assess(now, result)
        reap(dead)

    def alive(self):
        with self.lock:
            return self.proc is not None and self.proc.poll() is None

    def status(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            # A previously ready tunnel is never reported healthy if checks stopped.
            fresh = bool(self.checked) and now - self.checked <= 20
            state, error = self.state, self.error
            if self.desired and state == 'ready' and not fresh:
                state, error = 'stale', '%s health check is stale' % self.label
            return {
                'state': state, 'configured': self.configured, 'requested': self.desired,
                'process_alive': self.proc is not None and self.proc.poll() is None,
                'transport_ready': state == 'ready', 'last_error': error,
                'route': self.route, 'failed_attempts': self.failed,
                'health_checked': bool(self.checked),
                'health_age_seconds': round(now - self.checked) if self.checked else None,
                'retry_in_seconds': max(0, round(self.retry_at - now)) if state == 'retrying' else 0,
                'control_type': 'process',
            }

    def shutdown(self):
        with self.lock:
            self.desired = False
            proc = self._detach()
        reap(proc)


class OpenAITunnel(TunnelProcess):
    name = 'openai'
    label = 'OpenAI'
    process_name = 'OpenAI tunnel'
    enabled_option = 'tunnel_enabled'
    route_option = 'tunnel_mcp_path'
    startup_grace = 45
    stable_after = 90
    liveness_timeout = 60
    readiness_timeout = 600

    def default_state_file(self):
        return OPENAI_STATE

    def reset_health(self):
        self.ready_since = self.not_live_since = self.not_ready_since = 0.0

    def launch(self, opts):
        key = str(opts.get('openai_runtime_api_key') or '').strip()
        tunnel_id = str(opts.get('tunnel_id') or '').strip()
        level = str(opts.get('tunnel_log_level') or 'info')
        if not key or not tunnel_id:
            raise ValueError('OpenAI Runtime API Key or Tunnel ID is missing')
        if not TUNNEL_ID.fullmatch(tunnel_id):
            raise ValueError('OpenAI Tunnel ID is invalid')
        if not valid_mcp_route(self.route):
            raise ValueError('OpenAI MCP route is invalid')
        if level not in ('debug', 'info', 'warn'):
            raise ValueError('OpenAI log level is invalid')
        if not OPENAI_AUTH_FILE.is_file():
            raise ValueError('MCPHub tunnel authorization file is missing')
        save_secret(OPENAI_KEY_FILE, key)
        env = os.environ.copy()
        env.update({
            'CONTROL_PLANE_TUNNEL_ID': tunnel_id,
            'MCP_SERVER_URL': f'http://127.0.0.1:3000{self.route}',
            'MCP_EXTRA_HEADERS': f'Authorization: file:{OPENAI_AUTH_FILE}',
            'MCP_DISCOVERY_EXTRA_HEADERS': f'Authorization: file:{OPENAI_AUTH_FILE}',
            'MCP_STARTUP_WAIT_TIMEOUT': '30s',
            'MCP_MAX_CONCURRENT_REQUESTS': '20',
            'HEALTH_LISTEN_ADDR': '127.0.0.1:8080',
            'LOG_LEVEL': level,
            'LOG_FORMAT': 'struct-text',
            'LOG_HTTP_RAW_UNSAFE': 'false',
        })
        argv = [OPENAI_CLIENT, 'run', f'--control-plane.api-key=file:{OPENAI_KEY_FILE}']
        return argv, env, (key, tunnel_id)

    def probe(self, route):
        live = check(OPENAI_HEALTH + '/healthz')
        return live, check(OPENAI_HEALTH + '/readyz') if live else False

    def assess(self, now, result):
        live, ready = result
        self.not_live_since = 0.0 if live else (self.not_live_since or now)
        if ready:
            self.ready_since = self.ready_since or now
            self.not_ready_since = 0.0
            self.state = 'ready'
            self.error = ''
            if now - self.ready_since >= self.stable_after:
                self.failed = 0
        else:
            self.ready_since = 0.0
            self.not_ready_since = self.not_ready_since or now
            self.state = 'degraded' if live else 'starting'
        if now - self.started < self.startup_grace:
            return None
        if not live and now - self.not_live_since >= self.liveness_timeout:
            return self._fail('OpenAI tunnel health endpoint is not responding', now)
        if live and not ready and now - self.not_ready_since >= self.readiness_timeout:
            return self._fail('OpenAI tunnel readiness has been unavailable for 10 minutes', now)
        return None


class Controls:
    def __init__(self):
        self.openai = OpenAITunnel()
        self.remote = RemoteAccess(options)

    def processes(self):
        return {'openai': self.openai}

    def snapshot(self):
        now = time.monotonic()
        return {
            'openai': self.openai.status(now),
            'remote': self.remote.status(now),
        }

    def command(self, mode, action):
        if action not in ('start', 'stop', 'reload'):
            raise ValueError('Unsupported action')
        if mode in self.processes():
            return self.processes()[mode].command(action)
        raise ValueError('Unknown tunnel')

    def logs(self, mode):
        """Return separately buffered logs; never expose the HA App log globally."""
        if mode in self.processes():
            return self.processes()[mode].logs.snapshot()
        raise ValueError('Unknown tunnel')

    def diagnostics(self, mode):
        """Bounded local component diagnostics; do not return raw configuration."""
        if mode != 'openai':
            raise ValueError('Unknown tunnel')
        if not self.openai.alive():
            return {'note': 'OpenAI tunnel process is not running'}
        try:
            with urlopen(OPENAI_HEALTH + '/health?details=true', timeout=3) as response:
                report = json.loads(response.read(65536))
            components = {}
            for name in ('mcp', 'control-plane', 'response-delivery', 'queue', 'proxy'):
                item = report.get('components', {}).get(name)
                if isinstance(item, dict):
                    components[name] = {
                        k: item[k] for k in ('status', 'state', 'reason_code', 'observed_at')
                        if k in item and isinstance(item[k], (str, bool, int))
                    }
            return {
                'live': report.get('live') is True,
                'ready': report.get('ready') is True,
                'components': components,
            }
        except (HTTPError, URLError, OSError, ValueError, TimeoutError):
            return {'note': 'OpenAI component diagnostics are unavailable'}

    def tick(self):
        for tunnel in self.processes().values():
            tunnel.tick()

    def shutdown(self):
        for tunnel in self.processes().values():
            tunnel.shutdown()


# The standalone management console is never injected into MCPHub's SPA.
PAGE = Path(__file__).with_name('tunnel_dashboard.html').read_text(encoding='utf-8')
SCRIPT = Path(__file__).with_name('tunnel_dashboard.js').read_text(encoding='utf-8')


def handler_for(manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            LOG.debug(fmt, *args)

        def send(self, status, body=b'', mime='application/json'):
            self.send_response(status)
            for name, value in (
                ('Content-Type', mime),
                ('Content-Length', str(len(body))),
                ('Cache-Control', 'no-store'),
                ('X-Content-Type-Options', 'nosniff'),
                ('X-Frame-Options', 'SAMEORIGIN'),
                ('Content-Security-Policy', "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'"),
            ):
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ('/', '/index.html'):
                self.send(200, PAGE.encode(), 'text/html; charset=utf-8')
            elif self.path == '/app.js':
                self.send(200, SCRIPT.encode(), 'text/javascript; charset=utf-8')
            elif self.path == '/api/status':
                self.send(200, json.dumps(manager.snapshot()).encode())
            elif self.path == '/api/remote/check':
                # Makes one outbound request; require the dashboard's header.
                if self.headers.get('X-MCPHub-Tunnel-Control') != '1':
                    self.send(403, b'Forbidden', 'text/plain')
                    return
                try:
                    self.send(200, json.dumps(manager.remote.check()).encode())
                except ValueError as error:
                    self.send(409, str(error).encode(), 'text/plain')
            elif self.path == '/api/logs/openai':
                self.send(200, json.dumps(manager.logs('openai')).encode())
            elif self.path == '/api/diagnostics/openai':
                self.send(200, json.dumps(manager.diagnostics('openai')).encode())
            else:
                self.send(404, b'Not found', 'text/plain')

        def do_POST(self):
            parts = self.path.split('/')
            if (len(parts) != 5 or parts[:3] != ['', 'api', 'control']
                    or parts[3] != 'openai'
                    or parts[4] not in ('start', 'stop', 'reload')
                    or self.headers.get('X-MCPHub-Tunnel-Control') != '1'
                    or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'
                    or self.headers.get('Content-Length') != '2'):
                self.send(403, b'Forbidden', 'text/plain')
                return
            if self.rfile.read(2) != b'{}':
                self.send(400, b'Bad request', 'text/plain')
                return
            try:
                result = manager.command(parts[3], parts[4])
            except (ValueError, OSError):
                self.send(409, b'Configuration unavailable', 'text/plain')
                return
            self.send(200, json.dumps(result).encode())
    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] [tunnel-control] %(message)s')
    manager = Controls()
    server = ThreadingHTTPServer(PORT, handler_for(manager))
    server.daemon_threads = True
    stopped = threading.Event()

    def stop(_signum, _frame):
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    LOG.info('OpenAI tunnel control and remote access status are available on loopback only')
    try:
        while not stopped.is_set():
            manager.tick()
            stopped.wait(CHECK_INTERVAL)
    finally:
        server.shutdown()
        server.server_close()
        manager.shutdown()


if __name__ == '__main__':
    main()
