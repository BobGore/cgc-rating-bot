# cgc-rating-bot

A Discord bot that keeps a rating list for a chess club: members register an
online account, and the bot shows everyone's current rating alongside an
over-the-board estimate, split into rating sections.

## Commands

| Command | Effect |
| --- | --- |
| `!add <username> <site> <time control>` | Register an account, e.g. `!add Xadec chess.com blitz`. Validated against the site's API before it is stored. |
| `!remove <username>` | Removes every entry for that username. |
| `!rating` | Prints the current list. |
| `!helpratingbot` | Command summary. |

Sites: `chess.com` (blitz, rapid, bullet) and `lichess` (blitz, rapid, bullet,
classical).

## The OTB estimate

Ratings are converted using the [ChessGoals rating
comparison](https://chessgoals.com/rating-comparison/) fits (July 2026), which
model each rating pool as a cubic in Chess.com blitz. A non-blitz rating is
inverted back to blitz first, then pushed through the USCF cubic.

Two things worth knowing:

- The fits only cover blitz 500–3000. Ratings outside that range are reported
  as unconvertible rather than extrapolated — the cubics diverge badly beyond
  their domain.
- FIDE is deliberately not offered. Its cubic is non-monotonic below blitz
  1047, so inverting a FIDE rating between roughly 1660 and 1815 has two
  solutions and picks the wrong one.

The coefficients are refitted annually. To update, replace the `COEFFS` dict in
`conversion.py` and run `python3 check_coeffs.py`, which verifies that every
cubic is still monotonic across the domain — the assumption the inversion
depends on.

## Running it

```bash
python3 -m venv venv
venv/bin/pip install discord.py aiohttp

echo 'DISCORD_TOKEN=...' > .env && chmod 600 .env

cp roster.csv.example roster.csv    # optional: bulk-load existing members
venv/bin/python seed.py

set -a && . ./.env && set +a
venv/bin/python bot.py
```

The bot needs the **Message Content** privileged intent enabled in the Discord
developer portal, and the permissions Send Messages, Read Message History and
Add Reactions (bitfield `67648`).

For a persistent install, edit the paths in `ratingbot.service`, copy it to
`/etc/systemd/system/`, and `systemctl enable --now ratingbot`.

## Layout

| File | Purpose |
| --- | --- |
| `bot.py` | Commands and table rendering |
| `conversion.py` | Rating conversion, the only file that knows about the cubics |
| `sources.py` | chess.com and lichess lookups, with a one-hour cache |
| `store.py` | SQLite persistence |
| `seed.py` | Bulk-load from `roster.csv` |
| `check_coeffs.py` | Validates coefficients after an update |
| `set_owner.py` | Backfill who a pre-existing registration belongs to |

`.env`, `players.db` and `roster.csv` are gitignored: a token, local data, and
a list of real accounts respectively.

## Note on the User-Agent

chess.com rejects API requests without a real `User-Agent`. Put a working
contact address in `sources.py` before deploying — they ask for one so they can
reach you if the bot misbehaves.
