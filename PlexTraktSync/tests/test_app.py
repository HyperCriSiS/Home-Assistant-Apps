import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from policy import PolicyError, check_request, config, fingerprint, install_guard
from server import Controller, handler
from storage import read, write
from worker import analyze


def options():
    return yaml.safe_load((ROOT / "config.yaml").read_text())["options"]


class PolicyTests(unittest.TestCase):
    def test_all_protected_endpoints_and_methods(self):
        for endpoint in ("sync/collection", "sync/collection/remove", "sync/watchlist", "sync/watchlist/remove",
                         "sync/favorites", "users/me/lists/test/items"):
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                for preview in (True, False):
                    with self.subTest(endpoint=endpoint, method=method, preview=preview):
                        with self.assertRaises(PolicyError):
                            check_request(method, "https://api.trakt.tv/" + endpoint,
                                          preview=preview, ratings=True)

    def test_preview_blocks_media_writes_and_plex_get_actions(self):
        for method, url in (("POST", "https://api.trakt.tv/sync/history"),
                            ("POST", "https://api.trakt.tv/sync/ratings"),
                            ("GET", "http://plex:32400/:/scrobble?key=1"),
                            ("GET", "http://plex:32400/:/unscrobble?key=1"),
                            ("GET", "http://plex:32400/:/rate?key=1"),
                            ("PUT", "http://plex:32400/library/metadata/1")):
            with self.subTest(url=url), self.assertRaises(PolicyError):
                check_request(method, url, preview=True, ratings=True)

    def test_allowed_operations_and_refresh(self):
        for method, url in (("GET", "http://plex/library/sections"),
                            ("GET", "https://api.trakt.tv/sync/watched/movies"),
                            ("POST", "https://api.trakt.tv/oauth/token")):
            check_request(method, url, preview=True, ratings=False)
        check_request("POST", "https://api.trakt.tv/sync/history", preview=False, ratings=False)
        with self.assertRaises(PolicyError):
            check_request("POST", "https://api.trakt.tv/sync/ratings", preview=False, ratings=False)

    def test_configuration_never_inherits_unsafe_defaults(self):
        for priority in ("none", "plex", "trakt"):
            o = options()
            o.update(rating_priority=priority, ratings=True)
            c = config(o)
            self.assertFalse(c["sync"]["plex_to_trakt"]["collection"])
            self.assertFalse(c["sync"]["plex_to_trakt"]["clear_collected"])
            for direction in ("plex_to_trakt", "trakt_to_plex"):
                self.assertFalse(c["sync"][direction]["watchlist"])
            self.assertFalse(c["watch"]["add_collection"])
            self.assertFalse(c["watch"]["remove_collection"])
            self.assertTrue(c["watch"]["username_filter"])

    def test_installed_guard_blocks_collection_before_transport(self):
        with patch.object(requests.sessions.Session, "send") as transport:
            original = requests.sessions.Session.send
            try:
                install_guard(preview=False, ratings=True)
                with self.assertRaises(PolicyError):
                    requests.post("https://api.trakt.tv/sync/collection", json={"movies": []})
                with self.assertRaises(PolicyError):
                    requests.post("https://api.trakt.tv/scrobble/stop", json={})
                transport.assert_not_called()
            finally:
                requests.sessions.Session.send = original

    def test_guard_records_api_errors_and_refuses_ambiguous_search(self):
        response = requests.Response()
        response.status_code = 503
        response._content = b'{}'
        with patch.object(requests.sessions.Session, "send", return_value=response):
            original = requests.sessions.Session.send
            try:
                failures = install_guard(preview=True, ratings=False)
                requests.get("https://api.trakt.tv/users/me")
                self.assertEqual(failures, ["HTTP503"])
                response.status_code = 200
                response._content = b'[{"movie":1},{"movie":2}]'
                with self.assertRaises(PolicyError):
                    requests.get("https://api.trakt.tv/search/imdb/tt123")
            finally:
                requests.sessions.Session.send = original

    def test_metadata(self):
        c = yaml.safe_load((ROOT / "config.yaml").read_text())
        self.assertEqual(set(c["options"]), set(c["schema"]))
        self.assertEqual(c["ports"], {})
        self.assertTrue(c["panel_admin"])
        self.assertFalse(c["options"]["sync_enabled"])
        self.assertFalse(c.get("host_network", False))
        self.assertEqual(c["arch"], ["amd64", "aarch64"])
        self.assertEqual(c["options"], json.loads((ROOT / "default-options.json").read_text()))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        write(self.directory / "options.json", options())
        self.c = Controller(self.directory)

    def tearDown(self):
        self.c.shutdown()
        self.temp.cleanup()

    def approve(self):
        write(self.directory / "analysis.json", {"fingerprint": self.c.identity()})
        self.c.action("approve", {})

    def test_no_writes_without_analysis_and_approval(self):
        self.assertFalse(self.c.run("sync"))
        self.assertIn("Analyze", self.c.error)
        with self.assertRaises(ValueError):
            self.c.action("approve", {})

    def test_approval_invalidated_by_options_or_credentials(self):
        self.approve()
        self.assertTrue(self.c.approved())
        self.c.action("credentials", {"plex_token": "secret"})
        self.assertFalse(self.c.approved())
        self.approve()
        self.c.options["ratings"] = True
        self.assertFalse(self.c.approved())

    def test_tokens_and_approval_survive_restart(self):
        self.c.action("credentials", {"plex_token": "secret"})
        self.approve()
        restarted = Controller(self.directory)
        self.assertEqual(restarted.credentials()["plex_token"], "secret")
        self.assertTrue(restarted.approved())
        self.assertNotIn("secret", json.dumps(restarted.status()))

    def test_no_parallel_job(self):
        self.c.lock.acquire()
        try:
            with patch("server.subprocess.Popen") as launch:
                self.assertFalse(self.c.run("analyze"))
                launch.assert_not_called()
        finally:
            self.c.lock.release()

    def test_error_reschedules_without_restart_loop(self):
        self.approve()
        process = Mock()
        process.wait.return_value = 1
        process.poll.return_value = 1
        with patch("server.subprocess.Popen", return_value=process):
            self.assertFalse(self.c.run("sync"))
        self.assertIn("check Plex", self.c.error)
        self.assertGreater(self.c.next_sync, __import__("time").time() + 3500)
        self.assertNotIn("last_success", self.c.state)

    def test_failed_reanalysis_revokes_existing_approval(self):
        self.approve()
        process = Mock()
        process.wait.return_value = 1
        process.poll.return_value = 1
        with patch("server.subprocess.Popen", return_value=process):
            self.assertFalse(self.c.run("analyze"))
        self.assertFalse(self.c.approved())
        self.assertIsNone(read(self.directory / "analysis.json"))

    def test_scheduler_runs_only_when_due_enabled_and_approved(self):
        self.approve()
        self.c.options["sync_enabled"] = True
        self.approve()
        self.c.next_sync = 0
        with patch.object(self.c.stop, "wait", side_effect=[False, True]), patch.object(self.c, "run") as run:
            self.c.schedule()
            run.assert_called_once_with("sync")
        self.c.state["paused"] = True
        with patch.object(self.c.stop, "wait", side_effect=[False, True]), patch.object(self.c, "run") as run:
            self.c.schedule()
            run.assert_not_called()

    def test_authentication_cannot_change_during_a_worker(self):
        self.c.lock.acquire()
        try:
            with self.assertRaises(ValueError):
                self.c.action("credentials", {"plex_token": "must-not-be-saved"})
            self.assertEqual(self.c.credentials(), {})
        finally:
            self.c.lock.release()

    def test_success_and_pause(self):
        self.approve()
        process = Mock()
        process.wait.return_value = 0
        with patch("server.subprocess.Popen", return_value=process):
            self.assertTrue(self.c.run("sync"))
        self.assertIn("last_success", read(self.directory / "state.json"))
        self.c.action("pause", {"paused": True})
        self.assertFalse(self.c.run("sync"))

    def test_device_flow_does_not_expose_device_or_access_tokens(self):
        self.c.action("credentials", {"client_id": "client"})
        r = Mock(status_code=200)
        r.json.return_value = {"device_code": "private", "user_code": "ABCD", "verification_url": "https://trakt.tv/activate",
                               "expires_in": 600, "interval": 5}
        with patch("server.requests.post", return_value=r):
            public = self.c.action("trakt-start", {})
        self.assertNotIn("private", json.dumps(public))
        r.json.return_value = {"access_token": "access", "refresh_token": "refresh", "created_at": 100, "expires_in": 600}
        with patch("server.requests.post", return_value=r):
            self.c.action("trakt-poll", {})
        stored = read(self.directory / ".pytrakt.json")
        self.assertEqual(stored["OAUTH_TOKEN"], "access")
        self.assertEqual(stored["OAUTH_EXPIRES_AT"], 700)
        self.assertNotIn("access", json.dumps(self.c.status()))

    def test_future_state_migration_fails_closed(self):
        write(self.directory / "state.json", {"version": 2})
        with self.assertRaises(ValueError):
            Controller(self.directory)


class UpstreamContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = tempfile.TemporaryDirectory()
        for key in ("PTS_CONFIG_DIR", "PTS_CACHE_DIR", "PTS_LOG_DIR"):
            os.environ[key] = cls.environment.name

    @classmethod
    def tearDownClass(cls):
        import logging
        logging.shutdown()
        cls.environment.cleanup()

    def test_pinned_upstream_configuration_contract(self):
        import importlib.metadata
        from plextraktsync.config.PlexServerConfig import PlexServerConfig
        expected = json.loads((ROOT / "upstream.json").read_text())["version"]
        self.assertEqual(importlib.metadata.version("PlexTraktSync"), expected)
        self.assertEqual(PlexServerConfig("default", "token", ["http://plex"],
                                         config={"libraries": ["Films"]}).libraries, ["Films"])

    def test_rating_conflicts_are_preserved_with_no_priority(self):
        from plextraktsync.sync.SyncRatingsPlugin import SyncRatingsPlugin
        class Config:
            plex_to_trakt = {"ratings": True}
            trakt_to_plex = {"ratings": True}
            def __getitem__(self, key):
                return "none"
        media = Mock(plex_rating=8, trakt_rating=6)
        asyncio.run(SyncRatingsPlugin(Config()).sync_ratings(media, dry_run=False))
        media.trakt_rate.assert_not_called()
        media.plex_rate.assert_not_called()

    def test_existing_history_is_not_added_again(self):
        from plextraktsync.sync.SyncWatchedPlugin import SyncWatchedPlugin
        c = Mock(plex_to_trakt={"watched_status": True}, trakt_to_plex={"watched_status": True})
        media = Mock(watched_on_plex=True, watched_on_trakt=True)
        asyncio.run(SyncWatchedPlugin(c).sync_watched(media, dry_run=False))
        media.mark_watched_trakt.assert_not_called()
        media.mark_watched_plex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
