"""
Giveaway Tracker OAuth module.

The current Auto Join architecture does NOT use OAuth.

Auto Join means:

1. User enables /auto_join on in DM.
2. Detector finds a giveaway.
3. Bot DMs the user.
4. DM contains the server invite.
5. DM contains the giveaway message link.
6. User joins and enters manually.

There is intentionally:

- no OAuth polling
- no OAuth background task
- no authorization synchronization
- no access-token storage
- no guild-member OAuth endpoint
- no duplicate OAuth database

This module exists only so bot.py can have a clean,
stable module boundary.
"""


def setup(*args, **kwargs):

    print(
        "[OAUTH] OAuth system disabled."
    )

    print(
        "[OAUTH] Auto Join does not require OAuth."
    )


async def start(*args, **kwargs):

    return None


async def stop(*args, **kwargs):

    return None