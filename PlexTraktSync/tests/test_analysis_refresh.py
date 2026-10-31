import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from storage import read, write
from worker import analyze


class AnalysisTests(unittest.TestCase):
    def fixture(self):
        items = {key: SimpleNamespace(key=key, title=f"Title {key}", type=kind, is_watched=True)
                 for key, kind in ((1, "movie"), (2, "movie"), (3, "movie"),
                                   (4, "episode"), (5, "episode"), (6, "show"))}
        def media(key, watched, a=None, b=None):
            return SimpleNamespace(watched_on_plex=True, watched_on_trakt=watched,
                                   plex_rating=a, trakt_rating=b, plex=items[key])
        media_items = {1: media(1, False, 8, 6), 2: media(2, True, 8, 8),
                       4: media(4, True), 6: media(6, True, 9, 4)}
        mf = SimpleNamespace(resolve_any=lambda item: media_items.get(item.key))

        async def movies():
            for key in (1, 2, 3):
                value = mf.resolve_any(items[key])
                if value:
                    yield value

        async def episodes():
            mf.resolve_any(items[6])
            yield mf.resolve_any(items[4])
            # Item 5 simulates an episode skipped because its parent disappeared.

        return SimpleNamespace(
            walk_config=SimpleNamespace(walk_movies=True, walk_shows=True),
            server_config=SimpleNamespace(ignore_ids=[]),
            media_factory=mf,
            walker=SimpleNamespace(find_movies=movies, find_episodes=episodes),
            plex_api=SimpleNamespace(library_sections={
                1: SimpleNamespace(type="movie", pager=lambda: [items[k] for k in (1, 2, 3)]),
                2: SimpleNamespace(type="show", pager=lambda _: [items[k] for k in (4, 5)]),
            }),
        )

    def test_counts_cover_unmatched_titles_skipped_episodes_and_show_ratings(self):
        factory = self.fixture()
        factory.sync = Mock()
        report = asyncio.run(analyze(factory))
        self.assertEqual(report["watched_movies"], 3)
        self.assertEqual(report["watched_episodes"], 2)
        self.assertEqual(report["missing_in_trakt"], 1)
        self.assertEqual(report["already_in_trakt"], 2)
        self.assertEqual(report["rating_conflicts"], 2)
        self.assertEqual(report["show_rating_conflicts"], 1)
        self.assertEqual(report["not_traversed"], ["Title 5"])
        self.assertEqual(report["missing_titles"], ["Title 1"])
        self.assertEqual(set(report["existing_titles"]), {"Title 2", "Title 4"})
        self.assertEqual(set(report["rating_conflict_titles"]), {"Title 1", "Title 6"})
        self.assertEqual(set(report["unmatched"]), {"Title 3", "Title 5"})
        factory.sync.assert_not_called()

    def test_failed_reader_does_not_produce_a_successful_report(self):
        factory = self.fixture()
        factory.media_factory.resolve_any = Mock(side_effect=ConnectionError("simulated"))
        with self.assertRaises(ConnectionError):
            asyncio.run(analyze(factory))


class RefreshTests(unittest.TestCase):
    def test_upstream_refresh_updates_persistent_pytrakt_format(self):
        from trakt.api import TokenAuth
        from trakt.config import AuthConfig
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".pytrakt.json"
            write(path, {"CLIENT_ID": "client", "CLIENT_SECRET": None,
                         "OAUTH_TOKEN": "old", "OAUTH_REFRESH": "refresh", "OAUTH_EXPIRES_AT": 1})
            config = AuthConfig(str(path)).update(CLIENT_ID=None, CLIENT_SECRET=None,
                                                  OAUTH_TOKEN=None, OAUTH_REFRESH=None, OAUTH_EXPIRES_AT=None)
            config.load()
            client = Mock()
            client.post.return_value = {"access_token": "new", "refresh_token": "next",
                                        "created_at": 2000000000, "expires_in": 3600}
            auth = TokenAuth(client=client, config=config)
            auth.refresh_token()
            stored = read(path)
            self.assertEqual(stored["OAUTH_TOKEN"], "new")
            self.assertEqual(stored["OAUTH_REFRESH"], "next")
            self.assertEqual(stored["OAUTH_EXPIRES_AT"], 2000003600)
            self.assertEqual(client.post.call_args.args[0], "oauth/token")


if __name__ == "__main__":
    unittest.main()
