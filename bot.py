"""CGC Rating List Bot.

Commands:
    !add <username> <site> <time_control>
    !remove <username>
    !rating
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands

import sources
import store
from conversion import OutOfRange, to_uscf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ratingbot")

MAX_MESSAGE = 1900  # Discord's limit is 2000; leave room for the code fences.
MAX_CONCURRENT_FETCHES = 5

# Every command only works in one of these channels (the live rating channel,
# plus a test channel on a separate server). A channel ID only ever belongs to
# one server, so this also keeps the bot inert everywhere else it might get
# invited to, and in DMs - no separate guild check needed.
ALLOWED_CHANNEL_IDS = {
    853715007311970314,  # live
    1548669940368941108,  # test
}

# Can !remove any entry, regardless of who registered it.
ADMIN_USER_IDS = {
    810486671174795274,  # Bob
    315229727629508609,  # Matt
}

# (lower bound on USCF-equivalent, heading)
SECTIONS = [
    (1700, "+1700 Section"),
    (1400, "U1700 Section"),
    (1100, "U1400 Section"),
    (0, "U1100 Section"),
]

intents = discord.Intents.default()
intents.message_content = True
# Command input (usernames, site, time control) gets echoed back in replies
# unfiltered - this stops any of it from ever triggering a real @everyone/
# @here/role/user ping, regardless of what ends up in a message.
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    allowed_mentions=discord.AllowedMentions.none(),
)


@bot.event
async def on_ready():
    log.info("connected as %s", bot.user)


@bot.check
async def _in_rating_channel(ctx):
    return ctx.channel.id in ALLOWED_CHANNEL_IDS


@bot.command()
async def add(ctx, username: str, site: str, time_control: str):
    site, time_control = site.lower(), time_control.lower()

    if (site, time_control) not in sources.SUPPORTED:
        await _reject(ctx, f"`{site} {time_control}` isn't a combination I track")
        return

    async with aiohttp.ClientSession() as session:
        try:
            await sources.fetch(session, site, username, time_control)
        except sources.NoRating as exc:
            await _reject(ctx, str(exc))
            return
        except aiohttp.ClientError as exc:
            await _reject(ctx, f"couldn't reach {site} ({exc})")
            return

    if not store.add(site, username, time_control, ctx.author.id):
        await _reject(ctx, f"{username} is already on the list for {site} {time_control}")
        return

    await ctx.message.add_reaction("\u2705")


@bot.command()
async def remove(ctx, username: str):
    owners = store.owners(username)
    if not owners:
        await _reject(ctx, f"'{username}' isn't on the list")
        return

    if ctx.author.id not in ADMIN_USER_IDS and owners != {ctx.author.id}:
        await _reject(ctx, f"only {username} or an admin can remove this")
        return

    store.remove(username)
    await ctx.message.add_reaction("\u2705")


@bot.command(name="helpratingbot")
async def help_rating_bot(ctx):
    await ctx.send(
        "**CGC Rating List Bot**\n"
        "`!add <username> <site> <time control>` — e.g. `!add Xadec chess.com blitz`\n"
        "`!remove <username>` — removes every entry for that username\n"
        "`!rating` — the current list\n"
        "Sites: `chess.com` (blitz, rapid, bullet), `lichess` (blitz, rapid, bullet, classical).\n"
        "OTB estimates use the ChessGoals July 2026 conversion, USCF scale."
    )


@bot.command()
async def rating(ctx):
    players = store.all_players()
    if not players:
        await ctx.send("Nobody is registered yet. Use `!add <username> <site> <time control>`.")
        return

    async with ctx.typing():
        rows, problems = await _gather(players)

    for block in _render(rows):
        await ctx.send(block)

    if problems:
        await ctx.send("Not shown: " + "; ".join(problems))


async def _gather(players):
    """Fetch and convert every player. Returns (rows, problem descriptions)."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def one(session, site, username, time_control):
        async with semaphore:
            return await sources.fetch(session, site, username, time_control)

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *(one(session, *p) for p in players), return_exceptions=True
        )

    rows, problems = [], []
    for (site, username, time_control), result in zip(players, results):
        if isinstance(result, Exception):
            problems.append(f"{username} ({result})")
            continue
        rating, last_played = result
        source = sources.SUPPORTED[(site, time_control)][0]
        try:
            otb = to_uscf(rating, source)
        except OutOfRange as exc:
            problems.append(f"{username} ({exc})")
            continue
        rows.append((username, otb, rating, f"{site} {time_control}", last_played))

    rows.sort(key=lambda r: (-r[1], r[0].lower()))
    return rows, problems


def _last_played_note(last_played):
    """Trailing note for a row: the last-played date, flagged if it's stale. Kept short to avoid wrapping."""
    if last_played is None:
        return ""
    days_ago = (datetime.now(timezone.utc) - last_played).days
    date_str = last_played.date().isoformat()
    if days_ago > sources.STALE_DAYS:
        return f"  (last game: {date_str} — Stale {sources.STALE_DAYS}+ days)"
    return f"  (last game: {date_str})"


def _render(rows):
    """Yield message-sized code blocks, one or more per section."""
    for index, (floor, heading) in enumerate(SECTIONS):
        ceiling = SECTIONS[index - 1][0] if index else None
        section = [r for r in rows if r[1] >= floor and (ceiling is None or r[1] < ceiling)]
        if not section:
            continue

        width = max(len("Username"), max(len(r[0]) for r in section))
        header = (
            f"{'Username':<{width}}  {'CGC OTB Rating':>16}  {'Online Rating':>15}  Site\n"
            f"{'-' * width}  {'-' * 16}  {'-' * 15}  {'-' * 17}"
        )
        lines = [
            f"{name:<{width}}  {otb:>16}  {online:>15}  {site}{_last_played_note(last_played)}"
            for name, otb, online, site, last_played in section
        ]

        first = True
        while lines:
            body, size = [], 0
            while lines and size + len(lines[0]) + 1 <= MAX_MESSAGE - len(header):
                size += len(lines[0]) + 1
                body.append(lines.pop(0))
            title = f"__{heading}__\n" if first else ""
            yield title + "```\n" + header + "\n" + "\n".join(body) + "\n```"
            first = False


async def _reject(ctx, reason):
    await ctx.message.add_reaction("\u274c")
    await ctx.send(reason)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await _reject(ctx, "Usage: `!add <username> <site> <time control>`")
    elif isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
        pass
    else:
        log.exception("command failed", exc_info=error)
        await _reject(ctx, "something went wrong, check the logs")


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set")
    bot.run(token)
