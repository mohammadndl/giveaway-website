import os
import re

import discord

import database


TARGET_GIVEAWAY_BOT_ID = (
    os.getenv(
        "TARGET_GIVEAWAY_BOT_ID",
        ""
    ).strip()
    or None
)


def setup(bot):
    pass


def get_message_text(
    message
):

    parts = [
        message.content or ""
    ]

    for embed in message.embeds:

        parts.append(
            embed.title or ""
        )

        parts.append(
            embed.description or ""
        )

        if embed.author:

            parts.append(
                embed.author.name or ""
            )

        if embed.footer:

            parts.append(
                embed.footer.text or ""
            )

        for field in embed.fields:

            parts.append(
                field.name or ""
            )

            parts.append(
                field.value or ""
            )

    for row in message.components:

        for component in row.children:

            label = getattr(
                component,
                "label",
                None
            )

            custom_id = getattr(
                component,
                "custom_id",
                None
            )

            if label:
                parts.append(
                    str(label)
                )

            if custom_id:
                parts.append(
                    str(custom_id)
                )

    return " ".join(
        parts
    )


def looks_like_giveaway(
    message
):

    if not message.author.bot:
        return False

    if (
        TARGET_GIVEAWAY_BOT_ID
        and str(message.author.id)
        != TARGET_GIVEAWAY_BOT_ID
    ):

        return False

    text = get_message_text(
        message
    )

    lower = text.lower()

    score = 0

    if message.embeds:
        score += 2

    if re.search(
        r"\b\d+\s*(s|sec|secs|second|seconds|"
        r"m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|"
        r"d|day|days)\b",
        text,
        re.IGNORECASE
    ):

        score += 2

    if re.search(
        r"\b\d+\s*winners?\b",
        text,
        re.IGNORECASE
    ):

        score += 2

    giveaway_words = (
        "giveaway",
        "enter giveaway",
        "enter to win",
        "click to enter",
        "join giveaway"
    )

    if any(
        word in lower
        for word in giveaway_words
    ):

        score += 2

    for row in message.components:

        for component in row.children:

            label = getattr(
                component,
                "label",
                None
            )

            if not label:
                continue

            label = label.lower()

            if any(
                word in label
                for word in (
                    "enter",
                    "join",
                    "giveaway"
                )
            ):

                score += 3

    return score >= 5


def extract_prize(
    message
):

    if message.embeds:

        embed = message.embeds[0]

        if embed.title:

            title = embed.title.strip()

            if (
                "giveaway"
                not in title.lower()
            ):

                return title[:200]

        if embed.description:

            lines = [
                line.strip()
                for line
                in embed.description.splitlines()
                if line.strip()
            ]

            for line in lines:

                if "prize" in line.lower():

                    value = re.sub(
                        r"^.*?prize\s*[:\-]?\s*",
                        "",
                        line,
                        flags=re.IGNORECASE
                    ).strip()

                    if value:
                        return value[:200]

            if lines:
                return lines[0][:200]

    return "Unknown prize"


def extract_winner_count(
    message
):

    text = get_message_text(
        message
    )

    patterns = (
        r"(\d+)\s*winners?",
        r"winners?\s*[:\-]\s*(\d+)"
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                return int(
                    match.group(1)
                )

            except ValueError:
                pass

    return None


def extract_invite(
    message
):

    text = get_message_text(
        message
    )

    match = re.search(
        r"https?://"
        r"(?:discord\.gg|discord\.com/invite)"
        r"/[A-Za-z0-9\-]+",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(0)

    return None


async def notify_auto_join_users(
    message,
    prize,
    winner_count,
    invite_url
):

    notified = set()

    for guild in message.client.guilds:

        for member in guild.members:

            if member.bot:
                continue

            if member.id in notified:
                continue

            if not database.auto_join_enabled(
                member.id
            ):
                continue

            notified.add(
                member.id
            )

            embed = discord.Embed(
                title="🎉 GIVEAWAY DETECTED!",
                description=(
                    f"🎁 **Prize:** "
                    f"{prize}\n\n"

                    f"🏆 **Winners:** "
                    f"`{winner_count or 'Unknown'}`\n\n"

                    f"📍 **Server:** "
                    f"{message.guild.name}\n\n"

                    "Join the server and enter "
                    "the giveaway."
                )
            )

            view = discord.ui.View(
                timeout=None
            )

            if invite_url:

                view.add_item(
                    discord.ui.Button(
                        label="Join Server",
                        style=discord.ButtonStyle.link,
                        url=invite_url
                    )
                )

            view.add_item(
                discord.ui.Button(
                    label="Open Giveaway",
                    style=discord.ButtonStyle.link,
                    url=message.jump_url
                )
            )

            try:

                await member.send(
                    embed=embed,
                    view=view
                )

                print(
                    f"[DM] Giveaway sent to "
                    f"{member} ({member.id})"
                )

            except discord.Forbidden:

                print(
                    f"[DM] Cannot DM "
                    f"{member.id}"
                )

            except discord.HTTPException as e:

                print(
                    f"[DM ERROR] "
                    f"{member.id}: {e}"
                )


async def detect_winner(
    message
):

    text = get_message_text(
        message
    )

    lower = text.lower()

    winner_words = (
        "winner",
        "won",
        "congratulations",
        "congrats"
    )

    if not any(
        word in lower
        for word in winner_words
    ):

        return

    if not message.mentions:
        return

    for user in message.mentions:

        if user.bot:
            continue

        if not database.auto_join_enabled(
            user.id
        ):
            continue

        try:

            await user.send(
                "🏆 **YOU WON!**\n\n"
                "🎉 Congratulations!\n\n"
                f"🔗 **Winning message:**\n"
                f"{message.jump_url}"
            )

            print(
                f"[WINNER] "
                f"DM sent to {user.id}"
            )

        except discord.Forbidden:

            print(
                f"[WINNER] Cannot DM "
                f"{user.id}"
            )

        except discord.HTTPException as e:

            print(
                f"[WINNER ERROR] "
                f"{user.id}: {e}"
            )


async def process_message(
    message
):

    if not message.author.bot:
        return

    # Winner detection is separate from
    # giveaway detection.
    await detect_winner(
        message
    )

    if not looks_like_giveaway(
        message
    ):

        return

    if database.giveaway_exists(
        message.id
    ):

        return

    prize = extract_prize(
        message
    )

    winner_count = extract_winner_count(
        message
    )

    invite_url = extract_invite(
        message
    )

    database.save_giveaway(
        message_id=message.id,
        guild_id=(
            message.guild.id
            if message.guild
            else None
        ),
        channel_id=message.channel.id,
        jump_url=message.jump_url,
        prize=prize,
        winners=winner_count
    )

    print(
        "🎉 [GIVEAWAY DETECTED]"
    )

    print(
        f"Server: "
        f"{message.guild.name if message.guild else 'Unknown'}"
    )

    print(
        f"Prize: {prize}"
    )

    print(
        f"Winners: {winner_count}"
    )

    print(
        f"Message: {message.jump_url}"
    )

    print(
        f"Invite: "
        f"{invite_url or 'Not found'}"
    )

    await notify_auto_join_users(
        message,
        prize,
        winner_count,
        invite_url
    )