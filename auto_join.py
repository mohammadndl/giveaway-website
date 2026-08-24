import discord
from discord import app_commands

import database


AUTO_JOIN_GROUP = app_commands.Group(
    name="auto_join",
    description="Giveaway notification settings."
)


@AUTO_JOIN_GROUP.command(
    name="on",
    description="Enable automatic giveaway notifications."
)
async def auto_join_on(
    interaction: discord.Interaction
):
    if interaction.guild is not None:
        await interaction.response.send_message(
            "❌ This command only works in DMs.\n"
            "DM me and use `/auto_join on`.",
            ephemeral=True
        )
        return

    database.set_auto_join(
        interaction.user.id,
        True
    )

    await interaction.response.send_message(
        "✅ **Auto Join is now enabled!**\n\n"
        "When I detect a giveaway, I will DM you:\n"
        "🔗 A server invite\n"
        "🎉 The giveaway message\n\n"
        "You still need to enter the giveaway yourself."
    )

    print(
        f"[AUTO JOIN] ENABLED "
        f"user={interaction.user.id}"
    )


@AUTO_JOIN_GROUP.command(
    name="off",
    description="Disable automatic giveaway notifications."
)
async def auto_join_off(
    interaction: discord.Interaction
):
    if interaction.guild is not None:
        await interaction.response.send_message(
            "❌ This command only works in DMs.\n"
            "DM me and use `/auto_join off`.",
            ephemeral=True
        )
        return

    database.set_auto_join(
        interaction.user.id,
        False
    )

    await interaction.response.send_message(
        "🛑 **Auto Join is disabled.**"
    )

    print(
        f"[AUTO JOIN] DISABLED "
        f"user={interaction.user.id}"
    )


def setup(bot):
    bot.tree.add_command(
        AUTO_JOIN_GROUP
    )

    print(
        "[AUTO JOIN] Commands registered."
    )


async def notify_users(
    bot,
    message: discord.Message,
    prize: str,
    winner_count,
    invite_url: str | None
):
    users = database.get_auto_join_users()

    if not users:
        print(
            "[AUTO JOIN] "
            "No enabled users."
        )
        return

    for user_id in users:

        try:
            user = await bot.fetch_user(
                user_id
            )

        except discord.NotFound:
            print(
                f"[AUTO JOIN] "
                f"User {user_id} not found."
            )
            continue

        except discord.HTTPException as error:
            print(
                f"[AUTO JOIN] "
                f"Could not fetch {user_id}: "
                f"HTTP {error.status}"
            )
            continue

        server_name = (
            message.guild.name
            if message.guild
            else "Unknown Server"
        )

        embed = discord.Embed(
            title="🎉 GIVEAWAY DETECTED!",
            description=(
                f"🎁 **Prize:** {prize}\n\n"
                f"🏆 **Winners:** "
                f"`{winner_count or 'Unknown'}`\n\n"
                f"📍 **Server:** "
                f"{server_name}\n\n"
                "Join the server and enter "
                "the giveaway!"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Giveaway Tracker"
        )

        view = discord.ui.View(
            timeout=None
        )

        if invite_url:
            view.add_item(
                discord.ui.Button(
                    label="Join Server",
                    emoji="🔗",
                    style=discord.ButtonStyle.link,
                    url=invite_url
                )
            )

        view.add_item(
            discord.ui.Button(
                label="Open Giveaway",
                emoji="🎉",
                style=discord.ButtonStyle.link,
                url=message.jump_url
            )
        )

        try:
            await user.send(
                embed=embed,
                view=view
            )

            print(
                f"[AUTO JOIN] "
                f"Giveaway DM sent to {user_id}"
            )

        except discord.Forbidden:
            print(
                f"[AUTO JOIN] "
                f"Cannot DM {user_id}."
            )

        except discord.HTTPException as error:
            print(
                f"[AUTO JOIN] "
                f"DM HTTP {error.status} "
                f"for {user_id}"
            )