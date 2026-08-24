import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
import auto_join
import giveaway_system
import giveaway_detector
import oauth_server


load_dotenv()


TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN is missing from the environment."
    )


intents = discord.Intents.default()

# REQUIRED for reading giveaway messages.
intents.message_content = True


class GiveawayTracker(
    commands.Bot
):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        print(
            "[STARTUP] Initializing database..."
        )

        database.init_db()

        print(
            "[STARTUP] Registering Auto Join..."
        )

        auto_join.setup(
            self
        )

        print(
            "[STARTUP] Registering Giveaway..."
        )

        giveaway_system.setup(
            self
        )

        print(
            "[STARTUP] Initializing OAuth module..."
        )

        oauth_server.setup(
            self
        )

        print(
            "[STARTUP] Syncing slash commands..."
        )

        synced = await self.tree.sync()

        print(
            f"[STARTUP] "
            f"Synced {len(synced)} commands."
        )

    async def on_ready(
        self
    ):

        print()
        print(
            "=" * 60
        )

        print(
            "🚀 GIVEAWAY TRACKER ONLINE"
        )

        print(
            f"Bot: {self.user}"
        )

        print(
            f"Bot ID: {self.user.id}"
        )

        print(
            f"Servers: {len(self.guilds)}"
        )

        print(
            "=" * 60
        )

    async def on_message(
        self,
        message: discord.Message
    ):

        # Detect giveaways from other bots.
        try:

            await giveaway_detector.process_message(
                message
            )

        except Exception as error:

            print(
                "[DETECTOR ERROR]"
            )

            print(
                f"{type(error).__name__}: "
                f"{error}"
            )

        # Keep prefix-command support.
        try:

            await self.process_commands(
                message
            )

        except Exception as error:

            print(
                "[COMMAND ERROR]"
            )

            print(
                f"{type(error).__name__}: "
                f"{error}"
            )

    async def on_command_error(
        self,
        context,
        error
    ):

        print(
            "[PREFIX COMMAND ERROR]"
        )

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )


bot = GiveawayTracker()


if __name__ == "__main__":

    print(
        "[STARTUP] Starting bot..."
    )

    bot.run(
        TOKEN
    )