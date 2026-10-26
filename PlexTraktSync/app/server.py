"""Small Ingress onboarding and single-writer scheduler; no public host ports."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import requests

from policy import fingerprint, config
from settings import normalize_options
from storage import read, write
from backup_service import BackupService
from backup_store import MAX_ZIP


class Controller:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.options = normalize_options(read(self.directory / "options.json"))
        self.lock = threading.Lock()
        self.action_lock = threading.Lock()
        self.stop = threading.Event()
        self.wakeup = threading.Event()
        self.process = None
        self.watch_process = None
        self.watch_identity = None
        self.watch_retry_at = 0
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.device = None
        self.csrf = secrets.token_urlsafe(32)
        self.state = read(self.directory / "state.json", {"version": 1, "paused": False})
        if self.state.get("version") != 1:
            raise ValueError("Unsupported state version; refusing unsafe migration")
        self.next_sync = time.time() + 30
        self.error = self.state.get("last_error")
        self.backups = BackupService(self)

    def log(self, event, level="info", **fields):
        levels = {"info": 20, "warning": 30, "error": 40}
        if levels[level] >= levels[self.options["log_level"]]:
            print(json.dumps({"timestamp": time.time(), "level": level, "event": event, **fields}), flush=True)

    def credentials(self):
        return read(self.directory / "credentials.json", {})

    def identity(self):
        return fingerprint(self.options, self.credentials())

    def approved(self):
        return read(self.directory / "approval.json", {}).get("fingerprint") == self.identity()

    def save(self):
        self.state["last_error"] = self.error
        write(self.directory / "state.json", self.state)

    def status(self):
        return {**self.state, "busy": self.lock.locked(), "approved": self.approved(),
                "last_error": self.error, "next_sync": self.next_sync,
                "trakt_authorized": (self.directory / ".pytrakt.json").exists(),
                "plex_configured": bool(self.credentials().get("plex_token")),
                "analysis": read(self.directory / "analysis.json"),
                "watch_running": self.watch_process is not None and self.watch_process.poll() is None,
                "sync_options": config(self.options)["sync"],
                "protected_settings": {"collection": False, "clear_collected": False,
                                       "watch_add_collection": False, "watch_remove_collection": False,
                                       "username_filter": True, "trakt_favorites": "unchanged"},
                "csrf": self.csrf}

    def settings(self):
        credentials = self.credentials()
        return {"options": self.options, "revision": self.identity(),
                "stored_credentials": {key: bool(credentials.get(key))
                                       for key in ("plex_token", "client_id", "client_secret")}}

    def update_settings(self, data):
        if not isinstance(data, dict) or set(data) - {"options", "credentials", "revision"}:
            raise ValueError("Invalid settings request")
        if data.get("revision") != self.identity():
            raise ValueError("Settings changed in another session; reload before saving")
        options = normalize_options(data.get("options"))
        changes = data.get("credentials", {})
        allowed = {"plex_token", "client_id", "client_secret"}
        if (not isinstance(changes, dict) or set(changes) - allowed
                or any(not isinstance(value, str) or len(value) > 4096
                       or any(ord(c) < 32 for c in value) for value in changes.values())):
            raise ValueError("Invalid credentials")
        credentials = self.credentials()
        client_changed = bool(changes.get("client_id") and changes["client_id"] != credentials.get("client_id"))
        trakt_changed = client_changed or bool(changes.get("client_secret")
                                              and changes["client_secret"] != credentials.get("client_secret"))
        if client_changed:
            credentials.pop("client_secret", None)
        credentials.update({key: value for key, value in changes.items() if value})
        if options == self.options and credentials == self.credentials():
            return {"ok": True, **self.settings()}
        self.stop_watch()
        # Revoke before persistence: a partial disk failure must fail closed.
        for name in ("approval.json", "analysis.json"):
            (self.directory / name).unlink(missing_ok=True)
        if trakt_changed:
            self.device = None
            (self.directory / ".pytrakt.json").unlink(missing_ok=True)
        write(self.directory / "credentials.json", credentials)
        write(self.directory / "options.json", options)
        self.options = options
        self.next_sync = time.time() + options["sync_interval_minutes"] * 60
        self.error = None
        self.save()
        return {"ok": True, **self.settings()}

    def run(self, mode, ids=None):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            if mode != "analyze" and (not self.approved() or self.state["paused"]):
                raise ValueError("Analyze, approve and resume before syncing")
            if mode == "analyze":
                self.stop_watch()
                (self.directory / "approval.json").unlink(missing_ok=True)
                (self.directory / "analysis.json").unlink(missing_ok=True)
            else:
                self.backups.before_sync()
            self.log("job_started", mode=mode)
            with self.action_lock:
                if self.stop.is_set() or (mode != "analyze" and (self.state["paused"] or not self.approved())):
                    raise ValueError("Analyze, approve and resume before syncing")
                self.process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).with_name("worker.py")), mode, str(self.directory)]
                    + ([json.dumps(ids)] if ids else []),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            code = self.process.wait(timeout=6 * 3600)
            if code:
                kind = read(self.directory / "worker-error.json", {}).get("type", "WorkerError")
                raise ValueError(f"{kind}: check Plex connection and Trakt authorization")
            if self.stop.is_set() or (mode != "analyze" and self.state["paused"]):
                raise ValueError("Job interrupted; no successful completion recorded")
            self.error = None
            if mode in ("sync", "incremental"):
                self.state["last_success"] = time.time()
                self.save()
            self.log("job_completed", mode=mode)
            return True
        except Exception as error:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.error = str(error) if isinstance(error, ValueError) else type(error).__name__
            self.log("job_failed", level="error", mode=mode, error_type=type(error).__name__)
            self.save()
            return False
        finally:
            self.process = None
            if mode != "incremental":
                self.next_sync = time.time() + self.options["sync_interval_minutes"] * 60
            self.lock.release()

    def schedule(self):
        while not self.stop.wait(1):
            if self.backups.tick():
                continue
            self.ensure_watch()
            if (self.options["sync_enabled"] and time.time() >= self.next_sync
                    and self.approved() and not self.state["paused"]):
                self.run("sync")
            elif self.approved() and not self.state["paused"]:
                with self.pending_lock:
                    due = [key for key, at in self.pending.items() if at <= time.time()][:100]
                    for key in due:
                        del self.pending[key]
                if due and not self.run("incremental", due):
                    with self.pending_lock:
                        for key in due:
                            self.pending[key] = time.time() + 300

    def watch_events(self, process):
        try:
            for line in process.stdout:
                data = json.loads(line)
                key = str(data["key"])
                if not key.isdecimal() or len(key) > 12:
                    continue
                with self.pending_lock:
                    if key not in self.pending and len(self.pending) < 1000:
                        self.pending[key] = time.time() + 30
        except (ValueError, KeyError, OSError):
            self.error = "Invalid playback listener event"

    def ensure_watch(self):
        enabled = (self.options["watch_enabled"] and self.options["plex_to_trakt_watched"]
                   and self.approved() and not self.state["paused"] and not self.stop.is_set())
        if not enabled:
            self.stop_watch()
            return
        if self.watch_process is not None:
            if self.watch_process.poll() is None and self.watch_identity == self.identity():
                return
            self.stop_watch(clear_pending=self.watch_identity != self.identity())
            self.error = "Playback listener disconnected; retrying in 60 seconds"
            self.watch_retry_at = time.time() + 60
        if time.time() < self.watch_retry_at:
            return
        self.watch_identity = self.identity()
        try:
            self.watch_process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("watch_events.py")), str(self.directory)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
        except OSError:
            self.error = "Unable to start playback listener; retrying in 60 seconds"
            self.watch_retry_at = time.time() + 60
            self.log("listener_start_failed", level="error")
            return
        threading.Thread(target=self.watch_events, args=(self.watch_process,), daemon=True).start()

    def stop_watch(self, clear_pending=True):
        process, self.watch_process = self.watch_process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout is not None:
                process.stdout.close()
        if clear_pending:
            with self.pending_lock:
                self.pending.clear()

    def shutdown(self):
        self.stop.set()
        self.stop_watch()
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def action(self, action, data):
        with self.action_lock:
            if action.startswith("backup-"):
                return self.backups.handle(action, data)
            if action in ("analyze", "sync", "pause"):
                return self._action(action, data)
            if not self.lock.acquire(blocking=False):
                raise ValueError("Wait until the current job finishes")
            try:
                return self._action(action, data)
            finally:
                self.lock.release()

    def _action(self, action, data):
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        if action == "settings":
            return self.update_settings(data)
        if action in ("analyze", "sync"):
            if self.lock.locked():
                raise ValueError("A job is already running")
            threading.Thread(target=self.run, args=(action,), daemon=True).start()
            return {"accepted": True}
        if action == "approve":
            report = read(self.directory / "analysis.json", {})
            if report.get("fingerprint") != self.identity():
                raise ValueError("Run a fresh analysis first")
            write(self.directory / "approval.json", {"fingerprint": self.identity()})
        elif action == "pause":
            self.state["paused"] = bool(data["paused"])
            self.save()
            if self.state["paused"]:
                self.stop_watch()
                self.shutdown_worker()
        elif action == "credentials":
            return self.update_settings({"options": self.options, "credentials": data, "revision": self.identity()})
        elif action == "plex-test":
            from plexapi.server import PlexServer
            server = PlexServer(self.options["plex_url"], self.credentials()["plex_token"],
                                timeout=self.options["plex_timeout"])
            account = server.myPlexAccount()
            if account.username.casefold() != self.options["plex_username"].casefold():
                raise ValueError("Token account differs from configured Plex username")
            return {"connected": True, "libraries": [x.title for x in server.library.sections()]}
        elif action == "trakt-start":
            c = self.credentials()
            response = requests.post("https://api.trakt.tv/oauth/device/code",
                                     json={"client_id": c["client_id"]}, timeout=self.options["request_timeout"])
            response.raise_for_status()
            self.device = {**response.json(), "started": time.time(), "last_poll": 0}
            return {k: self.device[k] for k in ("user_code", "verification_url", "expires_in", "interval")}
        elif action == "trakt-poll":
            d, c = self.device, self.credentials()
            if not d or time.time() >= d["started"] + d["expires_in"]:
                raise ValueError("Authorization expired; start again")
            if time.time() < d["last_poll"] + d["interval"]:
                return {"pending": True}
            d["last_poll"] = time.time()
            payload = {"code": d["device_code"], "client_id": c["client_id"]}
            if c.get("client_secret"):
                payload["client_secret"] = c["client_secret"]
            response = requests.post("https://api.trakt.tv/oauth/device/token", json=payload,
                                     timeout=self.options["request_timeout"])
            if response.status_code in (400, 429):
                if response.status_code == 429:
                    d["interval"] += 5
                return {"pending": True}
            if response.status_code in (404, 409, 410, 418):
                self.device = None
                raise ValueError("Trakt authorization denied, used or expired; request a new code")
            response.raise_for_status()
            token = response.json()
            write(self.directory / ".pytrakt.json", {
                "CLIENT_ID": c["client_id"], "CLIENT_SECRET": c.get("client_secret"),
                "OAUTH_TOKEN": token["access_token"], "OAUTH_REFRESH": token["refresh_token"],
                "OAUTH_EXPIRES_AT": token["created_at"] + token["expires_in"],
            })
            self.device = None
            # A different Trakt account must go through analysis and approval again.
            (self.directory / "approval.json").unlink(missing_ok=True)
            (self.directory / "analysis.json").unlink(missing_ok=True)
            return {"authorized": True}
        else:
            raise ValueError("Unknown action")
        return {"ok": True}

    def shutdown_worker(self):
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()


def handler(controller):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def send(self, code, body, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; "
                             "form-action 'self'; frame-ancestors 'self'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def permitted(self):
            # Ingress source, never trust a caller-supplied forwarded header.
            return self.client_address[0] == "172.30.32.2"

        def do_GET(self):
            if not self.permitted():
                return self.send(403, b'{}')
            path = urlsplit(self.path).path
            if path == "/api/status":
                with controller.action_lock:
                    body = json.dumps(controller.status()).encode()
                return self.send(200, body)
            if path == "/api/settings":
                with controller.action_lock:
                    body = json.dumps(controller.settings()).encode()
                return self.send(200, body)
            if path == "/api/backups":
                with controller.action_lock:
                    body = json.dumps(controller.backups.status()).encode()
                return self.send(200, body)
            if path.startswith("/api/backups/download/"):
                try:
                    with controller.backups.mutex:
                        archive = controller.backups.store.path(path.rsplit("/", 1)[-1])
                        if archive.stat().st_size > MAX_ZIP:
                            raise ValueError("Archiv ist zu groß.")
                        body = archive.read_bytes()
                    return self.send(200, body, "application/zip")
                except (ValueError, OSError):
                    return self.send(404, b'{}')
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/index.html": ("index.html", "text/html; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                      "/ui.js": ("ui.js", "text/javascript; charset=utf-8")}
            assets["/backups-ui.js"] = ("backups-ui.js", "text/javascript; charset=utf-8")
            if path not in assets:
                return self.send(404, b'{}')
            name, content_type = assets[path]
            return self.send(200, Path(__file__).with_name(name).read_bytes(), content_type)

        def do_POST(self):
            if not self.permitted() or not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), controller.csrf):
                return self.send(403, b'{}')
            try:
                path = urlsplit(self.path).path
                allowed = {"settings", "credentials", "plex-test", "trakt-start", "trakt-poll",
                           "analyze", "approve", "sync", "pause", "backup-settings", "backup-create",
                           "backup-preview", "backup-restore", "backup-pin", "backup-delete", "backup-prune", "backup-cancel", "backup-verify"}
                if path == "/api/backups/import":
                    length = int(self.headers.get("Content-Length", "0"))
                    if self.headers.get("Content-Type") != "application/zip" or not 0 < length <= MAX_ZIP:
                        raise ValueError("Bitte ein ZIP-Archiv mit maximal 128 MiB hochladen.")
                    self.connection.settimeout(60)
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("Upload unvollständig.")
                    with controller.action_lock:
                        result = controller.backups.import_archive(raw)
                    return self.send(200, json.dumps(result).encode())
                if path not in {"/api/" + action for action in allowed}:
                    return self.send(404, b'{}')
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 16384:
                    raise ValueError("Request too large")
                data = json.loads(self.rfile.read(length))
                result = controller.action(path.rsplit("/", 1)[-1], data)
                return self.send(200, json.dumps(result).encode())
            except Exception as error:
                # Avoid request exception text, response bodies and secrets.
                message = str(error) if isinstance(error, ValueError) else type(error).__name__
                return self.send(400, json.dumps({"error": message}).encode())
    return Handler


def main():
    os.umask(0o077)
    controller = Controller(os.environ.get("PTS_CONFIG_DIR", "/data/pts"))
    server = ThreadingHTTPServer(("0.0.0.0", 8099), handler(controller))
    threading.Thread(target=controller.schedule, daemon=True).start()

    def stop(*_):
        controller.shutdown()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        controller.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
