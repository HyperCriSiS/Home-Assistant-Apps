import io
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from server import Controller
from storage import write
from watch_events import PlaybackEvents


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.validator = Mock(sessions={})
        self.validator.can_scrobble.return_value = True
        self.emit = Mock()
        self.now = 1000
        self.events = PlaybackEvents(self.validator, self.emit, clock=lambda: self.now)

    def event(self, state="playing", key="42", session="1"):
        return SimpleNamespace(state=state, key=key, session_key=session)

    def test_other_users_and_unverifiable_sessions_are_rejected(self):
        self.validator.can_scrobble.return_value = False
        self.events.on_play(self.event())
        self.events.on_play(self.event("stopped"))
        self.emit.assert_not_called()

    def test_progress_is_coalesced_and_stop_uses_bound_user(self):
        self.events.on_play(self.event())
        for _ in range(10):
            self.events.on_play(self.event())
        self.emit.assert_called_once_with("42")
        self.validator.can_scrobble.return_value = False  # Session is gone on stop.
        self.events.on_play(self.event("stopped"))
        self.assertEqual(self.emit.call_count, 2)
        self.assertFalse(self.events.sessions)

    def test_different_media_cannot_reuse_an_accepted_session(self):
        self.events.on_play(self.event())
        self.events.on_play(self.event("stopped", key="99"))
        self.emit.assert_called_once_with("42")

    def test_long_playback_and_reconnect(self):
        self.events.on_play(self.event())
        self.now += 61
        self.events.on_play(self.event())
        self.assertEqual(self.emit.call_count, 2)
        self.events.reset(None)
        self.events.on_play(self.event("stopped"))
        self.assertEqual(self.emit.call_count, 2)

    def test_invalid_keys_do_not_reach_scheduler(self):
        for key in ("../token", "a", "1" * 50):
            self.events.on_play(self.event(key=key))
        self.emit.assert_not_called()


class WatchSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        options = json.loads((ROOT / "default-options.json").read_text())
        options["watch_enabled"] = True
        write(self.directory / "options.json", options)
        self.c = Controller(self.directory)
        write(self.directory / "analysis.json", {"fingerprint": self.c.identity()})
        self.c.action("approve", {})

    def tearDown(self):
        self.c.shutdown()
        self.temp.cleanup()

    def test_listener_read_only_process_and_stop(self):
        process = Mock(stdout=io.StringIO(''))
        process.poll.return_value = None
        with patch("server.subprocess.Popen", return_value=process) as launch:
            self.c.ensure_watch()
        self.assertIn("watch_events.py", launch.call_args.args[0][1])
        self.assertTrue(self.c.status()["watch_running"])
        self.c.action("pause", {"paused": True})
        process.terminate.assert_called_once()
        self.assertFalse(self.c.status()["watch_running"])

    def test_events_debounced_without_resetting_full_sync_deadline(self):
        process = SimpleNamespace(stdout=io.StringIO('{"key":"42"}\n{"key":"42"}\n'))
        self.c.watch_events(process)
        self.assertEqual(len(self.c.pending), 1)
        self.assertGreater(self.c.pending["42"], time.time() + 20)
        deadline = self.c.next_sync
        worker = Mock()
        worker.wait.return_value = 0
        with patch("server.subprocess.Popen", return_value=worker):
            self.assertTrue(self.c.run("incremental", ["42"]))
        self.assertEqual(self.c.next_sync, deadline)

    def test_listener_never_starts_without_approval(self):
        (self.directory / "approval.json").unlink()
        with patch("server.subprocess.Popen") as launch:
            self.c.ensure_watch()
        launch.assert_not_called()

    def test_writer_lock_also_protects_incremental_runs(self):
        self.c.lock.acquire()
        try:
            with patch("server.subprocess.Popen") as launch:
                self.assertFalse(self.c.run("incremental", ["42"]))
                launch.assert_not_called()
        finally:
            self.c.lock.release()

    def test_listener_launch_failure_uses_backoff_instead_of_killing_scheduler(self):
        with patch("server.subprocess.Popen", side_effect=OSError("test")) as launch:
            self.c.ensure_watch()
            self.c.ensure_watch()
        launch.assert_called_once()
        self.assertGreater(self.c.watch_retry_at, time.time() + 50)
        self.assertIn("Unable to start", self.c.error)


if __name__ == "__main__":
    unittest.main()
