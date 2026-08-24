import os
import asyncio

import discord
from discord.ext import commands
from aiohttp import web
from dotenv import load_dotenv

import database
import giveaway_system
import giveaway_detector
import auto_join


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from Render Environment Variables."
    )


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

# Needed so the detector can read giveaway messages.
intents.message_content = True

# Needed to find users who enabled Auto Join.
intents.members = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(request):
    return web.Response(
        text="Giveaway Tracker is online!"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    # Render provides PORT automatically.
    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(
        f"🌐 Render HTTP server listening on port {port}"
    )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("=" * 60)
    print("🎉 GIVEAWAY TRACKER ONLINE")
    print("=" * 60)

    print(
        f"Bot: {bot.user}"
    )

    print(
        f"Bot ID: {bot.user.id}"
    )

    print(
        f"Servers: {len(bot.guilds)}"
    )

    for guild in bot.guilds:

        print(
            f"  • {guild.name} "
            f"({guild.id})"
        )

    print("=" * 60)

    # Sync slash commands.
    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands."
        )

    except Exception as error:

        print(
            "[SYNC ERROR]"
        )

        print(
            f"{type(error).__name__}: {error}"
        )


# =========================================================
# MESSAGE DETECTION
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # Giveaway detector handles:
    #
    # - giveaway detection
    # - giveaway links
    # - participant/winner information
    # - winner notifications
    #
    # It also ignores normal user messages.

    try:

        await giveaway_detector.process_message(
            message
        )

    except Exception as error:

        print(
            "[DETECTOR ERROR]"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

    # Keep normal Discord.py command processing.
    await bot.process_commands(
        message
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    # Initialize ONE SQLite database.
    database.init_db()

    print(
        "✅ Database initialized."
    )

    # Register Auto Join commands.
    auto_join.setup(
        bot
    )

    # Register Giveaway command.
    giveaway_system.setup(
        bot
    )

    # Initialize detector.
    giveaway_detector.setup(
        bot
    )

    print(
        "✅ Giveaway system loaded."
    )

    print(
        "✅ Auto Join loaded."
    )

    print(
        "✅ Giveaway detector loaded."
    )

    # Start Render HTTP server.
    await start_web_server()

    # Start Discord bot.
    await bot.start(
        TOKEN
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped."
        )

    except Exception as error:

        print(
            "=" * 60
        )

        print(
            "❌ BOT CRASHED"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        print(
            "=" * 60

        )

        raise