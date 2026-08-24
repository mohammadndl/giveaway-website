# bot.py
# Giveaway Tracker
# User App OAuth / Auto Join version

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
    raise RuntimeError("DISCORD_TOKEN is missing from the environment.")

TARGET_GIVEAWAY_BOT_ID = (
    os.getenv("TARGET_GIVEAWAY_BOT_ID", "").strip() or None
)


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

# Required so the giveaway detector can inspect messages.
intents.message_content = True


# =========================================================
# BOT
# =========================================================

class GiveawayTracker(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        database.init_db()

        print("[DATABASE] Database initialized.")

        # -------------------------------------------------
        # OAUTH SERVER
        # -------------------------------------------------

        oauth_server.init_oauth()

        print("[OAUTH] OAuth initialized.")

        # -------------------------------------------------
        # GIVEAWAY DETECTOR
        # -------------------------------------------------

        giveaway_detector.configure_target_bot(
            TARGET_GIVEAWAY_BOT_ID
        )

        # -------------------------------------------------
        # COMMANDS
        # -------------------------------------------------

        auto_join.setup(self)
        giveaway_system.setup(self)

        # -------------------------------------------------
        # OAUTH CALLBACK SERVER
        # -------------------------------------------------

        await oauth_server.start_oauth_server()

        # -------------------------------------------------
        # SYNC SLASH COMMANDS
        # -------------------------------------------------

        synced = await self.tree.sync()

        print(
            f"[BOT] Synced {len(synced)} slash command(s)."
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

    async def on_message(self, message: discord.Message):

        # -------------------------------------------------
        # GIVEAWAY DETECTION
        # -------------------------------------------------

        try:

            await giveaway_detector.process_message(
                message
            )

        except Exception as exc:

            print(
                "[DETECTOR] Error while processing "
                f"message {message.id}: {exc}"
            )

        # -------------------------------------------------
        # PREFIX COMMANDS
        # -------------------------------------------------

        await self.process_commands(message)


# =========================================================
# CREATE BOT
# =========================================================

bot = GiveawayTracker()


# =========================================================
# SLASH COMMAND ERROR HANDLER
# =========================================================

@bot.tree.error
async def slash_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):

    print(
        "[COMMAND ERROR]",
        type(error).__name__,
        error
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                "❌ Something went wrong.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Something went wrong.",
                ephemeral=True
            )

    except discord.HTTPException:
        pass


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("Starting Giveaway Tracker...")

    bot.run(TOKEN)