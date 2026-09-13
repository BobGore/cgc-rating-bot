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
    PRIMARY KEY (site, username, time_control)
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def add(site, username, time_control):
    """Register a player. Returns False if that exact entry already exists."""
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO players (site, username, time_control) VALUES (?, ?, ?)",
                (site, username, time_control),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def remove(username):
    """Delete every entry for a username. Returns how many rows went."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM players WHERE username = ?", (username,))
        return cur.rowcount


def all_players():
    with connect() as conn:
        rows = conn.execute(
            "SELECT site, username, time_control FROM players ORDER BY username"
        ).fetchall()
    return [tuple(r) for r in rows]
