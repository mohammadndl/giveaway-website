import discord
from discord import app_commands
import database,oauth_server
AUTO_JOIN=app_commands.Group(name='auto_join',description='Manage Auto Join.')
@AUTO_JOIN.command(name='on',description='Enable Auto Join.')
async def on(interaction):
 if interaction.guild is not None:return await interaction.response.send_message('❌ DM me and run `/auto_join on` there.')
 uid=str(interaction.user.id)
 if database.is_user_authorized(uid):
  database.set_auto_join(uid,True); return await interaction.response.send_message('✅ **Auto Join is now ON.** Your User App authorization is already saved, so you do not need to authenticate again.')
 view=discord.ui.View(timeout=300); view.add_item(discord.ui.Button(label='Add to My Apps',style=discord.ButtonStyle.link,url=oauth_server.create_authorization_url(uid),emoji='🔐'))
 await interaction.response.send_message('🔐 **Auto Join Authentication**\n\nYou only need to do this once. Click **Add to My Apps** and authorize Giveaway Tracker. After authorization Auto Join turns ON automatically.',view=view)
@AUTO_JOIN.command(name='off',description='Disable Auto Join.')
async def off(interaction):
 if interaction.guild is not None:return await interaction.response.send_message('❌ DM me and run `/auto_join off` there.')
 database.set_auto_join(str(interaction.user.id),False); await interaction.response.send_message('🛑 **Auto Join disabled.** Your authorization remains saved, so `/auto_join on` will not ask again.')
def setup(bot):bot.tree.add_command(AUTO_JOIN)
