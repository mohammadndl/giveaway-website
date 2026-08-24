import discord
from discord import app_commands

import database


auto_join_group = app_commands.Group(
    name="auto_join",
    description="Control Giveaway Tracker Auto Join."
)


@auto_join_group.command(
    name="on",
    description="Turn Auto Join on."
)
async def auto_join_on(
    interaction: discord.Interaction
):

    # Auto Join is a DM-only command.
    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ You must DM me and use "
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
        "When I detect a giveaway, I'll DM you "
        "with the server invite and the direct "
        "giveaway message."
    )

    print(
        f"[AUTO JOIN] ON: "
        f"{interaction.user} "
        f"({interaction.user.id})"
    )


@auto_join_group.command(
    name="off",
    description="Turn Auto Join off."
)
async def auto_join_off(
    interaction: discord.Interaction
):

    if interaction.guild is not None:

        await interaction.response.send_message(
            "❌ You must DM me and use "
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
        f"[AUTO JOIN] OFF: "
        f"{interaction.user} "
        f"({interaction.user.id})"
    )


def setup(bot):

    bot.tree.add_command(
        auto_join_group
    )