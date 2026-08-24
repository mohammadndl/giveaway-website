import discord
from discord import app_commands
import database

GROUP=app_commands.Group(name='auto_join',description='Control giveaway notifications.')

@GROUP.command(name='on',description='Turn giveaway Auto Join notifications on.')
async def on(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message('❌ DM me and use `/auto_join on` there.',ephemeral=True); return
    database.set_auto_join(interaction.user.id,True)
    await interaction.response.send_message('✅ **Auto Join is ON!**\n\nI will DM you when I detect a giveaway, with the server invite and giveaway message link when available.\n\nYou must join the server and press **Enter Giveaway** yourself.')
    print(f'[AUTO JOIN] ON: {interaction.user.id}')

@GROUP.command(name='off',description='Turn giveaway Auto Join notifications off.')
async def off(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message('❌ DM me and use `/auto_join off` there.',ephemeral=True); return
    database.set_auto_join(interaction.user.id,False)
    await interaction.response.send_message('🛑 **Auto Join is OFF.**')
    print(f'[AUTO JOIN] OFF: {interaction.user.id}')

def setup(bot): bot.tree.add_command(GROUP)
