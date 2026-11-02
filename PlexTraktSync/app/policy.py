"""Immutable policy enforced below upstream's sync and watch code."""
import hashlib
import json
import re
from urllib.parse import urlsplit, unquote


class PolicyError(RuntimeError):
    pass


def fingerprint(options, credentials):
    return hashlib.sha256(json.dumps([options, credentials], sort_keys=True).encode()).hexdigest()


def config(options):
    return {
        "excluded-libraries": options["exclude_libraries"],
        "logging": {"debug": False},
        "config": {"dotenv_override": False},
        "plex": {"timeout": options["plex_timeout"]},
        "xbmc-providers": {"movies": options["movie_provider"], "shows": options["show_provider"]},
        "liked_lists": {"keep_watched": options["liked_lists_keep_watched"]},
        "liked_list": {entry["name"]: {"keep_watched": entry["keep_watched"]}
                       for entry in options["liked_list_overrides"]},
        "sync": {
            "rating_priority": options["rating_priority"],
            "plex_to_trakt": {
                "collection": False, "clear_collected": False,
                "ratings": options["ratings"] and options["plex_to_trakt_ratings"],
                "watched_status": options["plex_to_trakt_watched"],
                "watchlist": options["plex_to_trakt_watchlist"],
            },
            "trakt_to_plex": {
                "liked_lists": options["liked_lists"],
                "ratings": options["ratings"] and options["trakt_to_plex_ratings"],
                "watched_status": options["trakt_to_plex_watched"],
                "watchlist": options["trakt_to_plex_watchlist"],
                "watchlist_as_playlist": options["watchlist_as_playlist"],
                "playback_status": options["trakt_to_plex_playback"],
            },
        },
        "watch": {"add_collection": False, "remove_collection": False,
                  "username_filter": True, "media_progressbar": False,
                  "ignore_clients": options["watch_ignore_clients"]},
    }


def capabilities(options):
    return {
        "server_url": options["plex_url"],
        "trakt_ratings": options["ratings"] and options["plex_to_trakt_ratings"],
        "plex_ratings": options["ratings"] and options["trakt_to_plex_ratings"],
        "trakt_watched": options["plex_to_trakt_watched"],
        "plex_watched": options["trakt_to_plex_watched"] or options["trakt_to_plex_playback"],
        "trakt_watchlist": options["plex_to_trakt_watchlist"],
        "plex_watchlist": options["trakt_to_plex_watchlist"] and not options["watchlist_as_playlist"],
        "playlists": options["liked_lists"] or (options["trakt_to_plex_watchlist"] and options["watchlist_as_playlist"]),
        "playback": options["trakt_to_plex_playback"],
    }


def check_request(method, url, *, preview, ratings, permissions=None):
    """Allow reads and token refresh. All other writes require a narrow allowlist.

    Plex uses GET for scrobble/rate actions, so preview needs path checks too.
    Collection/favorites always stay protected. Optional writes require the
    corresponding approved setting and are checked on every redirected send.
    """
    parsed = urlsplit(url)
    path = unquote(parsed.path).rstrip("/")
    method = method.upper()
    rights = permissions or {"trakt_ratings": ratings, "plex_ratings": ratings,
                             "trakt_watched": True, "plex_watched": True}
    plex_mutation = any(p in path.lower() for p in
                        ("/:/scrobble", "/:/unscrobble", "/:/rate", "/:/timeline", "/:/progress"))
    if parsed.hostname == "api.trakt.tv":
        if parsed.scheme != "https":
            raise PolicyError("Trakt requires HTTPS")
        if method in ("GET", "HEAD"):
            return
        if method == "POST" and path == "/oauth/token":
            return  # Refresh changes credentials, never media data.
        allowed = {"/sync/history"} if rights["trakt_watched"] else set()
        if rights["trakt_ratings"]:
            allowed.add("/sync/ratings")
        if rights.get("trakt_watchlist"):
            allowed.update({"/sync/watchlist", "/sync/watchlist/remove"})
        if not preview and method == "POST" and path in allowed:
            return
        raise PolicyError("Trakt write blocked by app policy")
    if preview and (method not in ("GET", "HEAD") or plex_mutation):
        raise PolicyError("Preview blocked a Plex write")
    if "/:/unscrobble" in path.lower():
        raise PolicyError("Clearing Plex watched state is prohibited")
    base = urlsplit(rights.get("server_url", ""))
    own_plex = (parsed.scheme, parsed.netloc) == (base.scheme, base.netloc)
    if "server_url" not in rights:
        own_plex = True  # Legacy pure-policy callers; runtime always supplies the server.
    route = path
    if own_plex and base.path.rstrip("/"):
        prefix = base.path.rstrip("/")
        route = path[len(prefix):] if path.startswith(prefix + "/") else path
    if "/:/rate" in path.lower() and not (own_plex and rights["plex_ratings"]):
        raise PolicyError("Rating writes disabled")
    if "/:/scrobble" in path.lower() and not (own_plex and rights["plex_watched"]):
        raise PolicyError("Plex watched writes disabled")
    if any(p in path.lower() for p in ("/:/timeline", "/:/progress")) and not (own_plex and rights.get("playback")):
        raise PolicyError("Plex playback writes disabled")
    if method in ("GET", "HEAD"):
        return
    if own_plex and rights["plex_ratings"] and method == "PUT" and route == "/:/rate":
        return
    if (rights.get("plex_watchlist") and method == "PUT"
            and parsed.scheme == "https" and parsed.hostname == "discover.provider.plex.tv"
            and path in ("/actions/addToWatchlist", "/actions/removeFromWatchlist")):
        return
    if own_plex and rights.get("playlists"):
        if method == "POST" and route == "/playlists":
            return
        if method == "PUT" and re.fullmatch(r"/playlists/[0-9]+(?:/items)?", route):
            return
        if method == "DELETE" and re.fullmatch(r"/playlists/[0-9]+/items/[0-9]+", route):
            return
    raise PolicyError("Unexpected Plex write blocked")


def install_guard(preview, ratings, options=None):
    import requests
    original = requests.sessions.Session.send
    failures = []

    def guarded(session, request, **kwargs):
        check_request(request.method, request.url, preview=preview, ratings=ratings,
                      permissions=capabilities(options) if options is not None else None)
        if options and urlsplit(request.url).hostname == "api.trakt.tv":
            kwargs["timeout"] = options["request_timeout"]
        elif kwargs.get("timeout") is None:
            kwargs["timeout"] = options["request_timeout"] if options else 30
        try:
            response = original(session, request, **kwargs)
        except requests.RequestException:
            failures.append("ConnectionError")
            raise
        if response.status_code in (401, 403, 429) or response.status_code >= 500:
            failures.append(f"HTTP{response.status_code}")
        if (urlsplit(request.url).hostname == "api.trakt.tv"
                and urlsplit(request.url).path.startswith("/search/")):
            data = response.json()
            if isinstance(data, list) and len(data) > 1:
                raise PolicyError("Ambiguous Trakt ID match; refusing to select a title")
        return response

    requests.sessions.Session.send = guarded
    return failures
