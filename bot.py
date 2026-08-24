import os,asyncio,discord
from discord.ext import commands
from dotenv import load_dotenv
import database,auto_join,giveaway_detector

load_dotenv()
TOKEN=os.getenv('DISCORD_TOKEN','').strip()
if not TOKEN:raise RuntimeError('DISCORD_TOKEN is missing.')
intents=discord.Intents.default(); intents.message_content=True; intents.members=True
bot=commands.Bot(command_prefix='!',intents=intents)

@bot.event
async def on_ready():
    print('='*60); print('🎉 GIVEAWAY TRACKER ONLINE'); print(f'Bot: {bot.user} ({bot.user.id})'); print(f'Servers: {len(bot.guilds)}'); print('='*60)
    try: print(f'✅ Synced {len(await bot.tree.sync())} slash commands.')
    except Exception as e: print(f'[SYNC ERROR] {type(e).__name__}: {e}')

@bot.event
async def on_message(message):
    try:await giveaway_detector.process_message(message)
    except Exception as e:print(f'[DETECTOR ERROR] {type(e).__name__}: {e}')
    await bot.process_commands(message)

async def main():
    database.init_db(); auto_join.setup(bot); giveaway_detector.setup(bot); await bot.start(TOKEN)

if __name__=='__main__':asyncio.run(main())
