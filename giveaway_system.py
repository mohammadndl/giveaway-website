import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Set
import discord
from discord import app_commands

DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.I)
ACTIVE = {}
giveaway_bot: discord.Client


def parse_duration(value: str) -> Optional[int]:
    match = DURATION_RE.fullmatch(value)
    if not match:
        return None
    amount = int(match.group(1))
    if amount <= 0:
        return None
    seconds = amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2).lower()]
    return seconds if seconds <= 7 * 86400 else None


def format_remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    d, seconds = divmod(seconds, 86400)
    h, seconds = divmod(seconds, 3600)
    m, seconds = divmod(seconds, 60)
    if d: return f"{d}d {h}h {m}m"
    if h: return f"{h}h {m}m {seconds}s"
    if m: return f"{m}m {seconds}s"
    return f"{seconds}s"


@dataclass
class Giveaway:
    channel_id: int
    host_id: int
    prize: str
    winners: int
    end_at: float
    message: Optional[discord.Message] = None
    participants: Set[int] = field(default_factory=set)
    ended: bool = False


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway: Giveaway, disabled=False):
        super().__init__(timeout=None)
        self.giveaway = giveaway
        enter = discord.ui.Button(label="Enter Giveaway", style=discord.ButtonStyle.success, emoji="🎉", custom_id=f"giveaway_enter_{giveaway.channel_id}_{giveaway.host_id}", disabled=disabled)
        leave = discord.ui.Button(label="Leave", style=discord.ButtonStyle.secondary, emoji="🚪", custom_id=f"giveaway_leave_{giveaway.channel_id}_{giveaway.host_id}", disabled=disabled)
        enter.callback = self.enter_callback
        leave.callback = self.leave_callback
        self.add_item(enter); self.add_item(leave)

    async def enter_callback(self, interaction):
        g = self.giveaway
        if g.ended or time.time() >= g.end_at:
            await interaction.response.send_message("❌ This giveaway has ended.", ephemeral=True); return
        if interaction.user.id in g.participants:
            await interaction.response.send_message("ℹ️ You are already entered.", ephemeral=True); return
        g.participants.add(interaction.user.id)
        await interaction.response.send_message("🎉 You entered the giveaway!", ephemeral=True)
        await update_message(g)

    async def leave_callback(self, interaction):
        g = self.giveaway
        if g.ended or time.time() >= g.end_at:
            await interaction.response.send_message("❌ This giveaway has ended.", ephemeral=True); return
        if interaction.user.id not in g.participants:
            await interaction.response.send_message("ℹ️ You are not entered.", ephemeral=True); return
        g.participants.remove(interaction.user.id)
        await interaction.response.send_message("🚪 You left the giveaway.", ephemeral=True)
        await update_message(g)


def build_embed(g: Giveaway):
    remaining = max(0, int(g.end_at - time.time()))
    time_left = "ENDED" if g.ended else format_remaining(remaining)
    return discord.Embed(
        title="🎉 Giveaway Ended" if g.ended else "🎉 GIVEAWAY",
        description=(f"## 🎁 {g.prize}\n\n"
                     f"⏳ **Time Left:** `{time_left}`\n"
                     f"👥 **Participants:** `{len(g.participants)}`\n"
                     f"🏆 **Winners:** `{g.winners}`"),
    )


async def update_message(g: Giveaway):
    if not g.message:
        return
    try:
        await g.message.edit(embed=build_embed(g), view=GiveawayView(g, g.ended))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        g.message = None


async def end_giveaway(g: Giveaway):
    if g.ended: return
    g.ended = True
    ACTIVE.pop(g.channel_id, None)
    ids = list(g.participants); random.shuffle(ids)
    winners = ids[:min(g.winners, len(ids))]
    await update_message(g)
    try:
        channel = await giveaway_bot.fetch_channel(g.channel_id)
    except Exception:
        channel = None
    if not channel: return
    if not winners:
        text = f"🎉 **Giveaway Ended!**\n🎁 Prize: **{g.prize}**\n😢 No participants entered, so there are no winners."
    else:
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        text = f"🎉 **Giveaway Ended!**\n🎁 Prize: **{g.prize}**\n🏆 Winners: {mentions}"
    try:
        await channel.send(text)
    except discord.HTTPException as exc:
        print(f"[GIVEAWAY] Winner announcement failed: {exc}")


async def giveaway_loop(g: Giveaway):
    while not g.ended:
        if g.end_at - time.time() <= 0:
            await end_giveaway(g); return
        await update_message(g)
        await asyncio.sleep(1 if g.end_at - time.time() <= 60 else 5)


@app_commands.command(name="giveaway", description="Create a giveaway.")
@app_commands.describe(prize="Giveaway prize.", duration="30s, 10m, 2h, or 1d.", winners="Number of winners.")
async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: app_commands.Range[int, 1, 100]):
    if interaction.guild is None:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True); return
    seconds = parse_duration(duration)
    if seconds is None:
        await interaction.response.send_message("❌ Invalid duration. Use `30s`, `10m`, `2h`, or `1d`.", ephemeral=True); return
    if len(prize) > 256:
        await interaction.response.send_message("❌ Prize must be 256 characters or less.", ephemeral=True); return
    await interaction.response.defer()
    g = Giveaway(interaction.channel_id, interaction.user.id, prize, int(winners), time.time() + seconds)
    try:
        message = await interaction.followup.send(embed=build_embed(g), view=GiveawayView(g), wait=True)
    except discord.HTTPException as exc:
        await interaction.followup.send(f"❌ Failed to create giveaway: `{exc}`", ephemeral=True); return
    g.message = message
    ACTIVE[g.channel_id] = g
    asyncio.create_task(giveaway_loop(g))
    print(f"[GIVEAWAY] Created message={message.id} prize={prize!r} duration={duration} winners={winners}")


def setup(bot: discord.Client):
    global giveaway_bot
    giveaway_bot = bot
    bot.tree.add_command(giveaway)
