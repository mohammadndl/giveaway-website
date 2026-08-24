import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
import auto_join
import oauth_server
import giveaway_system
import giveaway_detector

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

intents = discord.Intents.default()
intents.message_content = True


class GiveawayTracker(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        database.init_db()
        oauth_server.init_oauth()
        giveaway_detector.configure_target_bot(os.getenv("TARGET_GIVEAWAY_BOT_ID"))
        auto_join.setup(self)
        giveaway_system.setup(self)
        await oauth_server.start_oauth_server()
        synced = await self.tree.sync()
        print(f"[BOT] Synced {len(synced)} slash command(s).")

    async def on_ready(self):
        print("=" * 60)
        print("🚀 GIVEAWAY TRACKER IS ONLINE")
        print(f"Bot: {self.user} ({self.user.id})")
        print(f"Servers: {len(self.guilds)}")
        for guild in self.guilds:
            print(f"  - {guild.name} ({guild.id})")
        print("=" * 60)

    async def on_message(self, message: discord.Message):
        try:
            await giveaway_detector.process_message(message)
        except Exception as exc:
            print(f"[DETECTOR] Error on message {message.id}: {exc}")
        await self.process_commands(message)


bot = GiveawayTracker()


@bot.tree.error
async def app_command_error(interaction, error):
    print(f"[COMMAND ERROR] {type(error).__name__}: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Something went wrong.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Something went wrong.", ephemeral=True)
    except discord.HTTPException:
        pass


if __name__ == "__main__":
    bot.run(TOKEN)
