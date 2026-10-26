"""Immutable policy enforced below upstream's sync and watch code."""
import hashlib
import json
from urllib.parse import urlsplit


class PolicyError(RuntimeError):
    pass


def fingerprint(options, credentials):
    return hashlib.sha256(json.dumps([options, credentials], sort_keys=True).encode()).hexdigest()


def config(options):
    return {
        "excluded-libraries": options["exclude_libraries"],
        "logging": {"debug": False},
        "sync": {
            "rating_priority": options["rating_priority"],
            "plex_to_trakt": {
                "collection": False, "clear_collected": False,
                "ratings": options["ratings"],
                "watched_status": options["plex_to_trakt_watched"], "watchlist": False,
            },
            "trakt_to_plex": {
                "liked_lists": False, "ratings": options["ratings"],
                "watched_status": options["trakt_to_plex_watched"],
                "watchlist": False, "watchlist_as_playlist": False, "playback_status": False,
            },
        },
        "watch": {"add_collection": False, "remove_collection": False,
                  "username_filter": True, "media_progressbar": False},
    }


def check_request(method, url, *, preview, ratings):
    """Allow reads and token refresh. All other writes require a narrow allowlist.

    Plex uses GET for scrobble/rate actions, so preview needs path checks too.
    Never permit collection/watchlist/list/favorite mutations, even if upstream
    defaults or a later command change. Validate redirects on every send.
    """
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    method = method.upper()
    plex_mutation = any(p in path.lower() for p in
                        ("/:/scrobble", "/:/unscrobble", "/:/rate", "/:/timeline"))
    if parsed.hostname == "api.trakt.tv":
        if parsed.scheme != "https":
            raise PolicyError("Trakt requires HTTPS")
        if method in ("GET", "HEAD"):
            return
        if method == "POST" and path == "/oauth/token":
            return  # Refresh changes credentials, never media data.
        allowed = {"/sync/history"}
        if ratings:
            allowed.add("/sync/ratings")
        if not preview and method == "POST" and path in allowed:
            return
        raise PolicyError("Trakt write blocked by app policy")
    if preview and (method not in ("GET", "HEAD") or plex_mutation):
        raise PolicyError("Preview blocked a Plex write")
    if "/:/unscrobble" in path.lower():
        raise PolicyError("Clearing Plex watched state is prohibited")
    if not ratings and "/:/rate" in path.lower():
        raise PolicyError("Rating writes disabled")
    if method not in ("GET", "HEAD") and not (ratings and method == "PUT" and path == "/:/rate"):
        raise PolicyError("Unexpected Plex write blocked")


def install_guard(preview, ratings):
    import requests
    original = requests.sessions.Session.send
    failures = []

    def guarded(session, request, **kwargs):
        check_request(request.method, request.url, preview=preview, ratings=ratings)
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = 30
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
