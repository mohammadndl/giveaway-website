import discord
from discord import app_commands

import database


auto_join_group = app_commands.Group(
    name="auto_join",
    description="Control giveaway Auto Join."
)


@auto_join_group.command(
    name="on",
    description="Enable Auto Join."
)
async def auto_join_on(
    interaction: discord.Interaction
):

    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ You need to DM me and use "
            "`/auto_join on` there.",
            ephemeral=True
        )

        return

    database.set_auto_join(
        interaction.user.id,
        True
    )

    await interaction.response.send_message(
        "✅ **Auto Join is ON!**\n\n"
        "I'll notify you when I detect a giveaway "
        "and send you the server and giveaway link."
    )

    print(
        f"[AUTO JOIN] "
        f"Enabled for {interaction.user.id}"
    )


@auto_join_group.command(
    name="off",
    description="Disable Auto Join."
)
async def auto_join_off(
    interaction: discord.Interaction
):

    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ You need to DM me and use "
            "`/auto_join off` there.",
            ephemeral=True
        )

        return

    database.set_auto_join(
        interaction.user.id,
        False
    )

    await interaction.response.send_message(
        "🛑 **Auto Join is OFF.**"
    )

    print(
        f"[AUTO JOIN] "
        f"Disabled for {interaction.user.id}"
    )


def setup(bot):

    bot.tree.add_command(
        auto_join_group
    )