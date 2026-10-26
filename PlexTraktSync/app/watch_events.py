"""Read-only upstream notification adapter; all Trakt writes use the sync worker."""
import contextlib
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time

from policy import install_guard
from storage import read


class PlaybackEvents:
    def __init__(self, validator, emit, clock=time.monotonic):
        self.validator = validator
        self.emit = emit
        self.clock = clock
        self.sessions = {}
        self.last_emit = {}

    def on_play(self, event):
        session, key = str(event.session_key), str(event.key)
        if not key.isdecimal() or len(key) > 12:
            return
        bound = self.sessions.get(session)
        if bound is None:
            if event.state != "playing" or not self.validator.can_scrobble(event):
                return  # Fail closed, especially when sessions are unavailable.
            if len(self.sessions) >= 1000:
                return
            self.sessions[session] = key
        elif bound != key:
            return
        now = self.clock()
        # Recheck watched status during long playback and once after stopping.
        # This never infers watched status from progress: Plex remains authoritative.
        if event.state == "stopped" or now - self.last_emit.get(session, -1000) >= 60:
            self.emit(key)
            self.last_emit[session] = now
        if event.state == "stopped":
            self.sessions.pop(session, None)
            self.last_emit.pop(session, None)
            if self.validator.sessions is not None:
                self.validator.sessions.pop(str(event.session_key), None)

    def reset(self, _event):
        self.sessions.clear()
        self.last_emit.clear()
        if self.validator.sessions is not None:
            self.validator.sessions.clear()


def main(directory, output):
    directory = Path(directory)
    options = read(directory / "options.json")
    credentials = read(directory / "credentials.json", {})
    install_guard(preview=True, ratings=False)
    os.environ["PLEX_SERVER"] = "default"
    os.environ["PLEX_USERNAME"] = options["plex_username"]
    from plextraktsync.factory import factory
    from plextraktsync.watch.events import Error, PlaySessionStateNotification
    factory.run_config.update(cache=False, progressbar=False)
    account = factory.plex_api.account
    if account is None or account.username.casefold() != options["plex_username"].casefold():
        raise ValueError("Plex account mismatch")
    if factory.server_config.token != credentials["plex_token"]:
        raise ValueError("Plex configuration changed; restart listener")
    adapter = PlaybackEvents(factory.watch_state_updater,
                             lambda key: print(json.dumps({"key": key}), file=output, flush=True))
    listener = factory.web_socket_listener
    listener.on(PlaySessionStateNotification, adapter.on_play, state=["playing", "paused", "stopped"])
    listener.on(Error, adapter.reset)
    listener.listen()  # Upstream reconnects with a 15-second backoff.


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    logging.disable(100)
    output = sys.stdout
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            main(sys.argv[1], output)
    except Exception:
        sys.exit(1)
