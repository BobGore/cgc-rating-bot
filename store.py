"""SQLite storage for registered players."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("players.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    site         TEXT NOT NULL,
    username     TEXT NOT NULL COLLATE NOCASE,
    time_control TEXT NOT NULL,
    added_at     TEXT NOT NULL DEFAULT (datetime('now')),
    added_by     INTEGER,
    PRIMARY KEY (site, username, time_control)
);
"""


DB_LOCK_TIMEOUT = 5.0  # seconds to retry if another thread is mid-write, before giving up


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=DB_LOCK_TIMEOUT)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add added_by to a players table created before this column existed."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(players)")}
    if "added_by" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN added_by INTEGER")


def add(site, username, time_control, added_by):
    """Register a player. Returns False if that exact entry already exists."""
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO players (site, username, time_control, added_by) VALUES (?, ?, ?, ?)",
                (site, username, time_control, added_by),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def remove(username):
    """Delete every entry for a username. Returns how many rows went."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM players WHERE username = ?", (username,))
        return cur.rowcount


def owners(username):
    """Distinct added_by values recorded across every entry for username.

    None is included if any matching entry predates added_by tracking.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT added_by FROM players WHERE username = ?", (username,)
        ).fetchall()
    return {r["added_by"] for r in rows}


def set_added_by(username, discord_id):
    """Backfill added_by for every existing entry of username. Returns rows affected."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE players SET added_by = ? WHERE username = ?", (discord_id, username)
        )
        return cur.rowcount


def all_players():
    with connect() as conn:
        rows = conn.execute(
            "SELECT site, username, time_control FROM players ORDER BY username"
        ).fetchall()
    return [tuple(r) for r in rows]
