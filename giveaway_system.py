# giveaway_system.py

import asyncio
import random
import re
import time

import discord
from discord import app_commands


BOT = None

ACTIVE_GIVEAWAYS = {}

DURATION_RE = re.compile(
    r"^\s*(\d+)\s*([smhd])\s*$",
    re.I
)


def setup(bot):

    global BOT

    BOT = bot

    bot.tree.add_command(
        giveaway
    )


def parse_duration(
    value: str
):

    match = DURATION_RE.fullmatch(
        value
    )

    if not match:

        return None

    amount = int(
        match.group(1)
    )

    if amount <= 0:

        return None

    unit = (
        match.group(2)
        .lower()
    )

    multipliers = {

        "s": 1,

        "m": 60,

        "h": 3600,

        "d": 86400,
    }

    return (
        amount
        * multipliers[unit]
    )


def format_time(
    seconds
):

    seconds = max(
        0,
        int(seconds)
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
        channel_id,
        host_id,
        prize,
        winners,
        end_at
    ):

        self.channel_id = channel_id

        self.host_id = host_id

        self.prize = prize

        self.winners = winners

        self.end_at = end_at

        self.message = None

        self.participants = set()

        self.ended = False


def make_embed(
    giveaway: Giveaway
):

    if giveaway.ended:

        title = (
            "🎉 GIVEAWAY ENDED"
        )

        time_text = "ENDED"

    else:

        title = (
            "🎉 GIVEAWAY"
        )

        time_text = format_time(
            giveaway.end_at
            - time.time()
        )

    embed = discord.Embed(
        title=title,

        description=(

            f"## 🎁 "
            f"{giveaway.prize}\n\n"

            f"⏳ **Time Left:** "
            f"`{time_text}`\n\n"

            f"👥 **Participants:** "
            f"`{len(giveaway.participants)}`\n\n"

            f"🏆 **Winners:** "
            f"`{giveaway.winners}`"
        )
    )

    embed.set_footer(
        text=(
            "Hosted by "
            f"{giveaway.host_id}"
        )
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

        enter = discord.ui.Button(
            label="Enter Giveaway",
            style=discord.ButtonStyle.success,
            emoji="🎉",
            disabled=disabled
        )

        leave = discord.ui.Button(
            label="Leave",
            style=discord.ButtonStyle.secondary,
            emoji="🚪",
            disabled=disabled
        )

        enter.callback = (
            self.enter_callback
        )

        leave.callback = (
            self.leave_callback
        )

        self.add_item(
            enter
        )

        self.add_item(
            leave
        )

    async def enter_callback(
        self,
        interaction
    ):

        giveaway = (
            self.giveaway
        )

        if (
            giveaway.ended
            or
            time.time()
            >= giveaway.end_at
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
                "ℹ️ You are already entered.",
                ephemeral=True
            )

            return

        giveaway.participants.add(
            interaction.user.id
        )

        await interaction.response.send_message(
            "🎉 You entered the giveaway!",
            ephemeral=True
        )

        await update_giveaway(
            giveaway
        )

    async def leave_callback(
        self,
        interaction
    ):

        giveaway = (
            self.giveaway
        )

        if (
            giveaway.ended
            or
            time.time()
            >= giveaway.end_at
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
                "ℹ️ You are not entered.",
                ephemeral=True
            )

            return

        giveaway.participants.remove(
            interaction.user.id
        )

        await interaction.response.send_message(
            "🚪 You left the giveaway.",
            ephemeral=True
        )

        await update_giveaway(
            giveaway
        )


async def update_giveaway(
    giveaway
):

    if not giveaway.message:

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


async def end_giveaway(
    giveaway
):

    if giveaway.ended:

        return

    giveaway.ended = True

    ACTIVE_GIVEAWAYS.pop(
        giveaway.channel_id,
        None
    )

    winners = list(
        giveaway.participants
    )

    random.shuffle(
        winners
    )

    winners = winners[
        :giveaway.winners
    ]

    await update_giveaway(
        giveaway
    )

    try:

        channel = (
            await BOT.fetch_channel(
                giveaway.channel_id
            )
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):

        return

    if not winners:

        text = (

            "🎉 **Giveaway Ended!**\n\n"

            f"🎁 Prize: "
            f"**{giveaway.prize}**\n\n"

            "😢 No one entered."
        )

    else:

        mentions = ", ".join(
            f"<@{user_id}>"
            for user_id in winners
        )

        text = (

            "🎉 **Giveaway Ended!**\n\n"

            f"🎁 Prize: "
            f"**{giveaway.prize}**\n\n"

            f"🏆 Winner"
            f"{'s' if len(winners) != 1 else ''}: "
            f"{mentions}"
        )

    try:

        await channel.send(
            text
        )

    except discord.HTTPException:
        pass


async def giveaway_loop(
    giveaway
):

    while not giveaway.ended:

        if (
            time.time()
            >= giveaway.end_at
        ):

            await end_giveaway(
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

    prize="Giveaway prize.",

    duration=(
        "Duration: 30s, 10m, "
        "2h, 1d."
    ),

    winners=(
        "Number of winners."
    )
)
async def giveaway(
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
            "❌ Invalid duration.\n"
            "Use `30s`, `10m`, `2h`, or `1d`.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    giveaway_data = Giveaway(

        channel_id=interaction.channel_id,

        host_id=interaction.user.id,

        prize=prize,

        winners=int(winners),

        end_at=(
            time.time()
            + seconds
        )
    )

    try:

        message = (
            await interaction.followup.send(

                embed=make_embed(
                    giveaway_data
                ),

                view=GiveawayView(
                    giveaway_data
                ),

                wait=True
            )
        )

    except discord.HTTPException:

        return

    giveaway_data.message = (
        message
    )

    ACTIVE_GIVEAWAYS[
        interaction.channel_id
    ] = giveaway_data

    asyncio.create_task(
        giveaway_loop(
            giveaway_data
        )
    )