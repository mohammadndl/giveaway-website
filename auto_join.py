import discord
from discord import app_commands

import database
import oauth_server

AUTO_JOIN = app_commands.Group(name="auto_join", description="Manage automatic giveaway joining.")


@AUTO_JOIN.command(name="on", description="Authorize Giveaway Tracker in your Discord User Apps.")
async def auto_join_on(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message("❌ Please DM me and run `/auto_join on` there.")
        return

    user_id = str(interaction.user.id)
    database.set_auto_join(user_id, False)
    url = oauth_server.create_authorization_url(user_id)

    view = discord.ui.View(timeout=300)
    view.add_item(discord.ui.Button(
        label="Add to My Apps",
        style=discord.ButtonStyle.link,
        url=url,
        emoji="➕",
    ))

    await interaction.response.send_message(
        "🔐 **Giveaway Tracker Authorization**\n\n"
        "Click **Add to My Apps** and authorize Giveaway Tracker.\n\n"
        "After Discord confirms the User App installation, Auto Join is enabled automatically.\n"
        "You do **not** need to run `/auto_join on` again.",
        view=view,
    )


@AUTO_JOIN.command(name="off", description="Disable Auto Join.")
async def auto_join_off(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message("❌ Please DM me and run `/auto_join off` there.")
        return

    database.set_auto_join(str(interaction.user.id), False)
    await interaction.response.send_message("🛑 **Auto Join disabled.**")


def setup(bot: discord.Client):
    bot.tree.add_command(AUTO_JOIN)
