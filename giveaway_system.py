import asyncio
import random
import re
import time

import discord
from discord import app_commands


DURATION_RE = re.compile(
    r"^\s*(\d+)\s*([smhd])\s*$",
    re.I
)

BOT = None
ACTIVE_GIVEAWAYS = {}


def setup(bot):

    global BOT

    BOT = bot

    bot.tree.add_command(
        giveaway
    )


def parse_duration(value):

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

    units = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return (
        amount
        * units[
            match.group(2).lower()
        ]
    )


def format_time(seconds):

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
            f"{days}d {hours}h {minutes}m"
        )

    if hours:
        return (
            f"{hours}h {minutes}m {seconds}s"
        )

    if minutes:
        return (
            f"{minutes}m {seconds}s"
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


def make_embed(g):

    if g.ended:

        remaining = "ENDED"
        title = "🎉 GIVEAWAY ENDED"

    else:

        remaining = format_time(
            g.end_at - time.time()
        )

        title = "🎉 GIVEAWAY"

    embed = discord.Embed(
        title=title,
        description=(
            f"## 🎁 {g.prize}\n\n"
            f"⏳ **Time Left:** `{remaining}`\n\n"
            f"👥 **Participants:** "
            f"`{len(g.participants)}`\n\n"
            f"🏆 **Winners:** "
            f"`{g.winners}`"
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

        enter.callback = self.enter
        leave.callback = self.leave

        self.add_item(enter)
        self.add_item(leave)

    async def enter(
        self,
        interaction
    ):

        g = self.giveaway

        if (
            g.ended
            or time.time() >= g.end_at
        ):

            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )

            return

        if interaction.user.id in g.participants:

            await interaction.response.send_message(
                "ℹ️ You are already entered.",
                ephemeral=True
            )

            return

        g.participants.add(
            interaction.user.id
        )

        await interaction.response.send_message(
            "🎉 You entered!",
            ephemeral=True
        )

        await update_giveaway(g)

    async def leave(
        self,
        interaction
    ):

        g = self.giveaway

        if (
            g.ended
            or time.time() >= g.end_at
        ):

            await interaction.response.send_message(
                "❌ This giveaway has ended.",
                ephemeral=True
            )

            return

        if interaction.user.id not in g.participants:

            await interaction.response.send_message(
                "ℹ️ You aren't entered.",
                ephemeral=True
            )

            return

        g.participants.remove(
            interaction.user.id
        )

        await interaction.response.send_message(
            "🚪 You left the giveaway.",
            ephemeral=True
        )

        await update_giveaway(g)


async def update_giveaway(g):

    if g.message is None:
        return

    try:

        await g.message.edit(
            embed=make_embed(g),
            view=GiveawayView(
                g,
                g.ended
            )
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):

        g.message = None


async def end_giveaway(g):

    if g.ended:
        return

    g.ended = True

    ACTIVE_GIVEAWAYS.pop(
        g.channel_id,
        None
    )

    participants = list(
        g.participants
    )

    random.shuffle(
        participants
    )

    winners = participants[
        :g.winners
    ]

    await update_giveaway(g)

    try:

        channel = await BOT.fetch_channel(
            g.channel_id
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
            f"🎁 Prize: **{g.prize}**\n\n"
            "😢 Nobody entered."
        )

    else:

        mentions = ", ".join(
            f"<@{user_id}>"
            for user_id in winners
        )

        text = (
            "🎉 **Giveaway Ended!**\n\n"
            f"🎁 Prize: **{g.prize}**\n\n"
            f"🏆 Winner"
            f"{'s' if len(winners) != 1 else ''}: "
            f"{mentions}"
        )

    try:
        await channel.send(text)
    except discord.HTTPException:
        pass


async def giveaway_loop(g):

    while not g.ended:

        if time.time() >= g.end_at:

            await end_giveaway(g)

            return

        await update_giveaway(g)

        await asyncio.sleep(1)


@app_commands.command(
    name="giveaway",
    description="Create a giveaway."
)
@app_commands.describe(
    prize="Giveaway prize.",
    duration="Example: 30s, 10m, 2h, 1d.",
    winners="Number of winners."
)
async def giveaway(
    interaction: discord.Interaction,
    prize: str,
    duration: str,
    winners: app_commands.Range[int, 1, 100]
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ Use this command in a server.",
            ephemeral=True
        )

        return

    seconds = parse_duration(
        duration
    )

    if seconds is None:

        await interaction.response.send_message(
            "❌ Invalid duration. "
            "Use `30s`, `10m`, `2h`, or `1d`.",
            ephemeral=True
        )

        return

    g = Giveaway(
        channel_id=interaction.channel_id,
        host_id=interaction.user.id,
        prize=prize,
        winners=int(winners),
        end_at=time.time() + seconds
    )

    # IMPORTANT:
    # Only acknowledge ONCE.
    await interaction.response.send_message(
        embed=make_embed(g),
        view=GiveawayView(g)
    )

    try:

        g.message = (
            await interaction.original_response()
        )

    except discord.HTTPException:

        return

    ACTIVE_GIVEAWAYS[
        interaction.channel_id
    ] = g

    asyncio.create_task(
        giveaway_loop(g)
    )