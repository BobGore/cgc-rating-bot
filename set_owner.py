"""One-off: record who a registration belongs to, for entries added before
ownership was tracked.

Until this is run for a given username, only an admin (see ADMIN_USER_IDS in
bot.py) can !remove it - the bot has no way to verify who it belongs to.

Run:  python3 set_owner.py <username> <discord_id>
"""

import sys

import store

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 set_owner.py <username> <discord_id>")

    username, discord_id = sys.argv[1], int(sys.argv[2])
    updated = store.set_added_by(username, discord_id)
    if updated:
        print(f"{updated} row(s) updated for '{username}'")
    else:
        print(f"'{username}' isn't on the list")
