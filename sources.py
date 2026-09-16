"""Live rating lookups for chess.com and lichess."""

import asyncio
import json
import time
from datetime import datetime, timezone

import aiohttp

# (site, time_control) -> (conversion source key, key in the site's JSON)
SUPPORTED = {
    ("chess.com", "blitz"): ("cc_blitz", "chess_blitz"),
    ("chess.com", "rapid"): ("cc_rapid", "chess_rapid"),
    ("chess.com", "bullet"): ("cc_bullet", "chess_bullet"),
    ("lichess", "blitz"): ("li_blitz", "blitz"),
    ("lichess", "rapid"): ("li_rapid", "rapid"),
    ("lichess", "bullet"): ("li_bullet", "bullet"),
    ("lichess", "classical"): ("li_classical", "classical"),
}

# chess.com rejects requests without a real User-Agent. Put a contact in here;
# they ask for one so they can reach you if the bot misbehaves.
USER_AGENT = "CGC-Rating-List-Bot/1.0 (contact: your-email@example.com)"

CACHE_TTL = 3600
_cache: dict[tuple, tuple[float, tuple]] = {}

# Whether fetch() also reports each player's last-played date. For lichess this
# costs a second API call per player per !rating (chess.com's is free, already
# in the stats response) - gated by the same flag so behaviour is consistent
# across sites regardless of that cost difference.
SHOW_LAST_PLAYED = True

# How many days without a game before a rating is flagged as stale.
STALE_DAYS = 30

# lichess's games-export endpoint (used for last-played lookups) is throttled
# more strictly than the rest of their API, even for a handful of concurrent
# callers - space these calls out rather than firing them in a burst.
LICHESS_GAMES_MIN_INTERVAL = 2.0  # seconds between calls to that endpoint
_lichess_games_lock = asyncio.Lock()
_lichess_games_last_call = 0.0


class NoRating(Exception):
    """The account or that time control has no usable rating."""


async def fetch(session, site, username, time_control):
    """Return (rating, last_played) for the player. Raises NoRating if there isn't one.

    last_played is an aware UTC datetime, or None if SHOW_LAST_PLAYED is False
    or the player has no rated games in that time control's history.
    """
    key = (site, username.lower(), time_control)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL:
        return cached[1]

    if site == "chess.com":
        result = await _fetch_chesscom(session, username, time_control)
    else:
        result = await _fetch_lichess(session, username, time_control)

    _cache[key] = (time.monotonic(), result)
    return result


async def _fetch_chesscom(session, username, time_control):
    field = SUPPORTED[("chess.com", time_control)][1]
    url = f"https://api.chess.com/pub/player/{username.lower()}/stats"
    async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
        if resp.status == 404:
            raise NoRating(f"no chess.com account '{username}'")
        resp.raise_for_status()
        data = await resp.json()

    entry = data.get(field)
    if not entry or "last" not in entry:
        raise NoRating(f"'{username}' has no rated chess.com {time_control} games")

    last_played = None
    if SHOW_LAST_PLAYED:
        last_played = datetime.fromtimestamp(entry["last"]["date"], tz=timezone.utc)
    return entry["last"]["rating"], last_played


async def _fetch_lichess(session, username, time_control):
    field = SUPPORTED[("lichess", time_control)][1]
    url = f"https://lichess.org/api/user/{username}"
    async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
        if resp.status == 404:
            raise NoRating(f"no lichess account '{username}'")
        resp.raise_for_status()
        data = await resp.json()

    if data.get("disabled"):
        raise NoRating(f"lichess account '{username}' is closed")

    perf = data.get("perfs", {}).get(field)
    if not perf or not perf.get("games"):
        raise NoRating(f"'{username}' has no rated lichess {time_control} games")

    last_played = None
    if SHOW_LAST_PLAYED:
        last_played = await _fetch_lichess_last_played(session, username, field)
    return perf["rating"], last_played


async def _fetch_lichess_last_played(session, username, perf_type):
    """UTC datetime of the most recent rated game in perf_type, or None if there isn't one."""
    global _lichess_games_last_call

    async with _lichess_games_lock:
        wait = LICHESS_GAMES_MIN_INTERVAL - (time.monotonic() - _lichess_games_last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _lichess_games_last_call = time.monotonic()

        url = f"https://lichess.org/api/games/user/{username}"
        params = {"max": 1, "perfType": perf_type, "rated": "true"}
        headers = {"User-Agent": USER_AGENT, "Accept": "application/x-ndjson"}
        async with session.get(url, params=params, headers=headers) as resp:
            resp.raise_for_status()
            body = (await resp.text()).strip()

    if not body:
        return None
    game = json.loads(body.splitlines()[0])
    return datetime.fromtimestamp(game["lastMoveAt"] / 1000, tz=timezone.utc)
