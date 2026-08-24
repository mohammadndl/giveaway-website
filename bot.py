import os,discord
from discord.ext import commands
from dotenv import load_dotenv
import database,oauth_server,auto_join,giveaway_system,giveaway_detector
load_dotenv();TOKEN=os.getenv('DISCORD_TOKEN','').strip()
if not TOKEN:raise RuntimeError('DISCORD_TOKEN is missing')
intents=discord.Intents.default();intents.message_content=True
class Bot(commands.Bot):
 def __init__(self):super().__init__(command_prefix='!',intents=intents,help_command=None)
 async def setup_hook(self):
  database.init_db();oauth_server.init_oauth();auto_join.setup(self);giveaway_system.setup(self);giveaway_detector.configure_target_bot(os.getenv('TARGET_GIVEAWAY_BOT_ID'));await oauth_server.start_oauth_server();print(f'[BOT] Synced {len(await self.tree.sync())} command(s)')
 async def on_ready(self):print(f'🚀 GIVEAWAY TRACKER ONLINE | {self.user} | Servers: {len(self.guilds)}')
 async def on_message(self,m):
  try:await giveaway_detector.process_message(m)
  except Exception as e:print(f'[DETECTOR] {e}')
  await self.process_commands(m)
bot=Bot()
if __name__=='__main__':bot.run(TOKEN)
