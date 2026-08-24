import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
import giveaway_system
import giveaway_detector
import auto_join

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

intents = discord.Intents.default()

# Required for reading giveaway messages.
intents.message_content = True

# Used for finding users who enabled Auto Join.
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():

    database.init_db()

    print("=" * 60)
    print("🎉 GIVEAWAY TRACKER ONLINE")
    print(f"Bot: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Servers: {len(bot.guilds)}")

    for guild in bot.guilds:
        print(
            f"  • {guild.name} "
            f"({guild.id})"
        )

    print("=" * 60)

    try:
        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands."
        )

    except Exception as e:

        print(
            f"[SYNC ERROR] "
            f"{type(e).__name__}: {e}"
        )


@bot.event
async def on_message(
    message: discord.Message
):

    try:

        await giveaway_detector.process_message(
            message
        )

    except Exception as e:

        print(
            f"[DETECTOR ERROR] "
            f"{type(e).__name__}: {e}"
        )

    await bot.process_commands(
        message
    )


async def main():

    database.init_db()

    auto_join.setup(bot)

    giveaway_system.setup(bot)

    giveaway_detector.setup(bot)

    await bot.start(
        TOKEN
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )