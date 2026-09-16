"""One-off: list registrations with no recorded owner.

Until set_owner.py is run for one of these, only an admin (see
ADMIN_USER_IDS in bot.py) can !remove it - the bot has no way to
verify who it belongs to.

Run:  python3 list_unowned.py
"""

import store

if __name__ == "__main__":
    usernames = store.unowned_usernames()
    if not usernames:
        print("Every registration has a recorded owner.")
    else:
        print(f"{len(usernames)} unowned:")
        for name in usernames:
            print(f"  {name}")
