"""
OAuth is intentionally disabled.

This version does NOT use:

- OAuth user tokens
- user-account automation
- self-bots
- user impersonation

The bot account handles its own giveaway entries.
"""

def init_oauth():
    print(
        "[OAUTH] Disabled."
    )


async def start_oauth_server():
    print(
        "[OAUTH] Disabled."
    )