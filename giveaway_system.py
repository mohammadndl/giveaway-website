import asyncio
import random
import re
import time

import discord
from discord import app_commands

import database


ACTIVE_GIVEAWAYS = {}


DURATION_PATTERN = re.compile(
    r"^(\d+)\s*([smhd])$",
    re.IGNORECASE
)


def parse_duration(
    value
):

    match = DURATION_PATTERN.fullmatch(
        value.strip()
    )

    if not match:
        return None

    amount = int(
        match.group(1)
    )

    unit = match.group(2).lower()

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return (
        amount
        * multipliers[unit]
    )


def format_remaining(
    end_time
):

    seconds = max(
        0,
        int(
            end_time
            - time.time()
        )
    )

    days, seconds = divmod(
        seconds,
        86400
    )

    hours, seconds = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        seconds,
        60
    )

    if days:
        return (
            f"{days}d "
            f"{hours}h "
            f"{minutes}m"
        )

    if hours:
        return (
            f"{hours}h "
            f"{minutes}m "
            f"{seconds}s"
        )

    if minutes:
        return (
            f"{minutes}m "
            f"{seconds}s"
        )

    return f"{seconds}s"


class Giveaway:

    def __init__(
        self,
        channel,
        host,
        prize,
        winner_count,
        end_time
    ):

        self.channel = channel
        self.host = host
        self.prize = prize
        self.winner_count = winner_count
        self.end_time = end_time

        self.message = None

        self.participants = set()

        self.ended = False


def make_embed(
    giveaway
):

    if giveaway.ended:

        time_text = "ENDED"

    else:

        time_text = format_remaining(
            giveaway.end_time
        )

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=(
            f"## 🎁 {giveaway.prize}\n\n"

            f"⏳ **Time Left:** "
            f"`{time_text}`\n\n"

            f"👥 **Participants:** "
            f"`{len(giveaway.participants)}`\n\n"

            f"🏆 **Winners:** "
            f"`{giveaway.winner_count}`"
        )
    )

    embed.set_footer(
        text="Good luck! 🍀"
    )

    return embed


class GiveawayView(
    discord.ui.View
):

    def __init__(
        self,
        giveaway,
        disabled=False
    ):

        super().__init__(
            timeout=None
        )

        self.giveaway = giveaway

        enter_button = discord.ui.Button(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            disabled=disabled
        )

        leave_button = discord.ui.Button(
            label="Leave",
            emoji="🚪",
            style=discord.ButtonStyle.secondary,
            disabled=disabled
        )

        enter_button.callback = (
            self.enter_callback
        )

        leave_button.callback = (
            self.leave_callback
        )

        self.add_item(
            enter_button
        )

        self.add_item(
            leave_button
        )

    async def enter_callback(
        self,
        interaction
    ):

        giveaway = self.giveaway

        if (
            giveaway.ended
            or time.time()
            >= giveaway.end_time
        ):

            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )

            return

        if (
            interaction.user.id
            in giveaway.participants
        ):

            await interaction.response.send_message(
                "ℹ️ You're already entered!",
                ephemeral=True
            )

            return

        giveaway.participants.add(
            interaction.user.id
        )

        if giveaway.message:

            database.add_participant(
                giveaway.message.id,
                interaction.user.id
            )

        await interaction.response.send_message(
            "🎉 **You're entered!**",
            ephemeral=True
        )

        await update_giveaway(
            giveaway
        )

    async def leave_callback(
        self,
        interaction
    ):

        giveaway = self.giveaway

        if (
            giveaway.ended
            or time.time()
            >= giveaway.end_time
        ):

            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )

            return

        if (
            interaction.user.id
            not in giveaway.participants
        ):

            await interaction.response.send_message(
                "ℹ️ You're not entered.",
                ephemeral=True
            )

            return

        giveaway.participants.remove(
            interaction.user.id
        )

        if giveaway.message:

            database.remove_participant(
                giveaway.message.id,
                interaction.user.id
            )

        await interaction.response.send_message(
            "🚪 **You left the giveaway.**",
            ephemeral=True
        )

        await update_giveaway(
            giveaway
        )


async def update_giveaway(
    giveaway
):

    if giveaway.message is None:
        return

    try:

        await giveaway.message.edit(
            embed=make_embed(
                giveaway
            ),
            view=GiveawayView(
                giveaway,
                giveaway.ended
            )
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):

        giveaway.message = None


async def finish_giveaway(
    giveaway
):

    if giveaway.ended:
        return

    giveaway.ended = True

    ACTIVE_GIVEAWAYS.pop(
        giveaway.channel.id,
        None
    )

    participants = list(
        giveaway.participants
    )

    if participants:

        winners = random.sample(
            participants,
            min(
                giveaway.winner_count,
                len(participants)
            )
        )

    else:

        winners = []

    await update_giveaway(
        giveaway
    )

    if not winners:

        content = (
            "🎉 **Giveaway Ended!**\n\n"
            f"🎁 **Prize:** "
            f"{giveaway.prize}\n\n"
            "😢 Nobody entered."
        )

    else:

        mentions = ", ".join(
            f"<@{user_id}>"
            for user_id in winners
        )

        content = (
            "🎉 **Giveaway Ended!**\n\n"
            f"🎁 **Prize:** "
            f"{giveaway.prize}\n\n"
            f"🏆 **Winner"
            f"{'s' if len(winners) != 1 else ''}:** "
            f"{mentions}"
        )

    try:

        result_message = (
            await giveaway.channel.send(
                content
            )
        )

        # DM every winner with the exact
        # giveaway message link.
        for user_id in winners:

            try:

                user = await giveaway.channel.guild.fetch_member(
                    user_id
                )

                await user.send(
                    "🏆 **YOU WON!**\n\n"
                    f"🎁 **Prize:** "
                    f"{giveaway.prize}\n\n"
                    f"🔗 **Giveaway message:**\n"
                    f"{giveaway.message.jump_url if giveaway.message else result_message.jump_url}"
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

    except (
        discord.Forbidden,
        discord.HTTPException
    ):
        pass


async def giveaway_loop(
    giveaway
):

    while not giveaway.ended:

        if time.time() >= giveaway.end_time:

            await finish_giveaway(
                giveaway
            )

            return

        await update_giveaway(
            giveaway
        )

        await asyncio.sleep(
            1
        )


@app_commands.command(
    name="giveaway",
    description="Create a giveaway."
)
@app_commands.describe(
    prize="The giveaway prize.",
    duration="Example: 30s, 10m, 2h, 1d.",
    winners="Number of winners."
)
async def giveaway_command(
    interaction: discord.Interaction,
    prize: str,
    duration: str,
    winners: app_commands.Range[
        int,
        1,
        100
    ]
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command must be used in a server.",
            ephemeral=True
        )

        return

    seconds = parse_duration(
        duration
    )

    if seconds is None:

        await interaction.response.send_message(
            "❌ Invalid duration.\n\n"
            "Use examples like:\n"
            "`30s`\n"
            "`10m`\n"
            "`2h`\n"
            "`1d`",
            ephemeral=True
        )

        return

    giveaway = Giveaway(
        channel=interaction.channel,
        host=interaction.user,
        prize=prize,
        winner_count=int(winners),
        end_time=time.time() + seconds
    )

    # Only acknowledge the interaction ONCE.
    await interaction.response.send_message(
        embed=make_embed(
            giveaway
        ),
        view=GiveawayView(
            giveaway
        )
    )

    try:

        giveaway.message = (
            await interaction.original_response()
        )

    except discord.HTTPException:

        return

    ACTIVE_GIVEAWAYS[
        interaction.channel.id
    ] = giveaway

    database.save_giveaway(
        message_id=giveaway.message.id,
        guild_id=interaction.guild.id,
        channel_id=interaction.channel.id,
        jump_url=giveaway.message.jump_url,
        prize=prize,
        winners=int(winners)
    )

    # IMPORTANT:
    # The bot itself is automatically entered
    # into its OWN giveaway.
    giveaway.participants.add(
        interaction.client.user.id
    )

    database.add_participant(
        giveaway.message.id,
        interaction.client.user.id
    )

    await update_giveaway(
        giveaway
    )

    asyncio.create_task(
        giveaway_loop(
            giveaway
        )
    )


def setup(bot):

    bot.tree.add_command(
        giveaway_command
    )