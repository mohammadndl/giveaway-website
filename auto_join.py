# auto_join.py

import discord
from discord import app_commands

import database
import oauth_server


AUTO_JOIN = app_commands.Group(
    name="auto_join",
    description="Manage Auto Join."
)


@AUTO_JOIN.command(
    name="on",
    description="Enable Auto Join."
)
async def auto_join_on(
    interaction: discord.Interaction
):

    # -----------------------------------------------------
    # DM ONLY
    # -----------------------------------------------------

    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ DM me and use `/auto_join on` there."
        )

        return

    user_id = str(
        interaction.user.id
    )

    # -----------------------------------------------------
    # ALREADY AUTHORIZED?
    # -----------------------------------------------------
    #
    # THIS IS THE IMPORTANT FIX.
    #
    # If the user has already authorized the User App,
    # NEVER create another OAuth URL.
    #
    # -----------------------------------------------------

    if database.is_user_authorized(
        user_id
    ):

        database.set_auto_join(
            user_id,
            True
        )

        await interaction.response.send_message(
            "✅ **Auto Join is now ON!**\n\n"
            "You have already authorized "
            "Giveaway Tracker in your Discord "
            "User Apps, so authentication is not "
            "required again."
        )

        print(
            f"[AUTO JOIN] Existing authorization "
            f"reused: {user_id}"
        )

        return

    # -----------------------------------------------------
    # FIRST AUTHORIZATION
    # -----------------------------------------------------

    url = (
        oauth_server.create_authorization_url(
            user_id
        )
    )

    view = discord.ui.View(
        timeout=300
    )

    button = discord.ui.Button(

        label="Add to My Apps",

        style=discord.ButtonStyle.link,

        url=url,

        emoji="🔐"
    )

    view.add_item(button)

    await interaction.response.send_message(

        "🔐 **Auto Join Setup**\n\n"

        "You only need to authorize "
        "Giveaway Tracker once.\n\n"

        "Click **Add to My Apps** below "
        "and authorize the app.\n\n"

        "After that, future `/auto_join on` "
        "commands will automatically turn "
        "Auto Join on without asking you "
        "to authenticate again.",

        view=view
    )


@AUTO_JOIN.command(
    name="off",
    description="Disable Auto Join."
)
async def auto_join_off(
    interaction: discord.Interaction
):

    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ DM me and use `/auto_join off` there."
        )

        return

    user_id = str(
        interaction.user.id
    )

    database.set_auto_join(
        user_id,
        False
    )

    await interaction.response.send_message(

        "🛑 **Auto Join is OFF.**\n\n"

        "Your Discord User App authorization "
        "is still saved.\n\n"

        "You can use `/auto_join on` again "
        "without authenticating."
    )


def setup(bot):

    bot.tree.add_command(
        AUTO_JOIN
    )