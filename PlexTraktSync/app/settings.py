"""Normalize persisted HA options and migrate additive settings safely."""
import json
from pathlib import Path
from urllib.parse import urlsplit


def normalize_options(raw):
    path = Path(__file__).with_name("default-options.json")
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / "default-options.json"
    defaults = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) - set(defaults):
        raise ValueError("Unknown or invalid App options; raw upstream overrides are prohibited")
    options = {**defaults, **raw}
    for key, default in defaults.items():
        value = options[key]
        if isinstance(default, bool) and type(value) is not bool:
            raise ValueError(f"Invalid boolean option {key}")
        if isinstance(default, list) and not isinstance(value, list):
            raise ValueError(f"Invalid list option {key}")
        if isinstance(default, str) and (not isinstance(value, str) or len(value) > 2048):
            raise ValueError(f"Invalid text option {key}")
    url = options["plex_url"]
    try:
        parsed = urlsplit(url)
        if url and (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or any(c.isspace() for c in url)):
            raise ValueError()
        parsed.port
    except ValueError:
        raise ValueError("plex_url requires an HTTP or HTTPS server URL without credentials") from None
    if len(options["plex_username"]) > 256 or any(ord(c) < 32 for c in options["plex_username"]):
        raise ValueError("Invalid Plex username")
    for key, low, high in (("plex_timeout", 5, 300), ("request_timeout", 5, 300),
                           ("batch_delay", 0, 300), ("sync_interval_minutes", 15, 1440)):
        if type(options[key]) is not int or not low <= options[key] <= high:
            raise ValueError(f"Invalid numeric option {key}")
    choices = {"rating_priority": {"none", "plex", "trakt"}, "sync_media": {"all", "movies", "tv"},
               "movie_provider": {"imdb", "tmdb"}, "show_provider": {"imdb", "tvdb", "tmdb"},
               "log_level": {"info", "warning", "error"}}
    for key, allowed in choices.items():
        if options[key] not in allowed:
            raise ValueError(f"Invalid option {key}")
    for key in ("include_libraries", "exclude_libraries", "watch_ignore_clients", "ignore_ids"):
        if len(options[key]) > 1000 or any(not isinstance(value, str) or not value.strip()
                                           or len(value) > 512 for value in options[key]):
            raise ValueError(f"Invalid entries in {key}")
    if any(not value.isascii() or not value.isdecimal() or len(value) > 12 for value in options["ignore_ids"]):
        raise ValueError("ignore_ids must contain numeric Plex item IDs")
    names = set()
    for entry in options["liked_list_overrides"]:
        if (not isinstance(entry, dict) or set(entry) != {"name", "keep_watched"}
                or not isinstance(entry["name"], str) or not entry["name"].strip() or len(entry["name"]) > 512
                or type(entry["keep_watched"]) is not bool or entry["name"] in names):
            raise ValueError("Liked-list overrides require unique names and boolean keep_watched")
        names.add(entry["name"])
    return options
