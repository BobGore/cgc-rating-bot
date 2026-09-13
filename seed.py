"""One-off: bulk-load the roster from a CSV.

The old bot stored only (username, site, time control), all of which was
visible in its final !rating dump, so a restore is just a list of those.

roster.csv is deliberately not in version control: it is a list of real
people's accounts, and this repo is public. Copy roster.csv.example and
fill it in, or drop your own export in place.

Run:  python3 seed.py
"""

import csv
from pathlib import Path

import store

ROSTER_PATH = Path(__file__).with_name("roster.csv")

if __name__ == "__main__":
    if not ROSTER_PATH.exists():
        raise SystemExit(f"{ROSTER_PATH} not found — copy roster.csv.example and fill it in")

    with ROSTER_PATH.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    added = sum(store.add(r["site"], r["username"], r["time_control"]) for r in rows)
    print(f"{added} added, {len(rows) - added} already present")
