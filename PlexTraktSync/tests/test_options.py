import importlib.resources
import itertools
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from policy import PolicyError, capabilities, check_request, config, fingerprint, install_guard
from server import Controller
from settings import normalize_options
from storage import write


def defaults():
    return json.loads((ROOT / "default-options.json").read_text())


def check(options, method, url, preview=False):
    return check_request(method, url, preview=preview, ratings=options["ratings"], permissions=capabilities(options))


class MappingTests(unittest.TestCase):
    def test_every_upstream_sync_and_watch_key_has_a_mapping_or_explicit_lock(self):
        path = importlib.resources.files("plextraktsync").joinpath("config.default.yml")
        upstream = yaml.safe_load(path.read_text())
        result = config(defaults())
        self.assertEqual(set(result["sync"]), set(upstream["sync"]))
        for direction in ("plex_to_trakt", "trakt_to_plex"):
            self.assertEqual(set(result["sync"][direction]), set(upstream["sync"][direction]))
        self.assertEqual(set(result["watch"]), set(upstream["watch"]))
        self.assertEqual(set(result["liked_lists"]), set(upstream["liked_lists"]))
        self.assertEqual(set(result["xbmc-providers"]), set(upstream["xbmc-providers"]))

    def test_ratings_master_and_directions_are_independent(self):
        for master, p2t, t2p in itertools.product((True, False), repeat=3):
            options = defaults()
            options.update(ratings=master, plex_to_trakt_ratings=p2t, trakt_to_plex_ratings=t2p)
            result = config(options)["sync"]
            self.assertEqual(result["plex_to_trakt"]["ratings"], master and p2t)
            self.assertEqual(result["trakt_to_plex"]["ratings"], master and t2p)
            rights = capabilities(options)
            self.assertEqual(rights["trakt_ratings"], master and p2t)
            self.assertEqual(rights["plex_ratings"], master and t2p)

    def test_runtime_settings_and_list_overrides_map_to_upstream(self):
        options = defaults()
        options.update(plex_timeout=65, movie_provider="tmdb", show_provider="imdb",
                       watch_ignore_clients=["client-id"], liked_lists=True, liked_lists_keep_watched=False,
                       liked_list_overrides=[{"name": "My List", "keep_watched": True}])
        result = config(normalize_options(options))
        self.assertEqual(result["plex"]["timeout"], 65)
        self.assertEqual(result["watch"]["ignore_clients"], ["client-id"])
        self.assertEqual(result["liked_list"], {"My List": {"keep_watched": True}})
        self.assertFalse(result["liked_lists"]["keep_watched"])
        self.assertEqual(result["xbmc-providers"], {"movies": "tmdb", "shows": "imdb"})

    def test_old_options_keep_safe_defaults_and_invalidate_old_approval(self):
        old = {k: defaults()[k] for k in ("plex_url", "plex_username", "sync_enabled", "sync_interval_minutes",
                                        "watch_enabled", "plex_to_trakt_watched", "trakt_to_plex_watched",
                                        "ratings", "rating_priority", "include_libraries", "exclude_libraries", "log_level")}
        old["ratings"] = True
        migrated = normalize_options(old)
        self.assertTrue(migrated["plex_to_trakt_ratings"])
        self.assertTrue(migrated["trakt_to_plex_ratings"])
        self.assertFalse(migrated["plex_to_trakt_watchlist"])
        self.assertFalse(migrated["liked_lists"])
        self.assertFalse(migrated["trakt_to_plex_playback"])
        self.assertNotEqual(fingerprint(old, {}), fingerprint(migrated, {}))

    def test_every_native_option_has_german_and_english_help(self):
        for language in ("en", "de"):
            translation = yaml.safe_load((ROOT / "translations" / (language + ".yaml")).read_text(encoding="utf-8"))
            self.assertEqual(set(translation["configuration"]), set(defaults()))
            self.assertTrue(all(item.get("description") and item.get("name")
                                for item in translation["configuration"].values()))

    def test_unknown_collection_overrides_and_invalid_ids_are_rejected(self):
        for extra in ({"collection": True}, {"username_filter": False}, {"ignore_ids": ["../token"]},
                      {"plex_timeout": True}, {"liked_list_overrides": [{"name": "X", "keep_watched": "yes"}]}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                normalize_options({**defaults(), **extra})


class OptionalWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {key: cls.temp.name for key in
                             ("PTS_CONFIG_DIR", "PTS_CACHE_DIR", "PTS_LOG_DIR")})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()
        cls.env.stop()
        cls.temp.cleanup()

    def options(self, **extra):
        return {**defaults(), "plex_url": "http://plex:32400", **extra}

    def test_watchlist_writes_require_the_exact_direction(self):
        for p2t, t2p, playlist in itertools.product((True, False), repeat=3):
            o = self.options(plex_to_trakt_watchlist=p2t, trakt_to_plex_watchlist=t2p, watchlist_as_playlist=playlist)
            for path in ("/sync/watchlist", "/sync/watchlist/remove"):
                if p2t:
                    check(o, "POST", "https://api.trakt.tv" + path)
                else:
                    with self.assertRaises(PolicyError):
                        check(o, "POST", "https://api.trakt.tv" + path)
            for action in ("addToWatchlist", "removeFromWatchlist"):
                url = "https://discover.provider.plex.tv/actions/" + action
                if t2p and not playlist:
                    check(o, "PUT", url)
                else:
                    with self.assertRaises(PolicyError):
                        check(o, "PUT", url)

    def test_preview_blocks_every_optional_mutation_even_when_enabled(self):
        o = self.options(ratings=True, liked_lists=True, plex_to_trakt_watchlist=True,
                         trakt_to_plex_watchlist=True, trakt_to_plex_playback=True)
        operations = [("POST", "https://api.trakt.tv/sync/watchlist"),
                      ("PUT", "https://discover.provider.plex.tv/actions/removeFromWatchlist"),
                      ("POST", "http://plex:32400/playlists"),
                      ("DELETE", "http://plex:32400/playlists/10/items/11"),
                      ("GET", "http://plex:32400/:/progress?key=1&time=900"),
                      ("GET", "http://plex:32400/%3A/progress?key=1")]
        for method, url in operations:
            with self.subTest(url=url), self.assertRaises(PolicyError):
                check(o, method, url, preview=True)

    def test_collection_favorites_and_foreign_users_never_become_writable(self):
        o = self.options(ratings=True, liked_lists=True, plex_to_trakt_watchlist=True,
                         trakt_to_plex_watchlist=True, trakt_to_plex_playback=True)
        for endpoint in ("/sync/collection", "/sync/collection/remove", "/sync/favorites",
                         "/users/me/lists/favorites/items", "/scrobble/stop"):
            with self.subTest(endpoint=endpoint), self.assertRaises(PolicyError):
                check(o, "POST", "https://api.trakt.tv" + endpoint)
        self.assertTrue(config(o)["watch"]["username_filter"])

    def test_playlist_writes_are_limited_to_configured_plex_and_item_endpoints(self):
        o = self.options(liked_lists=True)
        for method, path in (("POST", "/playlists"), ("PUT", "/playlists/10/items"),
                             ("DELETE", "/playlists/10/items/11")):
            check(o, method, "http://plex:32400" + path)
            with self.assertRaises(PolicyError):
                check(o, method, "http://other:32400" + path)
        with self.assertRaises(PolicyError):
            check(o, "DELETE", "http://plex:32400/library/metadata/42")
        with self.assertRaises(PolicyError):
            check(o, "DELETE", "http://plex:32400/playlists/10")

    def test_playback_and_reverse_watched_directions_are_enforced(self):
        o = self.options()
        for path in ("/:/scrobble", "/:/progress", "/:/timeline"):
            with self.assertRaises(PolicyError):
                check(o, "GET", "http://plex:32400" + path)
        o["trakt_to_plex_playback"] = True
        check(o, "GET", "http://plex:32400/:/progress")
        check(o, "GET", "http://plex:32400/:/scrobble")
        with self.assertRaises(PolicyError):
            check(o, "GET", "http://plex:32400/:/unscrobble")

    def test_actual_upstream_watchlist_plugin_honors_directions_and_dry_run(self):
        from plextraktsync.sync.WatchListPlugin import WatchListPlugin
        for forward, reverse, dry_run in itertools.product((True, False), repeat=3):
            if not forward and not reverse:
                continue
            plugin = WatchListPlugin(Mock(update_trakt_wl=forward, update_plex_wl=reverse), Mock(), Mock())
            plugin.logger = Mock()
            media = Mock(plex=object())
            plugin.plex_wl = {media}
            plugin.trakt_wl = set()
            plugin.watchlist_sync_item(media, dry_run)
            self.assertEqual(media.add_to_trakt_watchlist.call_count, int(forward and not dry_run))
            self.assertEqual(media.remove_from_plex_watchlist.call_count, int(not forward and not dry_run))

    def test_trakt_timeout_is_applied_to_the_actual_transport(self):
        o = self.options(request_timeout=70)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{}'
        with patch.object(requests.sessions.Session, "send", return_value=response) as transport:
            original = requests.sessions.Session.send
            try:
                install_guard(preview=True, ratings=False, options=o)
                requests.get("https://api.trakt.tv/users/me", timeout=10)
                self.assertEqual(transport.call_args.kwargs["timeout"], 70)
            finally:
                requests.sessions.Session.send = original


if __name__ == "__main__":
    unittest.main()
