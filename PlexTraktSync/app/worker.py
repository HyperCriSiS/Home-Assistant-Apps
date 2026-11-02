"""Short lived upstream worker. Only the supervisor process schedules writers."""
import asyncio
import contextlib
import logging
import json
import os
import signal
from pathlib import Path
import sys

from policy import config, fingerprint, install_guard
from storage import read, write
from settings import normalize_options


async def analyze(factory):
    counts = {"watched_movies": 0, "watched_episodes": 0, "missing_in_trakt": 0,
              "already_in_trakt": 0, "rating_conflicts": 0, "show_rating_conflicts": 0,
              "unmatched": [], "not_traversed": [], "missing_titles": [],
              "existing_titles": [], "rating_conflict_titles": []}
    inventory = {}
    for section in factory.plex_api.library_sections.values():
        if section.type not in ("movie", "show"):
            continue
        if section.type == "movie" and not factory.walk_config.walk_movies:
            continue
        if section.type == "show" and not factory.walk_config.walk_shows:
            continue
        for item in section.pager("episode") if section.type == "show" else section.pager():
            if item.key in factory.server_config.ignore_ids:
                continue
            inventory[item.key] = item
    for item in inventory.values():
        if item.is_watched:
            counts["watched_episodes" if item.type == "episode" else "watched_movies"] += 1
    visited, rating_conflicts = set(), set()
    # Capture failed upstream resolutions as well as resolved walk results.
    original = factory.media_factory.resolve_any

    def resolve(item, *args, **kwargs):
        if item.key in factory.server_config.ignore_ids:
            return None
        visited.add(item.key)
        media = original(item, *args, **kwargs)
        if media is None:
            counts["unmatched"].append(str(item.title))
        else:
            a, b = media.plex_rating, media.trakt_rating
            if a is not None and b is not None and not a == b and item.key not in rating_conflicts:
                rating_conflicts.add(item.key)
                counts["rating_conflicts"] += 1
                counts["rating_conflict_titles"].append(str(item.title))
                if item.type == "show":
                    counts["show_rating_conflicts"] += 1
        return media

    factory.media_factory.resolve_any = resolve
    iterators = []
    if factory.walk_config.walk_movies:
        iterators.append(factory.walker.find_movies())
    if factory.walk_config.walk_shows:
        iterators.append(factory.walker.find_episodes())
    for iterator in iterators:
        async for media in iterator:
            if media.watched_on_plex:
                counts["already_in_trakt" if media.watched_on_trakt else "missing_in_trakt"] += 1
                counts["existing_titles" if media.watched_on_trakt else "missing_titles"].append(str(media.plex.title))
    counts["not_traversed"] = [str(item.title) for key, item in inventory.items() if key not in visited]
    counts["unmatched"].extend(counts["not_traversed"])
    factory.media_factory.resolve_any = original
    return counts


def main(mode, directory, ids=None):
    directory = Path(directory)
    options = normalize_options(read(directory / "options.json"))
    credentials = read(directory / "credentials.json", {})
    current = fingerprint(options, credentials)
    preview = mode == "analyze"
    if mode not in ("analyze", "sync", "incremental"):
        raise ValueError("Unsupported worker mode")
    if not preview and read(directory / "approval.json", {}).get("fingerprint") != current:
        raise ValueError("Initial analysis and explicit approval required")
    effective = dict(options)
    if mode == "incremental":
        # An item event must never replace an entire global list/playlist.
        for key in ("plex_to_trakt_watchlist", "trakt_to_plex_watchlist", "liked_lists"):
            effective[key] = False
    failures = install_guard(preview, options["ratings"], options=effective)
    # Regenerate the policy every run; never merge editable or inherited sync options.
    write(directory / "config.yml", config(effective))  # JSON is valid YAML.
    server_config = {"excluded-libraries": options["exclude_libraries"],
                     "ignore_ids": [int(value) for value in options["ignore_ids"]]}
    if options["include_libraries"]:
        server_config["libraries"] = options["include_libraries"]
    write(directory / "servers.yml", {"servers": {"default": {
        "urls": [options["plex_url"]], "token": credentials["plex_token"],
        "config": server_config,
    }}})
    os.environ["PLEX_SERVER"] = "default"
    os.environ["PLEX_USERNAME"] = options["plex_username"]
    from plextraktsync.factory import factory
    factory.run_config.update(progressbar=False, cache=False, batch_delay=options["batch_delay"])
    factory.walk_config.update(movies=options["sync_media"] in ("all", "movies"),
                               shows=options["sync_media"] in ("all", "tv"),
                               watchlist=mode != "incremental")
    if mode == "incremental":
        if not ids or any(not key.isdecimal() or len(key) > 12 for key in ids):
            raise ValueError("Invalid Plex item IDs")
        for key in ids:
            factory.walk_config.add_id(key)
    # A user-specific token is required. Validate identity rather than trusting a
    # text username to filter server-wide watched state belonging to another user.
    account = factory.plex_api.account
    if account is None or account.username.casefold() != options["plex_username"].casefold():
        raise ValueError("Plex token does not belong to the configured account")
    factory.trakt_api.me  # Validate OAuth; never enter an interactive login path.
    if preview:
        report = asyncio.run(analyze(factory))
        optional = any(options[key] for key in ("plex_to_trakt_watchlist", "trakt_to_plex_watchlist",
                                                "liked_lists", "trakt_to_plex_playback"))
        if optional:
            # Exercise the actual upstream plan, additionally protected at HTTP
            # level. List replacements are disclosed; exact playlist diffs aren't
            # available in upstream's preview API.
            asyncio.run(factory.sync.sync(factory.walker, dry_run=True))
        report["sync_options"] = config(options)["sync"]
        report["warnings"] = []
        if options["plex_to_trakt_watchlist"] or options["trakt_to_plex_watchlist"]:
            report["warnings"].append("Watchlist sync can add AND REMOVE entries; one-way mode mirrors the selected source.")
        if options["liked_lists"] or (options["trakt_to_plex_watchlist"] and options["watchlist_as_playlist"]):
            report["warnings"].append("Managed Plex playlist contents can be replaced. Exact playlist differences are not included in this report.")
        if options["trakt_to_plex_playback"]:
            report["warnings"].append("Trakt playback progress overwrites Plex progress and marks items watched at >=99%, even when reverse watched sync is off.")
        if failures:
            raise RuntimeError("Analysis had API errors; approval refused")
        report.update(fingerprint=current)
        write(directory / "analysis.json", report)
    else:
        # Upstream's background queue logs and swallows submission failures.
        # Preserve its batching but propagate those failures to the scheduler.
        from plextraktsync.queue.BackgroundTask import BackgroundTask
        errors = []

        def flush(task):
            for operation in task.tasks:
                try:
                    operation(task.queues)
                except Exception as error:
                    errors.append(type(error).__name__)

        BackgroundTask.timed_events = flush
        asyncio.run(factory.sync.sync(factory.walker, dry_run=False))
        if "queue" in factory.__dict__:
            factory.queue.close()
        if errors or failures:
            raise RuntimeError("Upstream queue submission failed")


if __name__ == "__main__":
    # Normal interpreter exit runs upstream's registered queue drain.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    # Upstream exception messages may contain URLs with tokens. Return only a
    # classified error; never persist or print raw upstream stdout/tracebacks.
    try:
        logging.disable(100)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            main(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else None)
    except Exception as error:
        write(Path(sys.argv[2]) / "worker-error.json", {"type": type(error).__name__})
        sys.exit(1)
