# bot.py

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
import oauth_server
import auto_join
import giveaway_system
import giveaway_detector


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")


TARGET_GIVEAWAY_BOT_ID = (
    os.getenv("TARGET_GIVEAWAY_BOT_ID", "").strip()
    or None
)


intents = discord.Intents.default()
intents.message_content = True


class GiveawayTracker(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):

        print("[STARTUP] Initializing database...")
        database.init_db()

        print("[STARTUP] Initializing OAuth...")
        oauth_server.init_oauth()

        print("[STARTUP] Initializing giveaway detector...")

        giveaway_detector.configure_target_bot(
            TARGET_GIVEAWAY_BOT_ID
        )

        print("[STARTUP] Loading Auto Join...")
        auto_join.setup(self)

        print("[STARTUP] Loading Giveaway System...")
        giveaway_system.setup(self)

        print("[STARTUP] Starting OAuth server...")
        await oauth_server.start_oauth_server()

        print("[STARTUP] Syncing slash commands...")

        synced = await self.tree.sync()

        print(
            f"[STARTUP] Synced {len(synced)} commands."
        )

    async def on_ready(self):

        print()
        print("=" * 60)
        print("🚀 GIVEAWAY TRACKER IS ONLINE")
        print("=" * 60)

        print(f"Bot: {self.user}")
        print(f"Bot ID: {self.user.id}")
        print(f"Servers: {len(self.guilds)}")

        for guild in self.guilds:
            print(
                f"  └─ {guild.name} "
                f"({guild.id})"
            )

        print("=" * 60)
        print()

    async def on_message(
        self,
        message: discord.Message
    ):

        try:

            await giveaway_detector.process_message(
                message
            )

        except Exception as exc:

            print(
                "[DETECTOR ERROR]"
            )

            print(
                f"Message: {message.id}"
            )

            print(
                f"Error: {type(exc).__name__}: {exc}"
            )

        await self.process_commands(message)


bot = GiveawayTracker()


@bot.tree.error
async def slash_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):

    print()
    print("=" * 60)
    print("❌ SLASH COMMAND ERROR")
    print("=" * 60)

    print(
        f"Type: {type(error).__name__}"
    )

    print(
        f"Error: {repr(error)}"
    )

    print("=" * 60)
    print()

    try:

        message = (
            "❌ Something went wrong.\n"
            f"`{type(error).__name__}`"
        )

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except discord.HTTPException as exc:

        print(
            f"[ERROR HANDLER] {exc}"
        )


if __name__ == "__main__":

    bot.run(TOKEN)