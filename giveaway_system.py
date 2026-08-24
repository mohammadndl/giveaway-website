import asyncio
import random
import re
import time

import discord
from discord import app_commands

import database


ACTIVE_GIVEAWAYS = {}


def parse_duration(
    value: str
):

    match = re.fullmatch(
        r"\s*(\d+)\s*([smhd])\s*",
        value,
        re.IGNORECASE
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

    return amount * multipliers[unit]


def format_time(
    timestamp: float
):

    remaining = max(
        0,
        int(timestamp - time.time())
    )

    days, remaining = divmod(
        remaining,
        86400
    )

    hours, remaining = divmod(
        remaining,
        3600
    )

    minutes, seconds = divmod(
        remaining,
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


class GiveawayState:

    def __init__(
        self,
        channel: discord.TextChannel,
        prize: str,
        winner_count: int,
        end_time: float
    ):

        self.channel = channel
        self.prize = prize
        self.winner_count = winner_count
        self.end_time = end_time

        self.message = None

        self.participants = set()

        self.ended = False

        self.lock = asyncio.Lock()


def make_embed(
    giveaway: GiveawayState
):

    if giveaway.ended:
        remaining = "ENDED"

    else:
        remaining = format_time(
            giveaway.end_time
        )

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        color=discord.Color.blurple()
    )

    embed.description = (
        f"## 🎁 {giveaway.prize}\n\n"
        f"⏳ **Time Left:** "
        f"`{remaining}`\n\n"
        f"👥 **Participants:** "
        f"`{len(giveaway.participants)}`\n\n"
        f"🏆 **Winners:** "
        f"`{giveaway.winner_count}`"
    )

    embed.set_footer(
        text="Giveaway Tracker"
    )

    return embed


class GiveawayView(
    discord.ui.View
):

    def __init__(
        self,
        giveaway: GiveawayState
    ):

        super().__init__(
            timeout=None
        )

        self.giveaway = giveaway

        enter = discord.ui.Button(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            disabled=giveaway.ended
        )

        leave = discord.ui.Button(
            label="Leave",
            emoji="🚪",
            style=discord.ButtonStyle.secondary,
            disabled=giveaway.ended
        )

        enter.callback = self.enter
        leave.callback = self.leave

        self.add_item(enter)
        self.add_item(leave)

    async def enter(
        self,
        interaction: discord.Interaction
    ):

        giveaway = self.giveaway

        async with giveaway.lock:

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
                    "ℹ️ You are already entered.",
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
            "🎉 **You entered the giveaway!**",
            ephemeral=True
        )

        await refresh_message(
            giveaway
        )

    async def leave(
        self,
        interaction: discord.Interaction
    ):

        giveaway = self.giveaway

        async with giveaway.lock:

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

            if giveaway.message:

                database.remove_participant(
                    giveaway.message.id,
                    interaction.user.id
                )

        await interaction.response.send_message(
            "🚪 **You left the giveaway.**",
            ephemeral=True
        )

        await refresh_message(
            giveaway
        )


async def refresh_message(
    giveaway: GiveawayState
):

    if giveaway.message is None:
        return

    try:

        await giveaway.message.edit(
            embed=make_embed(
                giveaway
            ),
            view=GiveawayView(
                giveaway
            )
        )

    except discord.NotFound:

        giveaway.message = None

    except discord.Forbidden:

        giveaway.message = None

    except discord.HTTPException as error:

        print(
            f"[GIVEAWAY] Edit error "
            f"HTTP {error.status}"
        )


async def finish_giveaway(
    giveaway: GiveawayState
):

    async with giveaway.lock:

        if giveaway.ended:
            return

        giveaway.ended = True

        participants = list(
            giveaway.participants
        )

    ACTIVE_GIVEAWAYS.pop(
        giveaway.channel.id,
        None
    )

    winners = random.sample(
        participants,
        min(
            giveaway.winner_count,
            len(participants)
        )
    ) if participants else []

    await refresh_message(
        giveaway
    )

    if not winners:

        result_text = (
            "🎉 **Giveaway Ended!**\n\n"
            f"🎁 **Prize:** "
            f"{giveaway.prize}\n\n"
            "😢 **Nobody entered.**"
        )

    else:

        mentions = ", ".join(
            f"<@{user_id}>"
            for user_id in winners
        )

        result_text = (
            "🎉 **Giveaway Ended!**\n\n"
            f"🎁 **Prize:** "
            f"{giveaway.prize}\n\n"
            f"🏆 **Winner"
            f"{'s' if len(winners) != 1 else ''}:** "
            f"{mentions}"
        )

    result_message = None

    try:

        result_message = (
            await giveaway.channel.send(
                result_text
            )
        )

    except discord.HTTPException as error:

        print(
            f"[GIVEAWAY] "
            f"Winner announcement failed: "
            f"HTTP {error.status}"
        )

    winning_link = None

    if result_message:

        winning_link = (
            result_message.jump_url
        )

    elif giveaway.message:

        winning_link = (
            giveaway.message.jump_url
        )

    for user_id in winners:

        try:

            user = (
                await giveaway.channel.guild
                .fetch_member(user_id)
            )

            await user.send(
                "🏆 **YOU WON!**\n\n"
                f"🎁 **Prize:** "
                f"{giveaway.prize}\n\n"
                "🎉 Congratulations!\n\n"
                "🔗 **Winning message:**\n"
                f"{winning_link or 'Unavailable'}"
            )

        except discord.NotFound:

            print(
                f"[GIVEAWAY] "
                f"Winner {user_id} "
                "could not be found."
            )

        except discord.Forbidden:

            print(
                f"[GIVEAWAY] "
                f"Cannot DM winner "
                f"{user_id}."
            )

        except discord.HTTPException as error:

            print(
                f"[GIVEAWAY] "
                f"Winner DM HTTP "
                f"{error.status}"
            )

    print(
        f"[GIVEAWAY] Finished "
        f"prize={giveaway.prize} "
        f"participants={len(participants)} "
        f"winners={len(winners)}"
    )


async def giveaway_loop(
    giveaway: GiveawayState
):

    while not giveaway.ended:

        if time.time() >= giveaway.end_time:

            await finish_giveaway(
                giveaway
            )

            return

        await refresh_message(
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
    winners: app_commands.Range[int, 1, 100]
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )

        return

    seconds = parse_duration(
        duration
    )

    if seconds is None:

        await interaction.response.send_message(
            "❌ Invalid duration.\n\n"
            "Examples:\n"
            "`30s`\n"
            "`10m`\n"
            "`2h`\n"
            "`1d`",
            ephemeral=True
        )

        return

    if seconds <= 0:

        await interaction.response.send_message(
            "❌ Duration must be greater than zero.",
            ephemeral=True
        )

        return

    giveaway = GiveawayState(
        channel=interaction.channel,
        prize=prize,
        winner_count=int(winners),
        end_time=time.time() + seconds
    )

    # IMPORTANT:
    # Respond exactly once.
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

    except discord.HTTPException as error:

        print(
            f"[GIVEAWAY] "
            f"Could not fetch original "
            f"message: HTTP {error.status}"
        )

        return

    # Restore nothing from an old giveaway.
    # This giveaway owns its own participant set.
    ACTIVE_GIVEAWAYS[
        giveaway.message.id
    ] = giveaway

    asyncio.create_task(
        giveaway_loop(
            giveaway
        )
    )


def setup(bot):

    bot.tree.add_command(
        giveaway_command
    )

    print(
        "[GIVEAWAY] "
        "/giveaway registered."
    )