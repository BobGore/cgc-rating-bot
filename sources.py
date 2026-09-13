"""Live rating lookups for chess.com and lichess."""

import time

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
_cache: dict[tuple, tuple[float, int]] = {}


class NoRating(Exception):
    """The account or that time control has no usable rating."""


async def fetch(session, site, username, time_control):
    """Return the player's current rating. Raises NoRating if there isn't one."""
    key = (site, username.lower(), time_control)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL:
        return cached[1]

    if site == "chess.com":
        rating = await _fetch_chesscom(session, username, time_control)
    else:
        rating = await _fetch_lichess(session, username, time_control)

    _cache[key] = (time.monotonic(), rating)
    return rating


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
    return entry["last"]["rating"]


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
    return perf["rating"]
